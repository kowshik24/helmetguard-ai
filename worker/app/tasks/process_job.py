from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from api.app.db.models import Job, JobStatus, Violation
from worker.app.pipeline.analyzer import VideoAnalyzer

logger = logging.getLogger(__name__)


class JobProcessor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.analyzer = VideoAnalyzer()

    def run(self, job_id: str, input_video_uri: str) -> None:
        job = self.db.get(Job, job_id)
        if not job:
            logger.error("Job not found: %s", job_id)
            return

        try:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.utcnow()
            job.progress_pct = 5
            self.db.commit()

            last_progress = 5

            def on_progress(progress: int) -> None:
                nonlocal last_progress
                progress = max(0, min(100, progress))
                if progress <= last_progress:
                    return
                last_progress = progress
                job.progress_pct = progress
                self.db.commit()

            output_video_uri, report_uri, violations = self.analyzer.analyze(
                job_id, input_video_uri, progress_callback=on_progress
            )

            for record in violations:
                violation = Violation(
                    job_id=job.id,
                    track_id=record.track_id,
                    timestamp_sec=record.timestamp_sec,
                    rider_count=record.rider_count,
                    no_helmet_count=record.no_helmet_count,
                    plate_text=record.plate_text,
                    plate_confidence=record.plate_confidence,
                    ocr_status=record.ocr_status,
                    evidence_image_uri=record.evidence_image_uri,
                )
                self.db.add(violation)

            job.output_video_uri = output_video_uri
            job.report_uri = report_uri
            job.progress_pct = 100
            job.status = JobStatus.COMPLETED
            job.finished_at = datetime.utcnow()
            job.error_message = None
            self.db.commit()

            logger.info("Job %s completed", job_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job %s failed", job_id)
            job.status = JobStatus.FAILED
            job.progress_pct = 100
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
            self.db.commit()
