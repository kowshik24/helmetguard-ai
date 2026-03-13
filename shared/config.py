from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "HelmetGuard AI"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "sqlite:///./data/helmetguard.db"

    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "helmetguard.jobs"

    data_root: Path = Field(default_factory=lambda: Path("data"))
    upload_dir: str = "uploads"
    artifacts_dir: str = "artifacts"
    reports_dir: str = "reports"

    max_upload_mb: int = 500
    signed_url_ttl_seconds: int = 3600

    detection_confidence: float = 0.35
    iou_threshold: float = 0.5
    violation_cooldown_seconds: int = 6
    frame_sample_rate: int = 2
    enable_vision_runtime: bool = True
    yolo_model_path: str = "yolov8n.pt"
    yolo_use_builtin_tracker: bool = True
    yolo_tracker_config: str = "bytetrack.yaml"
    target_classes_raw: str = "person,motorcycle,helmet,license_plate"
    enable_ocr: bool = True
    enable_ffmpeg_faststart: bool = True
    ffmpeg_bin: str = "ffmpeg"
    violation_ema_alpha: float = 0.35
    min_violation_frames: int = 3
    min_violation_score: float = 0.55

    @property
    def upload_path(self) -> Path:
        return self.data_root / self.upload_dir

    @property
    def artifacts_path(self) -> Path:
        return self.data_root / self.artifacts_dir

    @property
    def reports_path(self) -> Path:
        return self.data_root / self.reports_dir

    @property
    def target_classes(self) -> set[str]:
        return {item.strip() for item in self.target_classes_raw.split(",") if item.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
