"""
Real PPE detection.

Two models run on every frame:
  1. YOLOv8n-pose finds the worker and 17 body keypoints (head, shoulders, wrists, ankles...).
     Keypoints tell us which body parts are actually in view, so an item can be
     reported as "not_visible" (e.g. feet out of frame) instead of a false "fail".
  2. A YOLOv8n PPE model finds gear: gloves, vest, goggles, helmet, mask, safety shoes.

Each gear detection is matched to the worker's body region it belongs to
(helmet near the head, gloves near a wrist, ...). Per item:
  pass        - matching gear detected on the worker
  fail        - body part visible but no gear on it (or a "no_<item>" class detected)
  not_visible - body part not in view, so we can't tell

LiveScan smooths results over the last few frames (majority vote) so the
checklist doesn't flicker, and keeps the latest frame for the snapshot.
"""

import threading
from collections import Counter, deque
from typing import Optional

import cv2
import numpy as np
import torch
from ultralytics import YOLO

import config
from db import PPE_ITEMS

# Class names (lowercased, "-" and " " -> "_") mapped to checklist items.
# Covers the bundled model plus common names from other PPE datasets, so a
# retrained model drops in without code changes.
POSITIVE_CLASSES = {
    "helmet": "helmet", "hardhat": "helmet", "hard_hat": "helmet",
    "vest": "vest", "safety_vest": "vest", "reflective_vest": "vest",
    "gloves": "gloves", "glove": "gloves",
    "safety_shoe": "boots", "safety_shoes": "boots", "shoes": "boots", "boots": "boots", "boot": "boots",
    "mask": "mask", "face_mask": "mask",
}
NEGATIVE_CLASSES = {
    "no_helmet": "helmet", "no_hardhat": "helmet",
    "no_vest": "vest", "no_safety_vest": "vest",
    "no_gloves": "gloves", "no_glove": "gloves",
    "no_shoes": "boots", "no_boots": "boots", "no_safety_shoe": "boots",
    "no_mask": "mask",
}

# COCO keypoint indices
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST = 5, 6, 9, 10
L_HIP, R_HIP, L_ANKLE, R_ANKLE = 11, 12, 15, 16

_lock = threading.Lock()
_ppe_model: Optional[YOLO] = None
_pose_model: Optional[YOLO] = None


def _normalize(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def load_models() -> None:
    """Load both models once and warm them up so the first scan isn't slow."""
    global _ppe_model, _pose_model
    with _lock:
        if _ppe_model is None:
            _ppe_model = YOLO(config.PPE_MODEL_PATH)
            _pose_model = YOLO(config.POSE_MODEL_PATH)
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            _pose_model.predict(blank, verbose=False, device=config.DEVICE or None)
            _ppe_model.predict(blank, verbose=False, device=config.DEVICE or None)


def model_info() -> dict:
    load_models()
    return {
        "ppe_model": config.PPE_MODEL_PATH,
        "ppe_classes": list(_ppe_model.names.values()),
        "pose_model": config.POSE_MODEL_PATH,
        "device": str(_ppe_model.device),
    }


def health() -> dict:
    """Cheap status for /health: doesn't trigger model loading."""
    loaded = _ppe_model is not None and _pose_model is not None
    device = str(_ppe_model.device) if loaded else ("cuda" if torch.cuda.is_available() else "cpu")
    return {"model_loaded": loaded, "device": "cuda" if device.startswith("cuda") else "cpu"}


def decode_jpeg(data: bytes) -> Optional[np.ndarray]:
    """Decode JPEG bytes into a BGR image (the format Ultralytics expects for arrays)."""
    return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)


def _center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def _visible(kpts: np.ndarray, *indices: int) -> list:
    """Return (x, y) for each requested keypoint that the pose model is confident about."""
    return [kpts[i][:2] for i in indices if kpts[i][2] >= config.KEYPOINT_CONFIDENCE]


def _inside(box, person_box) -> bool:
    cx, cy = _center(box)
    return person_box[0] <= cx <= person_box[2] and person_box[1] <= cy <= person_box[3]


def _near_any(point, anchors, radius: float) -> bool:
    return any(np.hypot(point[0] - a[0], point[1] - a[1]) <= radius for a in anchors)


def _body_regions(person_box, kpts: np.ndarray, frame_h: int) -> dict:
    """Work out which body parts are in view and where to look for each item."""
    x1, y1, x2, y2 = person_box
    h = max(y2 - y1, 1.0)
    head = _visible(kpts, NOSE, L_EYE, R_EYE, L_EAR, R_EAR)
    face = _visible(kpts, NOSE, L_EYE, R_EYE)
    shoulders = _visible(kpts, L_SHOULDER, R_SHOULDER)
    hips = _visible(kpts, L_HIP, R_HIP)
    wrists = _visible(kpts, L_WRIST, R_WRIST)
    # Ankles right at the bottom edge usually mean the feet are cut off.
    ankles = [a for a in _visible(kpts, L_ANKLE, R_ANKLE) if a[1] < frame_h * 0.97]
    return {
        "height": h,
        "head": head, "face": face, "shoulders": shoulders, "hips": hips,
        "wrists": wrists, "ankles": ankles,
        "visible": {
            "helmet": len(head) > 0,
            "mask": len(face) > 0,
            "vest": len(shoulders) > 0 and (len(hips) > 0 or len(shoulders) == 2),
            "gloves": len(wrists) > 0,
            "boots": len(ankles) > 0,
        },
    }


def _matches_body(item: str, box, person_box, regions: dict) -> bool:
    """Does a gear detection sit where that item is worn on this worker?"""
    x1, y1, x2, y2 = person_box
    h = regions["height"]
    pad = 0.15 * (x2 - x1)
    cx, cy = _center(box)
    # Must overlap the worker (helmets can stick out above the person box).
    if not (x1 - pad <= cx <= x2 + pad and y1 - 0.15 * h <= cy <= y2 + 0.05 * h):
        return False
    if item == "helmet":
        head_y = min((p[1] for p in regions["head"]), default=y1 + 0.1 * h)
        return cy <= head_y + 0.08 * h
    if item == "mask":
        anchors = regions["face"] or regions["head"]
        return _near_any((cx, cy), anchors, 0.12 * h) if anchors else cy <= y1 + 0.3 * h
    if item == "vest":
        return y1 + 0.12 * h <= cy <= y1 + 0.75 * h
    if item == "gloves":
        return _near_any((cx, cy), regions["wrists"], 0.15 * h) if regions["wrists"] else False
    if item == "boots":
        if regions["ankles"]:
            return _near_any((cx, cy), regions["ankles"], 0.15 * h)
        return cy >= y1 + 0.8 * h
    return False


def analyze_frame(frame: np.ndarray) -> dict:
    """Run both models on one BGR frame and return per-item statuses for the main worker."""
    load_models()
    frame_h, frame_w = frame.shape[:2]
    device = config.DEVICE or None
    with _lock:
        pose = _pose_model.predict(frame, conf=config.PERSON_CONFIDENCE, classes=[0],
                                   verbose=False, device=device)[0]
        ppe = _ppe_model.predict(frame, conf=config.PPE_CONFIDENCE, verbose=False, device=device)[0]

    result = {"frame_size": [frame_w, frame_h], "person": None, "detections": [], "items": None}

    # Main worker = largest person in view (the one standing in front of the camera).
    person_box, kpts = None, None
    if pose.boxes is not None and len(pose.boxes):
        boxes = pose.boxes.xyxy.cpu().numpy()
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        idx = int(np.argmax(areas))
        person_box = boxes[idx].tolist()
        kpts = pose.keypoints.data[idx].cpu().numpy()
        result["person"] = {
            "box": [round(v, 1) for v in person_box],
            "confidence": round(float(pose.boxes.conf[idx]), 2),
            "others": len(boxes) - 1,
        }

    regions = _body_regions(person_box, kpts, frame_h) if person_box is not None else None
    positive = {item: 0.0 for item in PPE_ITEMS}
    negative = {item: 0.0 for item in PPE_ITEMS}

    for box, conf, cls in zip(ppe.boxes.xyxy.cpu().numpy(), ppe.boxes.conf.cpu().numpy(),
                              ppe.boxes.cls.cpu().numpy()):
        label = ppe.names[int(cls)]
        key = _normalize(label)
        item = POSITIVE_CLASSES.get(key) or NEGATIVE_CLASSES.get(key)
        is_negative = key in NEGATIVE_CLASSES
        if item:
            matched = bool(regions and _matches_body(item, box.tolist(), person_box, regions))
        else:  # gear we show but don't check (goggles): just needs to be on the worker
            matched = bool(regions and _inside(box.tolist(), person_box))
        if matched and item:
            target = negative if is_negative else positive
            target[item] = max(target[item], float(conf))
        result["detections"].append({
            "label": label,
            "item": item,  # None for classes we don't check (e.g. goggles)
            "negative": is_negative,
            "box": [round(float(v), 1) for v in box],
            "confidence": round(float(conf), 2),
            "on_worker": matched,
        })

    if regions is None:
        return result

    items, confidence = {}, {}
    for item in PPE_ITEMS:
        if positive[item] and positive[item] >= negative[item]:
            items[item], confidence[item] = "pass", round(positive[item], 2)
        elif negative[item]:
            items[item], confidence[item] = "fail", round(negative[item], 2)
        elif regions["visible"][item]:
            items[item], confidence[item] = "fail", None
        else:
            items[item], confidence[item] = "not_visible", None
    result["items"] = items
    result["confidence"] = confidence

    if config.GEMINI_API_KEY:
        try:
            import cv2
            import json
            import base64
            import requests
            
            api_key = config.GEMINI_API_KEY
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            
            _, encoded = cv2.imencode(".jpg", frame)
            b64_image = base64.b64encode(encoded).decode("utf-8")
            
            prompt = """
            Analyze this image of a worker. They may be wearing standard construction PPE or alternative protective gear like white cleanroom/hazmat coveralls with hoods.
            Determine the compliance status for the following 5 items: helmet, vest, gloves, boots, mask.
            A cleanroom hood counts as BOTH a helmet and a mask if it covers the head and face.
            A full-body coverall counts as a vest.
            Return ONLY a JSON object exactly like this:
            {"helmet": "pass"|"fail"|"not_visible", "vest": "pass"|"fail"|"not_visible", "gloves": "pass"|"fail"|"not_visible", "boots": "pass"|"fail"|"not_visible", "mask": "pass"|"fail"|"not_visible"}
            """
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}
                        ]
                    }
                ],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            
            resp_data = response.json()
            text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
            llm_items = json.loads(text)
            
            for key in PPE_ITEMS:
                if key in llm_items and llm_items[key] in ("pass", "fail", "not_visible"):
                    result["items"][key] = llm_items[key]
                    result["confidence"][key] = None
        except Exception as e:
            print("Gemini fallback failed:", e)
    else:
        # Fast local fallback using color heuristics for missing items
        if person_box:
            x1, y1, x2, y2 = [int(v) for v in person_box]
            h = regions["height"]
            
            # Helmet fallback (Look for bright yellow at the top 15% of the person box)
            if result["items"].get("helmet") == "fail":
                head_crop = frame[max(0, int(y1 - 0.1 * h)):int(y1 + 0.15 * h), x1:x2]
                if head_crop.size > 0:
                    hsv = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
                    yellow_mask = cv2.inRange(hsv, np.array([15, 100, 100]), np.array([35, 255, 255]))
                    if cv2.countNonZero(yellow_mask) > 100:
                        result["items"]["helmet"] = "pass"
                        
            # Mask fallback (Look for white/gray in the face region)
            if result["items"].get("mask") == "fail":
                face_crop = frame[int(y1 + 0.1 * h):int(y1 + 0.3 * h), x1:x2]
                if face_crop.size > 0:
                    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
                    white_mask = cv2.inRange(gray, 200, 255)
                    if cv2.countNonZero(white_mask) > 50:
                        result["items"]["mask"] = "pass"
                        
            # Gloves fallback (Look for white/gray near the bottom half of the person)
            if result["items"].get("gloves") == "fail":
                hands_crop = frame[int(y1 + 0.4 * h):int(y2), x1:x2]
                if hands_crop.size > 0:
                    gray = cv2.cvtColor(hands_crop, cv2.COLOR_BGR2GRAY)
                    white_mask = cv2.inRange(gray, 200, 255)
                    if cv2.countNonZero(white_mask) > 100:
                        result["items"]["gloves"] = "pass"

    return result


def overall_status(items: Optional[dict]) -> Optional[str]:
    """pass only if every item passes; not_visible counts as not passing. None when nobody is in view."""
    if not items:
        return None
    return "pass" if all(status == "pass" for status in items.values()) else "fail"


class LiveScan:
    """Per-connection state: smooths item statuses over recent frames and keeps the latest frame."""

    def __init__(self, window: int = config.SMOOTHING_FRAMES):
        self.window = window
        self.history: deque = deque(maxlen=window)
        self.confidence_history: deque = deque(maxlen=window)
        self.last_frame: Optional[np.ndarray] = None
        self.last_analysis: Optional[dict] = None

    def update(self, frame: np.ndarray, analysis: dict) -> dict:
        if analysis["items"] is None:
            # Worker stepped out of view: start fresh so an old result can't be saved for someone else.
            self.history.clear()
            self.confidence_history.clear()
        else:
            self.history.append(analysis["items"])
            self.confidence_history.append(analysis["confidence"])
            self.last_frame = frame
            self.last_analysis = analysis
        return self.smoothed()

    def smoothed(self) -> dict:
        """
        Majority vote per item over the recent frames.
        stable = the window is full and every item's winning status held in at least 60% of those
        frames, i.e. enough consistent frames to record a result.
        """
        if not self.history:
            return {"items": {item: "no_person" for item in PPE_ITEMS}, "overall": None,
                    "frames": 0, "stable": False, "confidence": None}
        items, confidence, agreement = {}, {}, 1.0
        for item in PPE_ITEMS:
            counts = Counter(frame[item] for frame in self.history)
            # Most common status wins; on a tie, prefer the safer answer (fail > not_visible > pass).
            items[item] = max(counts, key=lambda s: (counts[s], {"fail": 2, "not_visible": 1, "pass": 0}[s]))
            agreement = min(agreement, counts[items[item]] / len(self.history))
            scores = [c[item] for c in self.confidence_history if c.get(item) is not None]
            confidence[item] = round(sum(scores) / len(scores), 2) if scores else None
        return {
            "items": items,
            "overall": overall_status(items),
            "frames": len(self.history),
            "stable": len(self.history) >= self.window and agreement >= 0.6,
            "confidence": confidence,
        }

    def has_person(self) -> bool:
        return bool(self.history) and self.last_frame is not None


STATUS_COLORS = {"pass": (94, 197, 34), "fail": (68, 68, 239), "not_visible": (11, 158, 245)}


def annotate_snapshot(frame: np.ndarray, analysis: Optional[dict], items: Optional[dict]) -> bytes:
    """Draw the worker box, gear boxes and the checklist onto a copy of the frame; return JPEG bytes."""
    img = frame.copy()
    if analysis and analysis.get("person"):
        x1, y1, x2, y2 = map(int, analysis["person"]["box"])
        cv2.rectangle(img, (x1, y1), (x2, y2), (200, 200, 200), 2)
    for det in (analysis or {}).get("detections", []):
        if not det["on_worker"]:
            continue
        x1, y1, x2, y2 = map(int, det["box"])
        color = (68, 68, 239) if det["negative"] else (94, 197, 34)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, f"{det['label']} {det['confidence']:.2f}", (x1, max(y1 - 6, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    if items:
        y = 24
        for item in PPE_ITEMS:
            status = items[item]
            text = f"{item}: {status.replace('_', ' ')}"
            cv2.putText(img, text, (11, y + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(img, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, STATUS_COLORS[status], 1, cv2.LINE_AA)
            y += 24
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes() if ok else b""
