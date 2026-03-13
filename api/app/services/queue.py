import json
import logging
from pathlib import Path

try:
    from redis import Redis
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]

from shared.config import get_settings
from shared.contracts import JobPayload

logger = logging.getLogger(__name__)


class JobQueue:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._queue_file = settings.data_root / "local_queue.jsonl"
        self._queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True) if Redis else None

    def enqueue(self, payload: JobPayload) -> None:
        message = json.dumps(payload.model_dump())
        if self._redis:
            self._redis.lpush(self._settings.queue_name, message)
            return

        with self._queue_file.open("a", encoding="utf-8") as fp:
            fp.write(message + "\n")
        logger.warning("Redis unavailable. Job written to local fallback queue: %s", self._queue_file)
