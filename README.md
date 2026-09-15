# PPE Scanner - Working Prototype (Pipeline Only)

This proves the full flow end to end: browser camera → live stream to backend →
server-side detection → results shown back in real time on the video overlay.

**What's real:** camera capture, WebSocket streaming, server-side person
detection (pretrained YOLOv8n), live bounding box overlay, latency measurement.

**What's fake (on purpose, for now):** the helmet/vest/gloves/boots/mask
pass/fail checklist. It's random data from `run_ppe_check()` in
`backend/app.py`, clearly commented, so you can see the full UI/UX working
before investing time in training a real PPE model.

## 1. Run the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

First run will download `yolov8n.pt` (~6MB) automatically.

Check it's up: open http://localhost:8000/health -> should return `{"status":"ok"}`

## 2. Run the frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000 in your browser.

## 3. Testing on your phone (same wifi as your laptop)

1. Find your laptop's LAN IP (`ipconfig` on Windows, `ifconfig` or `ip addr` on Mac/Linux) — looks like `192.168.x.x`
2. In `frontend/.env.local`, set:
   ```
   NEXT_PUBLIC_WS_URL=ws://192.168.x.x:8000/ws/scan
   ```
3. Restart `npm run dev`
4. On your phone browser, go to `http://192.168.x.x:3000`
5. Note: most mobile browsers require HTTPS for camera access on non-localhost
   origins. If the camera doesn't open on phone, you'll need to run this behind
   HTTPS (e.g. via `ngrok http 3000` and `ngrok http 8000`, or a reverse proxy
   with a real cert) — happy to set that up next if you hit this.

## Next steps (real PPE detection)

Replace `run_ppe_check()` in `backend/app.py` with a real model:
1. Collect/label a PPE dataset (helmet, no-helmet, vest, no-vest, etc.) or start
   from an open dataset on Roboflow Universe.
2. Fine-tune a YOLOv8 model on those classes (`ultralytics` supports this
   directly - `yolo train data=ppe.yaml model=yolov8n.pt`).
3. Load your fine-tuned `.pt` file instead of `yolov8n.pt` and map its output
   classes to the `PPE_ITEMS` checklist.

Everything else (streaming, overlay, checklist UI, latency tracking) stays
the same.
