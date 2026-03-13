from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OcrStatus(str, enum.Enum):
    SUCCESS = "success"
    NOT_VISIBLE = "not_visible"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED, index=True)

    input_video_uri: Mapped[str] = mapped_column(Text)
    output_video_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_uri: Mapped[str | None] = mapped_column(Text, nullable=True)

    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    violations: Mapped[list[Violation]] = relationship(back_populates="job", cascade="all, delete-orphan")


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)

    track_id: Mapped[str] = mapped_column(String(64))
    timestamp_sec: Mapped[float] = mapped_column(Float)
    rider_count: Mapped[int] = mapped_column(Integer)
    no_helmet_count: Mapped[int] = mapped_column(Integer)

    plate_text: Mapped[str | None] = mapped_column(String(32), nullable=True)
    plate_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_status: Mapped[OcrStatus] = mapped_column(Enum(OcrStatus), default=OcrStatus.NOT_VISIBLE)

    evidence_image_uri: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped[Job] = relationship(back_populates="violations")
