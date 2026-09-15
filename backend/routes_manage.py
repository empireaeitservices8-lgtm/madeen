"""Login, sites, workers and user accounts. Shapes follow API_CONTRACT.md in the project root."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import (create_token, get_current_user, hash_password, require_admin, scoped_site_id,
                  verify_password)
from db import Site, User, Worker, get_db

router = APIRouter(prefix="/api")


# ---------- serializers ----------

def iso(dt) -> Optional[str]:
    return dt.replace(microsecond=0).isoformat() + "Z" if dt else None


def site_out(s: Site) -> dict:
    return {"id": s.id, "name": s.name, "location": s.location or "", "is_active": s.is_active,
            "created_at": iso(s.created_at)}


def user_out(u: User) -> dict:
    return {
        "id": u.id, "username": u.username, "full_name": u.full_name or "", "role": u.role,
        "site_id": u.site_id, "site_name": u.site.name if u.site else None,
        "is_active": u.is_active, "created_at": iso(u.created_at),
    }


def worker_out(w: Worker) -> dict:
    return {
        "id": w.id, "employee_code": w.employee_code or "", "full_name": w.full_name, "trade": w.trade or "",
        "site_id": w.site_id, "site_name": w.site.name if w.site else None,
        "is_active": w.is_active, "created_at": iso(w.created_at),
    }


def commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, message)


# ---------- auth ----------

class LoginIn(BaseModel):
    username: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.username) == body.username.strip().lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return {"access_token": create_token(user), "token_type": "bearer", "user": user_out(user)}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/auth/change-password")
def change_password(body: ChangePasswordIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


# ---------- sites ----------

class SiteIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    location: Optional[str] = None


class SitePatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    location: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/sites")
def list_sites(active: Optional[bool] = None, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    query = select(Site).order_by(Site.name)
    if scoped_site_id(user) is not None:
        query = query.where(Site.id == user.site_id)
    if active is not None:
        query = query.where(Site.is_active == active)
    return [site_out(s) for s in db.scalars(query)]


@router.post("/sites", status_code=201)
def create_site(body: SiteIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    site = Site(name=body.name.strip(), location=_blank_to_none(body.location))
    db.add(site)
    commit_or_conflict(db, "A site with that name already exists")
    return site_out(site)


@router.patch("/sites/{site_id}")
def update_site(site_id: int, body: SitePatch, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    site = db.get(Site, site_id) or _not_found("Site")
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "location" in changes:
        changes["location"] = _blank_to_none(changes["location"])
    for field, value in changes.items():
        setattr(site, field, value)
    commit_or_conflict(db, "A site with that name already exists")
    return site_out(site)


@router.delete("/sites/{site_id}")
def delete_site(site_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Soft delete: the site is hidden from active lists but its scans stay in reports."""
    site = db.get(Site, site_id) or _not_found("Site")
    site.is_active = False
    db.commit()
    return site_out(site)


# ---------- workers ----------

class WorkerIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    employee_code: Optional[str] = None
    trade: Optional[str] = None
    site_id: int


class WorkerPatch(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    employee_code: Optional[str] = None
    trade: Optional[str] = None
    site_id: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/workers")
def list_workers(site_id: Optional[int] = None, q: Optional[str] = None, active: Optional[bool] = True,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Worker).order_by(Worker.full_name)
    scope = scoped_site_id(user)
    if scope is not None:
        query = query.where(Worker.site_id == scope)
    if site_id is not None:
        query = query.where(Worker.site_id == site_id)
    if active is not None:
        query = query.where(Worker.is_active == active)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Worker.full_name.ilike(like), Worker.employee_code.ilike(like)))
    return [worker_out(w) for w in db.scalars(query)]


@router.post("/workers", status_code=201)
def create_worker(body: WorkerIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    db.get(Site, body.site_id) or _not_found("Site")
    worker = Worker(full_name=body.full_name.strip(), employee_code=_blank_to_none(body.employee_code),
                    trade=_blank_to_none(body.trade), site_id=body.site_id)
    db.add(worker)
    commit_or_conflict(db, "A worker with that employee code already exists")
    return worker_out(worker)


@router.patch("/workers/{worker_id}")
def update_worker(worker_id: int, body: WorkerPatch, _: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    worker = db.get(Worker, worker_id) or _not_found("Worker")
    changes = body.model_dump(exclude_unset=True)
    if "site_id" in changes:
        db.get(Site, changes["site_id"]) or _not_found("Site")
    for field in ("employee_code", "trade"):
        if field in changes:
            changes[field] = _blank_to_none(changes[field])
    for field, value in changes.items():
        setattr(worker, field, value)
    commit_or_conflict(db, "A worker with that employee code already exists")
    return worker_out(worker)


@router.delete("/workers/{worker_id}")
def delete_worker(worker_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Soft delete: keeps the worker's scan history."""
    worker = db.get(Worker, worker_id) or _not_found("Worker")
    worker.is_active = False
    db.commit()
    return worker_out(worker)


# ---------- users (admin only) ----------

class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    role: str = Field(pattern="^(admin|supervisor)$")
    site_id: Optional[int] = None


class UserPatch(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = Field(default=None, pattern="^(admin|supervisor)$")
    site_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8)  # admin reset


@router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.username))]


@router.post("/users", status_code=201)
def create_user(body: UserIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    _check_supervisor_site(body.role, body.site_id, db)
    new_user = User(username=body.username.strip(), password_hash=hash_password(body.password),
                    full_name=body.full_name, role=body.role,
                    site_id=body.site_id if body.role == "supervisor" else None)
    db.add(new_user)
    commit_or_conflict(db, "That username is taken")
    return user_out(new_user)


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    target = db.get(User, user_id) or _not_found("User")
    changes = body.model_dump(exclude_unset=True)
    if target.id == admin.id and (changes.get("role") == "supervisor" or changes.get("is_active") is False):
        raise HTTPException(400, "You can't demote or deactivate your own account")
    role = changes.get("role", target.role)
    site_id = changes.get("site_id", target.site_id)
    _check_supervisor_site(role, site_id, db)
    if "password" in changes:
        target.password_hash = hash_password(changes.pop("password"))
    for field, value in changes.items():
        setattr(target, field, value)
    if target.role == "admin":
        target.site_id = None
    db.commit()
    return user_out(target)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Soft delete: the account can no longer log in; its scans keep their 'scanned by' name."""
    target = db.get(User, user_id) or _not_found("User")
    if target.id == admin.id:
        raise HTTPException(400, "You can't delete your own account")
    target.is_active = False
    db.commit()
    return user_out(target)


# ---------- helpers ----------

def _not_found(what: str):
    raise HTTPException(404, f"{what} not found")


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    return value.strip() or None if value is not None else None


def _check_supervisor_site(role: str, site_id: Optional[int], db: Session) -> None:
    if role == "supervisor":
        if site_id is None:
            raise HTTPException(400, "Supervisors must be assigned to a site")
        db.get(Site, site_id) or _not_found("Site")
