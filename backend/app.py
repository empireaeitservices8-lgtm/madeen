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


import os
import asyncio
from db import Site, Worker, Question

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as db:
        ensure_default_admin(db)
        
        # Auto-seed dummy data if the database is brand new (useful for Render deployment)
        if not db.query(Site).first():
            db.add(Site(name='Site Alpha', location='North Wing'))
            db.commit()
            db.add(Worker(full_name='John Doe', site_id=1, trade='Welder'))
            db.commit()
        
        # Auto-seed questions if empty
        if not db.query(Question).first():
            os.system("python scripts/generate_hot_work.py")
            os.system("python scripts/generate_cold_work.py")
            
    # Load models in the background so we don't block Uvicorn from binding to the port!
    # Render times out if the port isn't bound within a few minutes.
    asyncio.create_task(run_in_threadpool(detector.load_models))
    yield
    asyncio.create_task(run_in_threadpool(detector.load_models))
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
