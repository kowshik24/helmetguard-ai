from pathlib import Path

from shared.config import get_settings


class LocalStorage:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.upload_path.mkdir(parents=True, exist_ok=True)
        self.settings.artifacts_path.mkdir(parents=True, exist_ok=True)
        self.settings.reports_path.mkdir(parents=True, exist_ok=True)

    def save_upload(self, filename: str, content: bytes) -> str:
        target = self.settings.upload_path / filename
        target.write_bytes(content)
        return str(target)

    def save_artifact(self, relative_name: str, content: bytes) -> str:
        target = self.settings.artifacts_path / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)

    def save_report(self, relative_name: str, content: bytes) -> str:
        target = self.settings.reports_path / relative_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)

    def exists(self, uri: str) -> bool:
        return Path(uri).exists()
