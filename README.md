# HelmetGuard AI

Upload-first helmet violation analysis platform.

## What is implemented
- FastAPI backend with job lifecycle endpoints
- Redis-backed async queue
- Worker service with baseline video analysis pipeline
- SQLite-backed persistence (configurable DB URL)
- Local filesystem artifact storage
- Docker Compose for local multi-service run

## API Endpoints
- `GET /api/v1/health`
- `POST /api/v1/jobs` (multipart `file` upload)
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/results?ocr_status=&has_plate=&min_no_helmet=`
- `GET /api/v1/jobs/{job_id}/artifacts/{report|video}`
- `GET /api/v1/jobs/{job_id}/violations/{violation_id}/evidence`
- `GET /jobs/{job_id}` (dedicated results page with thumbnails)

## Quick Start (Local)
1. `cp .env.example .env`
2. `./scripts/bootstrap.sh`
3. Start Redis (example): `docker run --rm -p 6379:6379 redis:7-alpine`
4. Install dependencies: `pip install -e .`
   - For full CV stack: `pip install -e .[vision]`
5. Start API: `make run-api`
6. Start worker: `make run-worker`

## Quick Start (Docker Compose)
1. `cp .env.example .env`
2. `./scripts/bootstrap.sh`
3. `docker compose -f infra/compose/docker-compose.yml up --build`

## Notes on Current Pipeline
- Worker now runs a real modular pipeline with detector/tracker/association/OCR hooks.
- Default detector is pretrained `yolov8n.pt` (configurable via `YOLO_MODEL_PATH`).
- YOLO native tracking is enabled by default using `model.track(..., tracker=bytetrack.yaml)`.
- Temporal rider-to-bike association uses memory from previous frames.
- Violation confidence is smoothed with EMA and minimum stable-frame gating.
- Plate text selection uses multi-frame memory and best-confidence fusion per bike track.
- Worker updates job progress during frame processing (not only at start/end).
- If OpenCV/model/OCR deps are missing, it gracefully falls back to placeholder mode.
- Configure model/tracker via `YOLO_MODEL_PATH`, `YOLO_USE_BUILTIN_TRACKER`, and `YOLO_TRACKER_CONFIG` in `.env`.

## Benchmarking
- Runtime summary only:
  - `python scripts/benchmark.py --pred data/reports/<job_id>/report.json`
- With ground truth:
  - `python scripts/benchmark.py --pred data/reports/<job_id>/report.json --gt path/to/ground_truth.json`

## Suggested Next Implementation Steps
1. Integrate YOLO detection + tracking in worker pipeline.
2. Replace placeholder evidence with frame crops.
3. Add OCR module and multi-frame plate fusion.
4. Add frontend upload/status/results pages.
