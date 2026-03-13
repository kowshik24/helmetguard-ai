# HelmetGuard AI - Concrete Implementation Checklist

## How to Use This Checklist
- Execute tasks in order unless marked parallel.
- Each task has a clear output and acceptance criteria.
- Keep PRs small: one major task-group per PR.

## Phase 0 - Project Setup (Day 1-2)

### 0.1 Repository skeleton
- Task: Create folders for `api/`, `worker/`, `shared/`, `infra/`, `tests/`, `docs/`.
- Output: Standardized repo layout from architecture doc.
- Done when: All base folders exist and README maps their purpose.

### 0.2 Python environment and tooling
- Task: Add dependency management (`uv` or `poetry`) and lockfile.
- Task: Add lint/format/type tools (`ruff`, `black`, `mypy` optional).
- Output: Reproducible dev environment.
- Done when: `make lint` and `make format` succeed locally.

### 0.3 Local infra bootstrap
- Task: Add `docker-compose` for `postgres`, `redis`, `minio`.
- Task: Add bootstrap script for buckets and DB migration run.
- Output: One command local startup.
- Done when: `docker compose up` gives healthy services.

### 0.4 Configuration baseline
- Task: Add `.env.example` with DB, Redis, object storage, thresholds.
- Task: Implement shared config loader.
- Output: Central config with validation.
- Done when: API and worker both start with same config module.

## Phase 1 - API + Job Lifecycle (Day 3-5)

### 1.1 FastAPI app bootstrap
- Task: Create FastAPI app with versioned routes `/api/v1`.
- Task: Add health endpoint.
- Output: Running API skeleton.
- Done when: `GET /api/v1/health` returns 200.

### 1.2 Database schema and migrations
- Task: Create tables `jobs`, `violations`, optional `job_events`.
- Task: Add migration tooling (Alembic).
- Output: Versioned schema.
- Done when: Fresh DB migration applies successfully.

### 1.3 Object storage integration
- Task: Implement upload helper to MinIO/S3-compatible storage.
- Task: Add signed URL generation for private artifacts.
- Output: Storage abstraction.
- Done when: Uploaded file path and signed read URL work end-to-end.

### 1.4 Job APIs
- Task: `POST /api/v1/jobs` (multipart video upload + create job).
- Task: `GET /api/v1/jobs/{job_id}` (status/progress).
- Task: `GET /api/v1/jobs/{job_id}/results` (stub until worker done).
- Output: Full job lifecycle contract.
- Done when: Uploaded video creates `queued` job row and response includes `job_id`.

### 1.5 Queue producer
- Task: Publish processing payload to Redis queue from job creation.
- Task: Add idempotency guard for duplicate enqueue.
- Output: API-to-worker decoupling.
- Done when: New jobs appear in queue and are not duplicated on retries.

## Phase 2 - Worker + Baseline Vision Pipeline (Day 6-10)

### 2.1 Worker bootstrap
- Task: Create worker process with queue consumer and graceful shutdown.
- Task: Implement job status transitions (`queued -> processing -> completed/failed`).
- Output: Functional async worker.
- Done when: Worker consumes test jobs and updates DB state.

### 2.2 Video decode and frame loop
- Task: Build frame reader and configurable sampling (`every_n_frames`).
- Task: Add progress updates by processed frame ratio.
- Output: Reusable frame processing loop.
- Done when: Worker reports progress during long jobs.

### 2.3 Detection and tracking integration
- Task: Integrate YOLO detector for `motorcycle`, `person`, `helmet`, `license_plate`.
- Task: Integrate tracker (ByteTrack/BoT-SORT).
- Output: Per-frame detections with stable track IDs.
- Done when: Debug output shows consistent IDs across frames.

### 2.4 Rider-bike association rules
- Task: Implement geometric association between person tracks and motorcycle tracks.
- Task: Estimate head region from person box.
- Output: `bike_id -> associated_people[]`.
- Done when: On sample clips, associated riders are mostly correct.

### 2.5 Helmet violation logic
- Task: Mark violation when associated required person lacks helmet overlap.
- Task: Add per-track cooldown dedupe.
- Output: Stable violation event generation.
- Done when: One bike track does not spam repeated violations.

### 2.6 Evidence extraction
- Task: Save best evidence frame (sharpness/size heuristic).
- Task: Save cropped bike/rider evidence assets.
- Output: Actionable evidence artifacts.
- Done when: Every violation has at least one evidence image URI.

### 2.7 Report generation
- Task: Create JSON report with summary + per-violation entries.
- Task: Save report to object storage and DB.
- Output: Machine-readable results.
- Done when: `/results` endpoint returns complete report payload.

## Phase 3 - Plate OCR and Output Video (Day 11-14)

### 3.1 Plate crop and preprocessing
- Task: Crop plate candidates from detection/tracks.
- Task: Add resize/denoise/rectification utilities.
- Output: OCR-friendly plate images.
- Done when: Plate crops are visibly cleaner than raw crops.

### 3.2 OCR module
- Task: Integrate OCR engine (e.g., PaddleOCR).
- Task: Parse and normalize plate text.
- Output: Text + confidence per candidate.
- Done when: OCR returns text for readable plate frames.

### 3.3 Multi-frame plate fusion
- Task: Aggregate OCR across track frames.
- Task: Select best plate text using confidence + pattern validation.
- Output: More stable final plate text.
- Done when: Final plate result is better than single-frame baseline.

### 3.4 Annotated video writer
- Task: Render boxes/labels/track IDs/violation markers into output video.
- Task: Upload processed video artifact and store URI.
- Output: Visual audit video.
- Done when: Results endpoint exposes downloadable annotated video URL.

## Phase 4 - Web UI (Day 15-18)

### 4.1 Upload and status page
- Task: Build upload form with file constraints and client validation.
- Task: Add polling UI for status/progress.
- Output: Usable MVP frontend flow.
- Done when: User can upload and see live status without manual API calls.

### 4.2 Results dashboard
- Task: Show summary counts, timeline, and violation list.
- Task: Render evidence snapshots and plate text/OCR state.
- Output: Decision-friendly review page.
- Done when: Non-technical user can inspect all results from UI.

### 4.3 Artifact actions
- Task: Add download links for report JSON and annotated video.
- Task: Add basic filters (with/without plate, confidence threshold).
- Output: Practical investigation UX.
- Done when: Reviewer can quickly find high-confidence cases.

## Phase 5 - Quality, Security, and Hardening (Day 19-23)

### 5.1 Validation and safety checks
- Task: Enforce mime/size limits and reject invalid uploads.
- Task: Add request size limits and server timeouts.
- Output: Safer ingestion path.
- Done when: Invalid files are rejected with clear error messages.

### 5.2 Auth and access controls (if required)
- Task: Add API key/JWT guard.
- Task: Restrict artifact access via signed URLs.
- Output: Controlled access.
- Done when: Unauthenticated requests cannot access job results.

### 5.3 Observability
- Task: Add structured logging and request/job correlation IDs.
- Task: Export metrics (job duration, fail rate, OCR success).
- Output: Operable system telemetry.
- Done when: You can diagnose slow/failed jobs from logs/metrics.

### 5.4 Failure and retry policy
- Task: Add bounded worker retries for transient failures.
- Task: Mark permanent failures with actionable error reason.
- Output: Predictable failure handling.
- Done when: Failed jobs are visible and not stuck in `processing`.

### 5.5 Data retention
- Task: Add cleanup job for stale raw uploads/artifacts by TTL.
- Output: Storage control policy.
- Done when: Old artifacts are cleaned automatically by schedule.

## Phase 6 - Model Improvement Loop (Day 24+ ongoing)

### 6.1 Curation pipeline
- Task: Sample frames from uploaded videos for annotation.
- Task: Build dataset splits (`train/val/test`) and version tags.
- Output: Growing domain dataset.
- Done when: Each release has a tracked dataset version.

### 6.2 Annotation operations
- Task: Set CVAT label schema and annotation guide.
- Task: Label hard cases first (night, occlusion, multiple riders).
- Output: Higher-value annotations.
- Done when: QA pass shows consistent annotations.

### 6.3 Retraining pipeline
- Task: Script training runs with reproducible config.
- Task: Register model metrics and artifact version.
- Output: Repeatable training workflow.
- Done when: New model can be promoted with measured gains.

### 6.4 Model release policy
- Task: Define promotion criteria (precision/recall/OCR thresholds).
- Task: Add rollback mechanism to previous stable model.
- Output: Safer production updates.
- Done when: Model deployment is reversible and metric-driven.

## Cross-Cutting Test Checklist

### Unit tests
- Association logic edge cases
- Helmet overlap logic
- OCR normalization and plate validation parser

### Integration tests
- Upload -> queue -> worker -> results end-to-end
- Worker failure and retry transitions
- Signed URL generation and expiration behavior

### Evaluation tests
- Helmet violation precision/recall on benchmark set
- OCR read accuracy and `not_visible` fallback rate
- Throughput benchmark by resolution and video length

## Minimal MVP Definition (Go-Live Gate)

- Must have:
  - Upload video
  - Async processing with visible status
  - Helmet violation detection with evidence images
  - Results API + UI display
- Should have:
  - Plate OCR with fallback status
  - Annotated output video
- Nice to have:
  - Auth, retention automation, advanced filters

## Suggested Task Board Columns
- `Backlog`
- `Ready`
- `In Progress`
- `In Review`
- `Done`
- `Blocked`

## Priority Order (If Time Is Tight)
1. Phase 1 (API/job lifecycle)
2. Phase 2 (worker + helmet pipeline)
3. Phase 4.1/4.2 (basic UI)
4. Phase 3 (OCR + annotated video)
5. Phase 5+ (hardening and improvement loop)
