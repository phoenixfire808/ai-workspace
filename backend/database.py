from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env", override=False)
DEFAULT_DB_PATH = BACKEND_DIR / "workspace.db"
_explicit_database_url = (os.getenv("WORKSPACE_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
if _explicit_database_url:
    DATABASE_URL = _explicit_database_url
    DB_PATH: Path | None = None
else:
    DB_PATH = Path(os.getenv("WORKSPACE_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite:") else {},
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


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    approval_policy: Mapped[str] = mapped_column(String(32), default="per_action")
    graph_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    runtime_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    input_text: Mapped[str] = mapped_column(Text, default="")
    final_output: Mapped[str] = mapped_column(Text, default="")
    error_detail: Mapped[str] = mapped_column(Text, default="")
    retain_context: Mapped[bool] = mapped_column(Boolean, default=True)
    max_parallel: Mapped[int] = mapped_column(Integer, default=4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class RunStep(Base):
    __tablename__ = "run_steps"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(120), index=True)
    node_type: Mapped[str] = mapped_column(String(32))
    branch_key: Mapped[str] = mapped_column(String(240), default="root")
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output: Mapped[str] = mapped_column(Text, default="")
    failure_class: Mapped[str] = mapped_column(String(120), default="")
    error_detail: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class RunEvent(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("run_steps.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(80))
    subject_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    impact_preview: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    approve_identical: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DelegateChild(Base):
    __tablename__ = "delegate_children"
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    parent_run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    parent_step_id: Mapped[str] = mapped_column(ForeignKey("run_steps.id"), index=True)
    subtask_id: Mapped[str] = mapped_column(String(96), index=True)
    worker_target: Mapped[str] = mapped_column(String(160), default="")
    assignment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), index=True)
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receipt: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    output: Mapped[str] = mapped_column(Text, default="")
    failure_class: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ModelEndpointProfile(Base):
    __tablename__ = "model_endpoint_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    provider_kind: Mapped[str] = mapped_column(String(64))
    base_url: Mapped[str] = mapped_column(String(1000))
    credential_alias: Mapped[str] = mapped_column(String(160), default="")
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    managed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class HardwareProfile(Base):
    __tablename__ = "hardware_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="auto")
    device_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class WorkspaceModelSetting(Base):
    __tablename__ = "workspace_model_settings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="global")
    provider: Mapped[str] = mapped_column(String(32), default="ollama")
    model: Mapped[str] = mapped_column(String(500))
    hardware_profile_id: Mapped[str] = mapped_column(String(64), default="auto")
    fallback_policy: Mapped[str] = mapped_column(String(32), default="explicit_only")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class FeedbackItem(Base):
    __tablename__ = "feedback_items"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[str] = mapped_column(Text, default="")
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    context_receipt: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    github_issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    github_url: Mapped[str] = mapped_column(String(1000), default="")
    failure_class: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
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
