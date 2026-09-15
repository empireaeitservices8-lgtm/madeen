# Training a better PPE model

The scanner ships with an open-source YOLOv8n PPE model
([Tanishjain9/yolov8n-ppe-detection-6classes](https://huggingface.co/Tanishjain9/yolov8n-ppe-detection-6classes),
MIT license, ~0.81 mAP50 overall; gloves ~0.69 and safety shoes ~0.64 are its weakest classes).
Fine-tuning on photos from **your** sites (your lighting, your vest colors, your camera angles)
is the single biggest accuracy improvement.

## 1. Collect and label images

- 300–1,000 photos taken with the phones/laptops you'll actually scan with, at scan distance.
- Include workers **with and without** each item, different lighting, and partially visible bodies.
- Label with [Roboflow](https://roboflow.com), [CVAT](https://cvat.ai) or [Label Studio](https://labelstud.io)
  and export in **YOLOv8** format.
- Easiest: keep the bundled model's class names and order — `Gloves, Vest, goggles, helmet, mask, safety_shoe`.
  You can also add explicit "missing" classes such as `no_helmet`, `no_vest`, `no_gloves`, `no_boots`, `no_mask`;
  the detector understands them (see `POSITIVE_CLASSES` / `NEGATIVE_CLASSES` in `detector.py`).

The original model's training dataset (15.6k images, ~670 MB) is published in the same
Hugging Face repo if you want to merge it with your own photos.

## 2. Train (RTX 3050 6 GB)

```bash
cd backend
.venv\Scripts\activate
python training/train.py --data path/to/data.yaml --epochs 50
```

- Starts from the bundled PPE model by default (fastest). Use `--model yolov8s.pt` for a larger,
  more accurate model trained from COCO (use `--batch 8` on 6 GB).
- Roughly 1–3 hours for a few thousand images. Training stops early if validation stops improving.
- Results, charts and the confusion matrix land in `training/runs/<name>/`.

## 3. Use the new model

The script copies the best weights to `weights/ppe_custom.pt`. In `backend/.env`:

```
PPE_MODEL_PATH=./weights/ppe_custom.pt
```

Restart the backend. `GET /api/model` shows which model and classes are loaded.
