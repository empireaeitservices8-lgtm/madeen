"""
Live scanning (WebSocket), scan history, violations and compliance reports.
Shapes follow API_CONTRACT.md in the project root.
"""

import base64
import binascii
import csv
import io
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import (APIRouter, Depends, File, HTTPException, Query, UploadFile, WebSocket,
                     WebSocketDisconnect)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

import detector
from auth import bearer, ensure_site_access, get_current_user, scoped_site_id, user_from_token
from config import APP_TZ, SNAPSHOT_DIR
from db import PPE_ITEMS, Scan, SessionLocal, User, Violation, Worker, get_db, utcnow

router = APIRouter()

RESULT_PATTERN = "^(pass|fail)$"


def user_from_header_or_query(
    token: Optional[str] = Query(default=None, description="Alternative to the Authorization header"),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    user = user_from_token(creds.credentials if creds else token, db)
    if not user:
        raise HTTPException(401, "Not logged in or session expired")
    return user


# ---------- time helpers (DB stores naive UTC; filters use calendar days in APP_TZ) ----------

def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.replace(microsecond=0).isoformat() + "Z" if dt else None


def to_local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(APP_TZ)


def _parse_day(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "Dates must be YYYY-MM-DD")


def _local_midnight_utc(day: date) -> datetime:
    local = datetime(day.year, day.month, day.day, tzinfo=APP_TZ)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _date_bounds(date_from: Optional[str], date_to: Optional[str]):
    start, end = _parse_day(date_from), _parse_day(date_to)
    return (_local_midnight_utc(start) if start else None,
            _local_midnight_utc(end + timedelta(days=1)) if end else None)


# ---------- serializers ----------

def violation_summary(v: Optional[Violation]) -> Optional[dict]:
    if v is None:
        return None
    return {
        "status": v.status,
        "resolved_by": {"id": v.resolved_by.id, "username": v.resolved_by.username} if v.resolved_by else None,
        "resolved_at": iso(v.resolved_at),
        "note": v.note or "",
    }


def scan_out(s: Scan) -> dict:
    return {
        "id": s.id,
        "created_at": iso(s.created_at),
        "worker": {"id": s.worker.id, "full_name": s.worker.full_name,
                   "employee_code": s.worker.employee_code or ""},
        "site": {"id": s.site.id, "name": s.site.name},
        "scanned_by": {"id": s.user.id, "username": s.user.username, "full_name": s.user.full_name or ""},
        "items": s.items(),
        "overall": s.overall,
        "has_snapshot": bool(s.snapshot_path),
        "violation": violation_summary(s.violation),
        # extras beyond the contract
        "confidence": (s.details or {}).get("confidence"),
        "snapshot_url": f"/api/scans/{s.id}/snapshot" if s.snapshot_path else None,
    }


SCAN_LOAD = (selectinload(Scan.worker), selectinload(Scan.site), selectinload(Scan.user),
             selectinload(Scan.violation).selectinload(Violation.resolved_by))


def _box(values) -> dict:
    x1, y1, x2, y2 = values
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def detection_message(analysis: dict, smoothed: dict, latency_ms: int) -> dict:
    """Build the contract's `detection` message from one frame's analysis and the smoothed state."""
    person = analysis.get("person")
    return {
        "type": "detection",
        "frame_width": analysis["frame_size"][0],
        "frame_height": analysis["frame_size"][1],
        "person": {**_box(person["box"]), "confidence": person["confidence"]} if person else None,
        # Gear worn by the worker in view. Label is the checklist item, or "goggles".
        "detections": [
            {"label": d["item"] or "goggles", **_box(d["box"]), "confidence": d["confidence"]}
            for d in analysis["detections"]
            if d["on_worker"] and not d["negative"] and (d["item"] or d["label"].lower() == "goggles")
        ],
        "items": smoothed["items"],
        "overall": smoothed["overall"],
        "stable": smoothed["stable"],
        "latency_ms": latency_ms,
    }


# ---------- filters ----------

def _filtered_scans(query, user: User, site_id=None, worker_id=None, result=None, date_from=None, date_to=None):
    scope = scoped_site_id(user)
    if scope is not None:
        query = query.where(Scan.site_id == scope)
    if site_id is not None:
        query = query.where(Scan.site_id == site_id)
    if worker_id is not None:
        query = query.where(Scan.worker_id == worker_id)
    if result:
        query = query.where(Scan.overall == result)
    start, end = _date_bounds(date_from, date_to)
    if start:
        query = query.where(Scan.created_at >= start)
    if end:
        query = query.where(Scan.created_at < end)
    return query


def _page(db: Session, query, limit: int, offset: int) -> dict:
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.options(*SCAN_LOAD).order_by(Scan.created_at.desc(), Scan.id.desc())
                      .limit(limit).offset(offset))
    return {"items": [scan_out(s) for s in rows], "total": total}


# ---------- live scan ----------

def _record_scan(db: Session, user: User, worker_id: int, site_id: int, live: detector.LiveScan) -> Scan:
    worker = db.get(Worker, worker_id)
    if not worker or not worker.is_active:
        raise ValueError("Worker not found or inactive")
    if worker.site_id != site_id:
        raise ValueError("That worker isn't assigned to this site")
    if user.role != "admin" and user.site_id != site_id:
        raise ValueError("You can only scan workers at your own site")
    smoothed = live.smoothed()
    if not live.has_person():
        raise ValueError("No worker in view. Point the camera at the worker first")
    if not smoothed["stable"]:
        raise ValueError("Result isn't stable yet. Hold the camera steady for a moment")

    analysis = live.last_analysis or {}
    scan = Scan(
        worker_id=worker.id, site_id=site_id, user_id=user.id, overall=smoothed["overall"],
        details={
            "confidence": smoothed["confidence"],
            "frames": smoothed["frames"],
            "person_confidence": (analysis.get("person") or {}).get("confidence"),
            "detections": analysis.get("detections", []),
        },
        **smoothed["items"],
    )
    db.add(scan)
    db.flush()

    now = utcnow()
    rel_path = Path(f"{now:%Y}") / f"{now:%m}" / f"scan_{scan.id}.jpg"
    (SNAPSHOT_DIR / rel_path).parent.mkdir(parents=True, exist_ok=True)
    (SNAPSHOT_DIR / rel_path).write_bytes(detector.annotate_snapshot(live.last_frame, analysis, smoothed["items"]))
    scan.snapshot_path = rel_path.as_posix()

    if scan.overall == "fail":
        db.add(Violation(scan_id=scan.id))
    db.commit()
    return db.scalar(select(Scan).options(*SCAN_LOAD).where(Scan.id == scan.id))


@router.websocket("/ws/scan")
async def scan_socket(websocket: WebSocket, token: Optional[str] = None):
    """
    Client -> server: {"type":"frame","image":"data:image/jpeg;base64,..."} (raw binary JPEG also accepted),
                      {"type":"record","worker_id":N,"site_id":N}, {"type":"reset"}
    Server -> client: {"type":"detection",...}, {"type":"recorded","scan":Scan}, {"type":"error","message":...}
    A bad token closes the socket with code 4401. Send the next frame only after the previous reply.
    """
    await websocket.accept()
    with SessionLocal() as db:
        user = user_from_token(token, db)
    if not user:
        await websocket.close(code=4401)
        return

    live = detector.LiveScan()
    await run_in_threadpool(detector.load_models)

    async def send_error(message: str):
        await websocket.send_json({"type": "error", "message": message})

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
                    live = detector.LiveScan()
                    continue
                if kind == "record":
                    try:
                        with SessionLocal() as db:
                            scan = await run_in_threadpool(
                                _record_scan, db, db.get(User, user.id),
                                int(payload.get("worker_id")), int(payload.get("site_id")), live)
                        live = detector.LiveScan()  # next worker starts fresh
                        await websocket.send_json({"type": "recorded", "scan": scan_out(scan)})
                    except (ValueError, TypeError) as exc:
                        await send_error(str(exc) if isinstance(exc, ValueError) and "invalid literal" not in str(exc)
                                         else "record needs numeric worker_id and site_id")
                    continue
                if kind != "frame":
                    await send_error(f"Unknown message type: {kind}")
                    continue
                try:
                    frame_bytes = base64.b64decode(str(payload.get("image", "")).split(",")[-1], validate=False)
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
                await websocket.send_json(detection_message(analysis, smoothed, latency_ms))
            except Exception as e:
                import traceback
                traceback.print_exc()
                await send_error(f"Internal Error: {str(e)}")
    except WebSocketDisconnect:
        pass


@router.post("/api/analyze")
async def analyze_image(image: UploadFile = File(...), _: User = Depends(get_current_user)):
    """Run PPE detection on one uploaded image (testing without a camera). Nothing is saved."""
    frame = detector.decode_jpeg(await image.read())
    if frame is None:
        raise HTTPException(422, "Could not decode image")
    start = time.perf_counter()
    analysis = await run_in_threadpool(detector.analyze_frame, frame)
    items = analysis["items"] or {item: "no_person" for item in PPE_ITEMS}
    single = {"items": items, "overall": detector.overall_status(analysis["items"]), "stable": False}
    return detection_message(analysis, single, round((time.perf_counter() - start) * 1000))


@router.get("/api/model")
async def model_details(_: User = Depends(get_current_user)):
    return await run_in_threadpool(detector.model_info)


# ---------- scans ----------

@router.get("/api/scans")
def list_scans(site_id: Optional[int] = None, worker_id: Optional[int] = None,
               result: Optional[str] = Query(default=None, pattern=RESULT_PATTERN),
               date_from: Optional[str] = None, date_to: Optional[str] = None,
               limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = _filtered_scans(select(Scan), user, site_id, worker_id, result, date_from, date_to)
    return _page(db, query, limit, offset)


def _csv_response(db: Session, user: User, site_id, worker_id, result, date_from, date_to) -> Response:
    query = _filtered_scans(select(Scan), user, site_id, worker_id, result, date_from, date_to)
    rows = db.scalars(query.options(*SCAN_LOAD).order_by(Scan.created_at.desc()))
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["scan_id", "time_utc", "time_local", "worker", "employee_code", "site", "scanned_by",
                     *PPE_ITEMS, "overall", "violation_status", "violation_note"])
    for s in rows:
        writer.writerow([s.id, iso(s.created_at), f"{to_local(s.created_at):%Y-%m-%d %H:%M:%S}",
                         s.worker.full_name, s.worker.employee_code or "", s.site.name, s.user.username,
                         *s.items().values(), s.overall,
                         s.violation.status if s.violation else "", (s.violation.note or "") if s.violation else ""])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="ppe_scans.csv"'})


@router.get("/api/reports/export.csv")
@router.get("/api/scans/export.csv")
def export_scans(site_id: Optional[int] = None, worker_id: Optional[int] = None,
                 result: Optional[str] = Query(default=None, pattern=RESULT_PATTERN),
                 date_from: Optional[str] = None, date_to: Optional[str] = None,
                 user: User = Depends(user_from_header_or_query), db: Session = Depends(get_db)):
    return _csv_response(db, user, site_id, worker_id, result, date_from, date_to)


def _get_scan(db: Session, user: User, scan_id: int) -> Scan:
    scan = db.scalar(select(Scan).options(*SCAN_LOAD).where(Scan.id == scan_id))
    if not scan:
        raise HTTPException(404, "Scan not found")
    ensure_site_access(user, scan.site_id)
    return scan


@router.get("/api/scans/{scan_id}")
def get_scan(scan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return scan_out(_get_scan(db, user, scan_id))


@router.get("/api/scans/{scan_id}/snapshot")
def get_snapshot(scan_id: int, user: User = Depends(user_from_header_or_query), db: Session = Depends(get_db)):
    scan = _get_scan(db, user, scan_id)
    if not scan.snapshot_path:
        raise HTTPException(404, "Snapshot not found")
    path = (SNAPSHOT_DIR / scan.snapshot_path).resolve()
    if not path.is_file() or SNAPSHOT_DIR.resolve() not in path.parents:
        raise HTTPException(404, "Snapshot not found")
    return FileResponse(path, media_type="image/jpeg")


# ---------- violations (a violation is a failed scan) ----------

class ResolveIn(BaseModel):
    note: str = ""


@router.get("/api/violations")
def list_violations(status: Optional[str] = Query(default=None, pattern="^(open|resolved)$"),
                    site_id: Optional[int] = None, worker_id: Optional[int] = None,
                    date_from: Optional[str] = None, date_to: Optional[str] = None,
                    limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = _filtered_scans(select(Scan).join(Scan.violation), user, site_id, worker_id, "fail",
                            date_from, date_to)
    if status:
        query = query.where(Violation.status == status)
    return _page(db, query, limit, offset)


def _violation_for(db: Session, user: User, scan_id: int) -> tuple:
    scan = _get_scan(db, user, scan_id)
    if scan.overall != "fail":
        raise HTTPException(404, "That scan passed, so it has no violation")
    if scan.violation is None:  # safety net for scans saved without one
        db.add(Violation(scan_id=scan.id))
        db.commit()
        scan = _get_scan(db, user, scan_id)
    return scan, scan.violation


@router.post("/api/violations/{scan_id}/resolve")
def resolve_violation(scan_id: int, body: ResolveIn, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    _, violation = _violation_for(db, user, scan_id)
    violation.status, violation.note = "resolved", body.note.strip()
    violation.resolved_by_id, violation.resolved_at = user.id, utcnow()
    db.commit()
    db.expire_all()
    return scan_out(_get_scan(db, user, scan_id))


@router.post("/api/violations/{scan_id}/reopen")
def reopen_violation(scan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _, violation = _violation_for(db, user, scan_id)
    violation.status, violation.resolved_by_id, violation.resolved_at = "open", None, None
    db.commit()
    db.expire_all()
    return scan_out(_get_scan(db, user, scan_id))


# ---------- reports ----------

def _rate(passed: int, total: int) -> float:
    return round(passed * 100 / total, 1) if total else 0.0


@router.get("/api/reports/summary")
def report_summary(site_id: Optional[int] = None, worker_id: Optional[int] = None,
                   date_from: Optional[str] = None, date_to: Optional[str] = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Totals and breakdowns for the filtered scans. Defaults to the last 30 days."""
    today = datetime.now(APP_TZ).date()
    end_day = _parse_day(date_to) or today
    start_day = _parse_day(date_from) or end_day - timedelta(days=29)
    if start_day > end_day:
        raise HTTPException(422, "date_from must be on or before date_to")

    query = _filtered_scans(select(Scan), user, site_id, worker_id, None,
                            start_day.isoformat(), end_day.isoformat())
    scans = list(db.scalars(query.options(selectinload(Scan.worker), selectinload(Scan.site))
                            .order_by(Scan.created_at)))

    by_day = {}
    day = start_day
    while day <= end_day:
        by_day[day.isoformat()] = {"date": day.isoformat(), "total": 0, "passed": 0, "failed": 0}
        day += timedelta(days=1)
    by_item = {item: {"pass": 0, "fail": 0, "not_visible": 0} for item in PPE_ITEMS}
    by_site, by_worker = {}, {}
    passed = 0

    for s in scans:
        ok = s.overall == "pass"
        passed += ok
        groups = [
            by_day.get(f"{to_local(s.created_at):%Y-%m-%d}"),
            by_site.setdefault(s.site_id, {"site_id": s.site_id, "site_name": s.site.name,
                                           "total": 0, "passed": 0, "failed": 0}),
            by_worker.setdefault(s.worker_id, {"worker_id": s.worker_id, "full_name": s.worker.full_name,
                                               "employee_code": s.worker.employee_code or "",
                                               "total": 0, "passed": 0, "failed": 0, "last_scan_at": None}),
        ]
        for group in groups:
            if group is not None:
                group["total"] += 1
                group["passed" if ok else "failed"] += 1
        by_worker[s.worker_id]["last_scan_at"] = iso(s.created_at)
        for item, status in s.items().items():
            by_item[item][status] += 1

    for group in (*by_site.values(), *by_worker.values()):
        group["compliance_rate"] = _rate(group["passed"], group["total"])

    open_query = _filtered_scans(select(Scan.id).join(Scan.violation).where(Violation.status == "open"),
                                 user, site_id, worker_id)
    return {
        "total_scans": len(scans),
        "passed": passed,
        "failed": len(scans) - passed,
        "compliance_rate": _rate(passed, len(scans)),
        "open_violations": db.scalar(select(func.count()).select_from(open_query.subquery())),
        "by_item": by_item,
        "by_day": list(by_day.values()),
        "by_site": sorted(by_site.values(), key=lambda g: g["site_name"]),
        "by_worker": sorted(by_worker.values(), key=lambda g: (g["compliance_rate"], g["full_name"])),
        # extras beyond the contract
        "date_from": start_day.isoformat(),
        "date_to": end_day.isoformat(),
        "workers_scanned": len(by_worker),
    }
