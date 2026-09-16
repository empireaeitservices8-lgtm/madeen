"""
PPE Scanner - Backend
---------------------
FastAPI app: real PPE detection over WebSocket, scan logging with snapshots,
violations, compliance reports, and admin/supervisor accounts.

Run (from the backend folder):
  .venv\\Scripts\\activate            (macOS/Linux: source .venv/bin/activate)
  uvicorn app:app --host 0.0.0.0 --port 8000

Endpoints and the WebSocket protocol follow API_CONTRACT.md in the project root.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

import detector
from auth import ensure_default_admin
from config import CORS_ORIGINS
from db import SessionLocal, init_db
from routes_manage import router as manage_router
from routes_scans import router as scans_router
from routes_vehicle import router as vehicle_router
from routes_test import router as test_router
from routes_tool import router as tool_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        ensure_default_admin(db)
    await run_in_threadpool(detector.load_models)  # load + warm up before the first scan
    yield


app = FastAPI(title="PPE Scanner API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(manage_router)
app.include_router(scans_router)
app.include_router(vehicle_router)
app.include_router(test_router)
app.include_router(tool_router)


@app.get("/health")
def health():
    return {"status": "ok", **detector.health()}
