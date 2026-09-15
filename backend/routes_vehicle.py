"""
Vehicle Inspection — Live scanning WebSocket + scan history.
Protocol mirrors /ws/scan but targets VehicleScan instead of Scan.

Client → server:
  {"type":"frame","image":"data:image/jpeg;base64,..."}
  {"type":"record","vehicle_type":"Dump Truck","site_id":1}
  {"type":"reset"}

Server → client:
  {"type":"detection",...}
  {"type":"recorded","scan":{...}}
  {"type":"error","message":"..."}
"""

import base64
import binascii
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

import detector
from auth import ensure_site_access, get_current_user, scoped_site_id, user_from_token
from config import APP_TZ, SNAPSHOT_DIR
from db import VEHICLE_ITEMS, SessionLocal, Site, User, VehicleScan, get_db, utcnow
from routes_scans import user_from_header_or_query, iso, to_local, _date_bounds

router = APIRouter()

# ---------- serializer ----------

def vscan_out(s: VehicleScan) -> dict:
    return {
        "id": s.id,
        "created_at": iso(s.created_at),
        "vehicle_type": s.vehicle_type,
        "site": {"id": s.site.id, "name": s.site.name},
        "scanned_by": {"id": s.user.id, "username": s.user.username,
                       "full_name": s.user.full_name or ""},
        "items": s.items(),
        "overall": s.overall,
        "has_snapshot": bool(s.snapshot_path),
        "snapshot_url": f"/api/vehicle-scans/{s.id}/snapshot" if s.snapshot_path else None,
    }


VSCAN_LOAD = (selectinload(VehicleScan.site), selectinload(VehicleScan.user))


# ---------- vehicle-specific LiveScan wrapper ----------

# ── COCO class IDs that correspond to vehicles/heavy equipment ─────────────
# These are the standard YOLO/COCO class IDs present in yolov8n-pose.pt when
# used as a general detector (the pose model is YOLOv8n trained on COCO).
COCO_VEHICLE_CLASSES = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    # heavy equipment mapped via generic vehicle classes
    # (a fine-tuned model would add excavator, bulldozer, etc. directly)
}

# Checklist items that need a vehicle to be present to make sense
VEHICLE_ITEMS_NEED_VEHICLE = {"lights", "tires", "mirrors", "windshield",
                               "fire_extinguisher", "beacon", "reverse_alarm", "body_condition"}


def _analyze_vehicle_frame(frame) -> dict:
    """
    Run the pose model as a plain object detector (no keypoints needed) to find
    vehicle-class objects in the frame.  Returns a dict with:
      - vehicle_found: bool
      - vehicle_labels: list[str]   — e.g. ["truck"]
      - detections: list[dict]      — boxes for the overlay
      - frame_size: [w, h]
    """
    import detector as _det
    _det.load_models()
    import config as _cfg
    frame_h, frame_w = frame.shape[:2]
    device = _cfg.DEVICE or None

    # Use the pose model as a generic COCO detector — same weights, just don't
    # request pose keypoints so it works on all object classes.
    # classes=None → detect everything; we filter by COCO_VEHICLE_CLASSES afterwards.
    with _det._lock:
        result = _det._pose_model.predict(
            frame,
            conf=0.25,          # lower threshold so partially-visible vehicles are caught
            verbose=False,
            device=device,
        )[0]

    vehicle_found = False
    vehicle_labels = []
    detections = []

    if result.boxes is not None:
        for box, conf, cls_id in zip(
            result.boxes.xyxy.cpu().numpy(),
            result.boxes.conf.cpu().numpy(),
            result.boxes.cls.cpu().numpy(),
        ):
            cid = int(cls_id)
            label = COCO_VEHICLE_CLASSES.get(cid)
            if label:
                vehicle_found = True
                vehicle_labels.append(label)
                detections.append({
                    "label": label,
                    "x1": round(float(box[0]), 1), "y1": round(float(box[1]), 1),
                    "x2": round(float(box[2]), 1), "y2": round(float(box[3]), 1),
                    "confidence": round(float(conf), 2),
                })

    return {
        "frame_size": [frame_w, frame_h],
        "vehicle_found": vehicle_found,
        "vehicle_labels": vehicle_labels,
        "detections": detections,
    }


class VehicleLiveScan:
    """
    Per-connection state for vehicle inspection.

    A frame is only counted toward the smoothing window if at least one
    COCO vehicle-class object is detected. This prevents a person's face
    (or any non-vehicle content) from being recorded as a passing inspection.

    Items:
      body_condition  — PASS only when a vehicle object is actually detected
      All other items — always NOT VISIBLE with the current generic model
                        (a fine-tuned vehicle-parts model would fill these in)
    stable            — True only after WINDOW consecutive vehicle frames
    """

    WINDOW = 8

    def __init__(self):
        self._history: list[dict] = []
        self.last_frame = None
        self.last_analysis: dict = {}
        self._consecutive_no_vehicle = 0

    def update(self, frame, analysis: dict) -> dict:
        """
        analysis here is the raw PPE/pose dict from analyze_frame().
        We run our own vehicle detection on top of the same frame.
        """
        self.last_frame = frame

        # Run vehicle-class detection
        vehicle_info = _analyze_vehicle_frame(frame)
        self.last_analysis = vehicle_info

        if not vehicle_info["vehicle_found"]:
            # No vehicle → reset history so a person can't sneak in 8 frames
            self._consecutive_no_vehicle += 1
            if self._consecutive_no_vehicle >= 3:
                self._history.clear()
            return self.smoothed()

        self._consecutive_no_vehicle = 0

        # Build per-item statuses for this frame.
        # With a generic COCO model we can only confirm the vehicle is present
        # (body_condition). All specific part items stay not_visible until a
        # specialised vehicle-parts model is available.
        frame_items: dict[str, str] = {item: "not_visible" for item in VEHICLE_ITEMS}
        frame_items["body_condition"] = "pass"   # vehicle confirmed in frame

        self._history.append(frame_items)
        if len(self._history) > self.WINDOW:
            self._history.pop(0)

        return self.smoothed()

    def smoothed(self) -> dict:
        if not self._history:
            blank = {item: "no_vehicle" for item in VEHICLE_ITEMS}
            return {"items": blank, "overall": "fail", "stable": False,
                    "confidence": 0.0, "frames": 0}

        result: dict[str, str] = {}
        for item in VEHICLE_ITEMS:
            counts: dict[str, int] = {}
            for frame in self._history:
                v = frame.get(item, "no_vehicle")
                counts[v] = counts.get(v, 0) + 1
            result[item] = max(counts, key=lambda k: counts[k])

        all_pass = all(v == "pass" for v in result.values())
        overall = "pass" if all_pass else "fail"
        stable = len(self._history) >= self.WINDOW

        return {"items": result, "overall": overall, "stable": stable,
                "confidence": 1.0, "frames": len(self._history)}

    def has_vehicle(self) -> bool:
        return bool(self._history)



# ---------- record helper ----------

def _record_vscan(db: Session, user: User, vehicle_type: str, site_id: int,
                   live: VehicleLiveScan) -> VehicleScan:
    site = db.get(Site, site_id)
    if not site or not site.is_active:
        raise ValueError("Site not found or inactive")
    if user.role != "admin" and user.site_id != site_id:
        raise ValueError("You can only scan vehicles at your own site")

    smoothed = live.smoothed()
    if not smoothed["stable"]:
        raise ValueError("Result isn't stable yet. Hold the camera steady for a moment")

    scan = VehicleScan(
        vehicle_type=vehicle_type,
        site_id=site_id,
        user_id=user.id,
        overall=smoothed["overall"],
        details={"frames": smoothed["frames"]},
        **{item: smoothed["items"][item] for item in VEHICLE_ITEMS},
    )
    db.add(scan)
    db.flush()

    # Save snapshot
    if live.last_frame is not None:
        now = utcnow()
        rel_path = Path(f"{now:%Y}") / f"{now:%m}" / f"vscan_{scan.id}.jpg"
        (SNAPSHOT_DIR / rel_path).parent.mkdir(parents=True, exist_ok=True)
        analysis = live.last_analysis or {}
        (SNAPSHOT_DIR / rel_path).write_bytes(
            detector.annotate_snapshot(live.last_frame, analysis, smoothed["items"])
        )
        scan.snapshot_path = rel_path.as_posix()

    db.commit()
    return db.scalar(select(VehicleScan).options(*VSCAN_LOAD).where(VehicleScan.id == scan.id))


# ---------- WebSocket ----------

@router.websocket("/ws/vehicle-scan")
async def vehicle_scan_socket(websocket: WebSocket, token: Optional[str] = None):
    await websocket.accept()
    with SessionLocal() as db:
        user = user_from_token(token, db)
    if not user:
        await websocket.close(code=4401)
        return

    live = VehicleLiveScan()
    await run_in_threadpool(detector.load_models)

    async def send_error(msg: str):
        await websocket.send_json({"type": "error", "message": msg})

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            frame_bytes = message.get("bytes")

            if frame_bytes is None:
                try:
                    payload = json.loads(message.get("text") or "")
                    kind = payload.get("type")
                except (json.JSONDecodeError, AttributeError):
                    await send_error("Messages must be JSON objects")
                    continue

                if kind == "reset":
                    live = VehicleLiveScan()
                    continue

                if kind == "record":
                    try:
                        vtype = str(payload.get("vehicle_type", "")).strip()
                        sid = int(payload.get("site_id"))
                        if not vtype:
                            raise ValueError("vehicle_type is required")
                        with SessionLocal() as db:
                            vscan = await run_in_threadpool(
                                _record_vscan, db, db.get(User, user.id), vtype, sid, live)
                        live = VehicleLiveScan()
                        await websocket.send_json({"type": "recorded", "scan": vscan_out(vscan)})
                    except (ValueError, TypeError) as exc:
                        await send_error(str(exc) if isinstance(exc, ValueError)
                                         and "invalid literal" not in str(exc)
                                         else "record needs vehicle_type string and numeric site_id")
                    continue

                if kind != "frame":
                    await send_error(f"Unknown message type: {kind}")
                    continue

                try:
                    frame_bytes = base64.b64decode(
                        str(payload.get("image", "")).split(",")[-1], validate=False)
                except (binascii.Error, ValueError):
                    await send_error("Frame image isn't valid base64")
                    continue

            start = time.perf_counter()
            frame = detector.decode_jpeg(frame_bytes) if frame_bytes else None
            if frame is None:
                await send_error("Could not decode frame as JPEG")
                continue

            try:
                analysis = await run_in_threadpool(detector.analyze_frame, frame)
                smoothed = live.update(frame, analysis)
                latency_ms = round((time.perf_counter() - start) * 1000)

                # Use the vehicle-specific analysis stored in live (set by _analyze_vehicle_frame)
                veh = live.last_analysis or {}
                fw, fh = (veh.get("frame_size") or analysis["frame_size"])
                await websocket.send_json({
                    "type": "detection",
                    "frame_width": fw,
                    "frame_height": fh,
                    "person": None,   # vehicle scan — never highlight a person box
                    "detections": veh.get("detections", []),   # vehicle bounding boxes
                    "items": smoothed["items"],
                    "overall": smoothed["overall"],
                    "stable": smoothed["stable"],
                    "latency_ms": latency_ms,
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                await send_error(f"Internal Error: {str(e)}")

    except WebSocketDisconnect:
        pass


# ---------- REST ----------

def _filtered_vscans(query, user: User, site_id=None, vehicle_type=None,
                     result=None, date_from=None, date_to=None):
    scope = scoped_site_id(user)
    if scope is not None:
        query = query.where(VehicleScan.site_id == scope)
    if site_id:
        query = query.where(VehicleScan.site_id == site_id)
    if vehicle_type:
        query = query.where(VehicleScan.vehicle_type == vehicle_type)
    if result:
        query = query.where(VehicleScan.overall == result)
    start, end = _date_bounds(date_from, date_to)
    if start:
        query = query.where(VehicleScan.created_at >= start)
    if end:
        query = query.where(VehicleScan.created_at < end)
    return query


@router.get("/api/vehicle-scans")
def list_vehicle_scans(
    site_id: Optional[int] = None,
    vehicle_type: Optional[str] = None,
    result: Optional[str] = Query(default=None, pattern="^(pass|fail)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = _filtered_vscans(select(VehicleScan), user, site_id, vehicle_type, result, date_from, date_to)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.options(*VSCAN_LOAD)
        .order_by(VehicleScan.created_at.desc(), VehicleScan.id.desc())
        .limit(limit).offset(offset)
    )
    return {"items": [vscan_out(s) for s in rows], "total": total}


@router.get("/api/vehicle-scans/{scan_id}")
def get_vehicle_scan(scan_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    scan = db.scalar(select(VehicleScan).options(*VSCAN_LOAD).where(VehicleScan.id == scan_id))
    if not scan:
        raise HTTPException(404, "Vehicle scan not found")
    ensure_site_access(user, scan.site_id)
    return vscan_out(scan)


@router.get("/api/vehicle-scans/{scan_id}/snapshot")
def get_vehicle_snapshot(scan_id: int, user: User = Depends(user_from_header_or_query),
                         db: Session = Depends(get_db)):
    scan = db.scalar(select(VehicleScan).options(*VSCAN_LOAD).where(VehicleScan.id == scan_id))
    if not scan or not scan.snapshot_path:
        raise HTTPException(404, "Snapshot not found")
    ensure_site_access(user, scan.site_id)
    path = (SNAPSHOT_DIR / scan.snapshot_path).resolve()
    if not path.is_file() or SNAPSHOT_DIR.resolve() not in path.parents:
        raise HTTPException(404, "Snapshot not found")
    return FileResponse(path, media_type="image/jpeg")
