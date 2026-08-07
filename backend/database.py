from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from sqlalchemy import DateTime, JSON, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env", override=False)
DEFAULT_DB_PATH = BACKEND_DIR / "workspace.db"
DB_PATH = Path(os.getenv("WORKSPACE_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    canvas_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class TaskItem(Base):
    __tablename__ = "task_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), default="todo")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Any]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def list_projects(db: Any) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.updated_at.desc())).all())


def upsert_task(
    db: Any,
    *,
    task_id: str,
    project_id: str | None,
    title: str,
    status: str,
    notes: str,
) -> TaskItem:
    task = db.get(TaskItem, task_id)
    if task is None:
        task = TaskItem(id=task_id, project_id=project_id)
        db.add(task)
    task.project_id = project_id
    task.title = title
    task.status = status
    task.notes = notes
    task.updated_at = utc_now()
    db.commit()
    db.refresh(task)
    return task
