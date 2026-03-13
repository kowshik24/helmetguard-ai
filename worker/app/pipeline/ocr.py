from __future__ import annotations

from shared.config import get_settings
from worker.app.pipeline.types import PlateResult


class OcrEngine:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._engine = None

        if not self.settings.enable_vision_runtime:
            return

        if not self.settings.enable_ocr:
            return

        try:
            from paddleocr import PaddleOCR  # type: ignore
        except Exception:
            return

        self._engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

    @property
    def ready(self) -> bool:
        return self._engine is not None

    def read(self, image) -> PlateResult:
        if not self._engine:
            return PlateResult(text=None, confidence=None)

        results = self._engine.ocr(image, cls=True)
        if not results or not results[0]:
            return PlateResult(text=None, confidence=None)

        # Keep best OCR line for plate-like short text.
        best_text = None
        best_conf = 0.0
        for line in results[0]:
            text = line[1][0].strip() if line and len(line) > 1 else ""
            conf = float(line[1][1]) if line and len(line) > 1 else 0.0
            if conf > best_conf and text:
                best_conf = conf
                best_text = text

        if not best_text:
            return PlateResult(text=None, confidence=None)
        return PlateResult(text=best_text, confidence=best_conf)
