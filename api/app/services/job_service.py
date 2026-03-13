from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.app.db.models import Job, JobStatus, OcrStatus, Violation
from api.app.schemas.jobs import JobResultsResponse, JobStatusResponse, ViolationResponse
from api.app.services.queue import JobQueue
from api.app.services.storage import LocalStorage
from shared.contracts import JobPayload


class JobService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = LocalStorage()
        self.queue = JobQueue()
        self.max_upload_bytes = self.storage.settings.max_upload_mb * 1024 * 1024

    def create_job(self, file: UploadFile) -> Job:
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

        ext = Path(file.filename).suffix or ".mp4"
        safe_name = f"{uuid.uuid4()}{ext}"
        content = file.file.read()
        if len(content) > self.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max allowed is {self.storage.settings.max_upload_mb} MB.",
            )

        input_video_uri = self.storage.save_upload(safe_name, content)

        job = Job(input_video_uri=input_video_uri, status=JobStatus.QUEUED, progress_pct=0)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        try:
            self.queue.enqueue(JobPayload(job_id=job.id, input_video_uri=job.input_video_uri))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Queue unavailable: {exc}",
            ) from exc
        return job

    def get_job(self, job_id: str) -> Job:
        job = self.db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job

    def get_status(self, job_id: str) -> JobStatusResponse:
        job = self.get_job(job_id)
        return JobStatusResponse(
            job_id=job.id,
            status=job.status,
            progress_pct=job.progress_pct,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error_message=job.error_message,
        )

    def get_results(
        self,
        job_id: str,
        ocr_status: OcrStatus | None = None,
        has_plate: bool | None = None,
        min_no_helmet: int = 0,
    ) -> JobResultsResponse:
        job = self.get_job(job_id)

        violations_query = self.db.query(Violation).filter(Violation.job_id == job.id)
        if ocr_status is not None:
            violations_query = violations_query.filter(Violation.ocr_status == ocr_status)
        if has_plate is True:
            violations_query = violations_query.filter(Violation.plate_text.is_not(None))
        elif has_plate is False:
            violations_query = violations_query.filter(Violation.plate_text.is_(None))
        if min_no_helmet > 0:
            violations_query = violations_query.filter(Violation.no_helmet_count >= min_no_helmet)

        violation_rows = violations_query.order_by(Violation.timestamp_sec.asc()).all()
        violations = [
            ViolationResponse(
                id=v.id,
                track_id=v.track_id,
                timestamp_sec=v.timestamp_sec,
                rider_count=v.rider_count,
                no_helmet_count=v.no_helmet_count,
                plate_text=v.plate_text,
                plate_confidence=v.plate_confidence,
                ocr_status=v.ocr_status,
                evidence_image_uri=v.evidence_image_uri,
            )
            for v in violation_rows
        ]

        return JobResultsResponse(
            job_id=job.id,
            status=job.status,
            output_video_uri=job.output_video_uri,
            report_uri=job.report_uri,
            total_violations=len(violations),
            violations=violations,
        )

    def get_report_json(self, job: Job) -> dict:
        if not job.report_uri:
            return {}
        path = Path(job.report_uri)
        if not path.exists():
            return {}
        return json.loads(path.read_text())

    def resolve_job_artifact(self, job_id: str, artifact_type: str) -> Path:
        job = self.get_job(job_id)
        if artifact_type == "report":
            uri = job.report_uri
        elif artifact_type == "video":
            uri = job.output_video_uri
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown artifact type")

        if not uri:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not ready")
        return self._validate_local_path(uri)

    def resolve_evidence_artifact(self, job_id: str, violation_id: str) -> Path:
        violation = (
            self.db.query(Violation)
            .filter(Violation.id == violation_id, Violation.job_id == job_id)
            .one_or_none()
        )
        if not violation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")
        return self._validate_local_path(violation.evidence_image_uri)

    def _validate_local_path(self, uri: str) -> Path:
        path = Path(uri)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file missing")
        root = self.storage.settings.data_root.resolve()
        resolved = path.resolve()
        if root not in resolved.parents and resolved != root:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Artifact path not allowed")
        return resolved
