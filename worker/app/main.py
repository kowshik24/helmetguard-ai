from __future__ import annotations

import json
import logging
import signal
from typing import Any

try:
    from redis import Redis
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]

from api.app.db.init_db import init_db
from api.app.db.session import SessionLocal
from shared.config import get_settings
from shared.contracts import JobPayload
from shared.logging import configure_logging
from worker.app.tasks.process_job import JobProcessor

configure_logging()
logger = logging.getLogger(__name__)

RUNNING = True


def _stop(*_: Any) -> None:
    global RUNNING
    RUNNING = False


def main() -> None:
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    settings = get_settings()
    init_db()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True) if Redis else None
    fallback_queue = settings.data_root / "local_queue.jsonl"
    fallback_queue.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Worker started. queue=%s", settings.queue_name)
    while RUNNING:
        raw_payload = _next_payload(redis_client, settings.queue_name, fallback_queue)
        if not raw_payload:
            continue

        payload = JobPayload.model_validate(json.loads(raw_payload))

        db = SessionLocal()
        try:
            JobProcessor(db).run(payload.job_id, payload.input_video_uri)
        finally:
            db.close()

    logger.info("Worker stopped")


def _next_payload(redis_client: Redis | None, queue_name: str, queue_file) -> str | None:
    if redis_client:
        item = redis_client.brpop(queue_name, timeout=2)
        if item:
            _, raw_payload = item
            return raw_payload
        return None

    if not queue_file.exists():
        return None

    lines = queue_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    first = lines[0]
    queue_file.write_text("\n".join(lines[1:]) + ("\n" if len(lines) > 1 else ""), encoding="utf-8")
    return first


if __name__ == "__main__":
    main()
