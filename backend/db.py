"""Database models and session handling (SQLAlchemy 2.0, SQLite by default)."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from config import DATABASE_URL

PPE_ITEMS = ["helmet", "vest", "gloves", "boots", "mask"]

VEHICLE_ITEMS = ["lights", "tires", "mirrors", "windshield", "fire_extinguisher", "beacon", "reverse_alarm", "body_condition"]

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    location: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class User(Base):
    """Someone who logs in: an admin (everything) or a supervisor (scans and data for one site)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    full_name: Mapped[Optional[str]] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(16), default="supervisor")  # admin | supervisor
    site_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sites.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    site: Mapped[Optional[Site]] = relationship()


class Worker(Base):
    """A person being scanned. Workers don't log in."""

    __tablename__ = "workers"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    employee_code: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    trade: Mapped[Optional[str]] = mapped_column(String(80))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    site: Mapped[Site] = relationship()


class Scan(Base):
    """One recorded PPE check. Item statuses are pass | fail | not_visible."""

    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    helmet: Mapped[str] = mapped_column(String(12))
    vest: Mapped[str] = mapped_column(String(12))
    gloves: Mapped[str] = mapped_column(String(12))
    boots: Mapped[str] = mapped_column(String(12))
    mask: Mapped[str] = mapped_column(String(12))
    # pass only if all 5 items pass; anything else (fail or not_visible) is fail
    overall: Mapped[str] = mapped_column(String(12), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)  # confidences, frames used, etc.
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(255))

    worker: Mapped[Worker] = relationship()
    site: Mapped[Site] = relationship()
    user: Mapped[User] = relationship()
    violation: Mapped[Optional["Violation"]] = relationship(back_populates="scan", uselist=False)

    def items(self) -> dict:
        return {item: getattr(self, item) for item in PPE_ITEMS}


class Violation(Base):
    """Created automatically for every failed scan, so admins can follow up and resolve it."""

    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(primary_key=True)
    scan_id: Mapped[int] = mapped_column(ForeignKey("scans.id"), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="open", index=True)  # open | resolved
    note: Mapped[Optional[str]] = mapped_column(String(1000))
    resolved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    scan: Mapped[Scan] = relationship(back_populates="violation")
    resolved_by: Mapped[Optional[User]] = relationship()


class VehicleScan(Base):
    """One recorded vehicle inspection. Items are pass | fail | not_visible."""

    __tablename__ = "vehicle_scans"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_type: Mapped[str] = mapped_column(String(80), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    # one column per checklist item
    lights: Mapped[str] = mapped_column(String(12))
    tires: Mapped[str] = mapped_column(String(12))
    mirrors: Mapped[str] = mapped_column(String(12))
    windshield: Mapped[str] = mapped_column(String(12))
    fire_extinguisher: Mapped[str] = mapped_column(String(12))
    beacon: Mapped[str] = mapped_column(String(12))
    reverse_alarm: Mapped[str] = mapped_column(String(12))
    body_condition: Mapped[str] = mapped_column(String(12))

    overall: Mapped[str] = mapped_column(String(12), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_path: Mapped[Optional[str]] = mapped_column(String(255))

    site: Mapped[Site] = relationship()
    user: Mapped[User] = relationship()

    def items(self) -> dict:
        return {item: getattr(self, item) for item in VEHICLE_ITEMS}


class Question(Base):
    """A multiple choice question for the safety knowledge test."""

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(500))
    option_a: Mapped[str] = mapped_column(String(200))
    option_b: Mapped[str] = mapped_column(String(200))
    option_c: Mapped[str] = mapped_column(String(200))
    option_d: Mapped[str] = mapped_column(String(200))
    correct_answer: Mapped[str] = mapped_column(String(1))  # A, B, C, or D


class TestAttempt(Base):
    """A record of a worker taking the safety test."""

    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    
    score: Mapped[int] = mapped_column()  # e.g., 17
    total: Mapped[int] = mapped_column(default=50)
    passed: Mapped[bool] = mapped_column()

    details: Mapped[dict] = mapped_column(JSON, default=dict)  # The specific questions and chosen answers

    worker: Mapped[Worker] = relationship()
    site: Mapped[Site] = relationship()
    user: Mapped[User] = relationship()


def init_db() -> None:
    Base.metadata.create_all(engine)
    if DATABASE_URL.startswith("sqlite"):
        # Lightweight migration for databases created before sites.is_active existed.
        with engine.begin() as conn:
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sites)")}
            if "is_active" not in columns:
                conn.exec_driver_sql("ALTER TABLE sites ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
