from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.app.db.models import OcrStatus
from api.app.db.session import get_db
from api.app.schemas.jobs import JobCreateResponse, JobResultsResponse, JobStatusResponse
from api.app.services.job_service import JobService

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse)
def create_job(file: UploadFile = File(...), db: Session = Depends(get_db)) -> JobCreateResponse:
    service = JobService(db)
    job = service.create_job(file)
    return JobCreateResponse(job_id=job.id, status=job.status)


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    service = JobService(db)
    return service.get_status(job_id)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(
    job_id: str,
    ocr_status: OcrStatus | None = Query(default=None),
    has_plate: bool | None = Query(default=None),
    min_no_helmet: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> JobResultsResponse:
    service = JobService(db)
    return service.get_results(
        job_id=job_id,
        ocr_status=ocr_status,
        has_plate=has_plate,
        min_no_helmet=min_no_helmet,
    )


@router.get("/{job_id}/artifacts/{artifact_type}")
def download_job_artifact(
    job_id: str,
    artifact_type: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    service = JobService(db)
    path = service.resolve_job_artifact(job_id, artifact_type)
    return FileResponse(path=path, filename=path.name)


@router.get("/{job_id}/violations/{violation_id}/evidence")
def download_violation_evidence(
    job_id: str,
    violation_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    service = JobService(db)
    path = service.resolve_evidence_artifact(job_id, violation_id)
    return FileResponse(path=path, filename=path.name)
