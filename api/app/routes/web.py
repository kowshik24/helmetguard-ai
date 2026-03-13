from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    path = Path(__file__).resolve().parents[1] / "templates" / "index.html"
    return path.read_text(encoding="utf-8")


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_results_page(job_id: str) -> str:
    _ = job_id
    path = Path(__file__).resolve().parents[1] / "templates" / "results.html"
    return path.read_text(encoding="utf-8")
