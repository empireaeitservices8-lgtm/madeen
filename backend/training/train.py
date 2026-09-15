"""
Fine-tune the PPE detector on your own labeled photos.

Usage (from the backend folder, venv active):
  python training/train.py --data training/ppe.yaml
  python training/train.py --data path/to/roboflow_export/data.yaml --epochs 80 --model yolov8s.pt

When training finishes, the best weights are copied to weights/ppe_custom.pt.
Point the server at them with PPE_MODEL_PATH=./weights/ppe_custom.pt in backend/.env
and restart. Class names are matched automatically (see POSITIVE_CLASSES in detector.py),
so names like "helmet", "hardhat", "vest", "gloves", "boots", "mask", "no_helmet" all work.
"""

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

BACKEND_DIR = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Fine-tune the PPE detection model")
    parser.add_argument("--data", required=True, help="Dataset YAML (YOLO format)")
    parser.add_argument("--model", default=str(BACKEND_DIR / "weights" / "ppe_yolov8n.pt"),
                        help="Starting weights: the bundled PPE model (default) or yolov8n.pt / yolov8s.pt")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16, help="Lower this if you run out of GPU memory (6 GB: 16 for n, 8 for s)")
    parser.add_argument("--device", default="0", help='"0" for the first GPU, or "cpu"')
    parser.add_argument("--name", default="ppe_custom")
    args = parser.parse_args()

    model = YOLO(args.model)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=str(BACKEND_DIR / "training" / "runs"),
        name=args.name,
        exist_ok=True,
        patience=15,   # stop early if validation stops improving
        workers=2,     # Windows is happier with few dataloader workers
    )

    best = BACKEND_DIR / "training" / "runs" / args.name / "weights" / "best.pt"
    target = BACKEND_DIR / "weights" / f"{args.name}.pt"
    shutil.copy(best, target)
    metrics = YOLO(target).val(data=args.data, imgsz=args.imgsz, device=args.device, verbose=False)
    print(f"\nSaved {target}")
    print(f"mAP50: {metrics.box.map50:.3f}   mAP50-95: {metrics.box.map:.3f}")
    print(f"Use it: set PPE_MODEL_PATH=./weights/{target.name} in backend/.env and restart the server.")


if __name__ == "__main__":
    main()
