from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
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
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> FileResponse:
    service = JobService(db)
    path = service.resolve_job_artifact(job_id, artifact_type)
    media_type = "video/mp4" if path.suffix.lower() == ".mp4" else None
    if download:
        return FileResponse(path=path, filename=path.name, media_type=media_type)
    return StreamingResponse(
        iter([path.read_bytes()]),
        media_type=media_type or "application/octet-stream",
        headers={
            "Content-Disposition": "inline",
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/{job_id}/violations/{violation_id}/evidence")
def download_violation_evidence(
    job_id: str,
    violation_id: str,
    download: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> FileResponse:
    service = JobService(db)
    path = service.resolve_evidence_artifact(job_id, violation_id)
    media_type = _guess_media_type(path)
    if download:
        return FileResponse(path=path, filename=path.name, media_type=media_type)
    return StreamingResponse(
        iter([path.read_bytes()]),
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": "inline"},
    )


def _guess_media_type(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".svg":
        return "image/svg+xml"
    if ext == ".mp4":
        return "video/mp4"
    return None
