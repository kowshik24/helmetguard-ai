from datetime import datetime

from pydantic import BaseModel, Field

from api.app.db.models import JobStatus, OcrStatus


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress_pct: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None


class ViolationResponse(BaseModel):
    id: str
    track_id: str
    timestamp_sec: float
    rider_count: int
    no_helmet_count: int
    plate_text: str | None
    plate_confidence: float | None
    ocr_status: OcrStatus
    evidence_image_uri: str


class JobResultsResponse(BaseModel):
    job_id: str
    status: JobStatus
    output_video_uri: str | None
    report_uri: str | None
    total_violations: int = Field(default=0)
    violations: list[ViolationResponse] = Field(default_factory=list)
