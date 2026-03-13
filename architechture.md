# HelmetGuard AI - Full Project Architecture (Upload-First MVP)

## 1) Goals and Constraints

### Primary goal
Build a web application where users upload traffic videos and receive helmet-violation analysis results:
- violating rider/passenger detections
- plate text when readable
- evidence snapshots and clips
- processed annotated video

### Current constraints
- No live camera integration initially
- No private/local camera dataset initially
- Must support iterative model improvement from uploaded videos

## 2) High-Level Architecture

```text
[Web UI]
   |
   v
[FastAPI API Gateway]
   |                         +-----------------------------+
   | create job              | Metadata DB (PostgreSQL)   |
   +-----------------------> | jobs, violations, outputs   |
   |                         +-----------------------------+
   |
   | enqueue
   v
[Redis Queue] ---> [Inference Worker(s)] ---> [Model Runtime (YOLO + OCR + OpenCV)]
                           |                         |
                           | writes artifacts        |
                           v                         v
                     [Object Storage]          [Model Registry/Weights]
                     (videos/images/json)
```

## 3) Core Components

### 3.1 Frontend (Web UI)
- Upload video file
- Track job status (`queued`, `processing`, `completed`, `failed`)
- View violations timeline
- Preview evidence snapshots
- Download annotated video and JSON report

Suggested stack:
- React + Vite + Tailwind (or plain server-rendered pages for simpler MVP)

### 3.2 API Layer (FastAPI)
- Handles authentication (if enabled), uploads, job lifecycle, results fetch
- Persists metadata in PostgreSQL
- Stores large files in object storage (MinIO/S3)
- Enqueues async processing jobs in Redis-backed worker queue

### 3.3 Async Processing
- Worker service consumes jobs and runs full CV pipeline
- Parallel workers for throughput
- Retry policy for transient failures
- Idempotent processing using `job_id`

Worker framework options:
- `Celery` (mature, scalable)
- `RQ` or `Dramatiq` (simpler)

### 3.4 Vision/ML Runtime
Pipeline stages per video:
1. Decode frames (sample strategy configurable)
2. Detect objects: `motorcycle`, `person`, `helmet`, `license_plate`
3. Track objects across frames (ByteTrack/BoT-SORT)
4. Associate riders/passengers with each motorcycle
5. Infer helmet compliance per associated person
6. For violations, detect/crop plate and run OCR
7. Multi-frame fusion: select best plate/evidence frame
8. Write outputs (JSON + snapshots + annotated video)

### 3.5 Storage
- Object storage buckets:
  - `raw-videos/`
  - `processed-videos/`
  - `evidence-images/`
  - `reports/`
- PostgreSQL stores metadata, state, and queryable results

### 3.6 Observability
- Structured logs (JSON)
- Metrics:
  - job duration
  - queue depth
  - fail rate
  - FPS throughput
  - OCR success rate
- Error tracking (Sentry optional)

## 4) Detailed Data Flow

1. User uploads video via `/api/v1/jobs`.
2. API stores file in object storage and inserts `job` row in DB.
3. API enqueues `{job_id, video_uri, config}` to Redis queue.
4. Worker picks job and marks status `processing`.
5. Worker executes pipeline and periodically updates progress.
6. Worker stores artifacts:
   - annotated video
   - violation evidence images
   - report JSON
7. Worker writes `violations` rows and marks job `completed`.
8. UI fetches summary + assets URLs and renders results page.

## 5) Service Boundaries

### API Service
Responsibilities:
- request validation
- auth/rate limiting
- upload orchestration
- status/result retrieval

Does not do heavy inference in request thread.

### Worker Service
Responsibilities:
- frame processing/inference
- business rules and evidence selection
- OCR and post-processing

Does not expose public HTTP endpoints.

## 6) API Contract (MVP)

### `POST /api/v1/jobs`
Create analysis job with video upload.

Response:
```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### `GET /api/v1/jobs/{job_id}`
Returns job status and progress.

### `GET /api/v1/jobs/{job_id}/results`
Returns:
- summary counts
- per-violation records
- URLs for evidence and annotated video

### `GET /api/v1/health`
Service health check.

## 7) Data Model (PostgreSQL)

### `jobs`
- `id` (UUID, PK)
- `status` (`queued|processing|completed|failed`)
- `input_video_uri`
- `output_video_uri` (nullable)
- `report_uri` (nullable)
- `progress_pct`
- `error_message` (nullable)
- `created_at`, `started_at`, `finished_at`

### `violations`
- `id` (UUID, PK)
- `job_id` (FK -> jobs)
- `track_id`
- `timestamp_sec`
- `rider_count`
- `no_helmet_count`
- `plate_text` (nullable)
- `plate_confidence` (nullable)
- `ocr_status` (`success|not_visible|failed`)
- `evidence_image_uri`
- `created_at`

### `job_events` (optional)
- timeline of state/progress updates for debugging/audit

## 8) Model Strategy

## 8.1 Initial model sources (no local data yet)
- Start from public pretrained detector
- Fine-tune on public helmet/plate datasets

## 8.2 Progressive improvement loop
1. Sample frames from uploaded videos (with policy/consent).
2. Annotate hard cases in CVAT.
3. Retrain model versions.
4. Register version and deploy to worker.
5. Track quality metrics per model version.

## 8.3 Versioning
- Keep model artifacts versioned (`model_name:version`)
- Store active model version in config table/env
- Include `model_version` in each job result for traceability

## 9) Business Rules

- Violation condition:
  - one motorcycle track
  - associated rider/passenger(s)
  - any required person without helmet
- Dedup:
  - one violation record per bike track in configurable cooldown window
- OCR fallback:
  - if no valid plate after N frames, save evidence with `ocr_status=not_visible|failed`

## 10) Non-Functional Requirements

### Performance
- Target MVP: process at >= 5 FPS/video on 1 GPU worker (depends on resolution/model)
- Max upload size configurable (for example 500 MB)
- Timeout and retry limits per job

### Reliability
- At-least-once job execution with idempotent writes
- Graceful recovery after worker restart

### Security and Privacy
- File type and size validation
- Malware scanning optional for uploaded files
- Signed URLs for private artifact access
- Retention policy:
  - raw uploads TTL
  - evidence and reports retention period
- PII handling and legal compliance per region

## 11) Deployment Architecture

### Environment split
- `dev`: local docker-compose
- `staging`: production-like test
- `prod`: scaled deployment

### Suggested deployment units
- `api` container (FastAPI + Uvicorn/Gunicorn)
- `worker` container (GPU-enabled if available)
- `redis` container
- `postgres` container
- `minio` (or managed S3)
- optional `nginx` ingress/reverse proxy

### Horizontal scaling
- Scale API independently from workers
- Increase worker replicas with queue-based load balancing

## 12) Configuration Management

Use environment variables for:
- DB URL
- Redis URL
- Object storage credentials
- Active model versions
- inference thresholds (confidence, IoU, cooldown)
- upload limits and retention days

## 13) Testing Strategy

### Unit tests
- association logic
- violation decision rules
- OCR result validation/parsing

### Integration tests
- upload -> queue -> process -> result lifecycle
- failed job retry and status transitions

### Evaluation tests
- offline benchmark set for:
  - helmet violation precision/recall
  - plate read accuracy
  - false positives per minute

## 14) Phased Implementation Plan

### Phase 1: Upload + Offline Violation Detection
- upload/status/results APIs
- detector + tracker + helmet rule
- evidence images + report JSON

### Phase 2: Plate OCR and Better Evidence
- plate detection + OCR
- multi-frame best-plate selection
- annotated output video

### Phase 3: Production Hardening
- auth, rate limits, retention policies
- observability dashboards
- model version rollout strategy

### Phase 4: Optional Live Camera Extension
- RTSP ingest service
- stream chunking and near-real-time alerts
- same core worker pipeline reused

## 15) Recommended Repository Structure

```text
helmetguard-ai/
  api/
    app/
      main.py
      routes/
      schemas/
      services/
      db/
  worker/
    app/
      pipeline/
      models/
      ocr/
      tracking/
      rules/
      tasks/
  shared/
    configs/
    logging/
    contracts/
  infra/
    docker/
    compose/
  tests/
    unit/
    integration/
    evaluation/
  docs/
```

## 16) Key Risks and Mitigations

- Risk: weak accuracy on unseen camera angles
  - Mitigation: continuous retraining from uploaded-video samples
- Risk: false positives in crowded traffic
  - Mitigation: stronger association rules + temporal consensus
- Risk: OCR failures under blur/tilt
  - Mitigation: multi-frame OCR fusion + rectification
- Risk: long processing times for high-res videos
  - Mitigation: configurable frame sampling and worker scaling

## 17) Final Recommendation

Start with an upload-first asynchronous architecture and keep inference decoupled from API requests. This gives a stable product foundation now and allows easy expansion to live camera streaming later without rewriting the core CV pipeline.
