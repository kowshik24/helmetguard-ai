from __future__ import annotations

from shared.config import get_settings
from worker.app.pipeline.types import Detection


class Detector:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._model = None
        self._class_map: dict[int, str] = {}

        if not self.settings.enable_vision_runtime:
            return

        try:
            from ultralytics import YOLO  # type: ignore
        except Exception:
            return

        try:
            self._model = YOLO(self.settings.yolo_model_path)
        except Exception:
            return
        names = getattr(self._model.model, "names", None)
        if isinstance(names, dict):
            self._class_map = {int(k): str(v) for k, v in names.items()}

    @property
    def ready(self) -> bool:
        return self._model is not None

    def detect(self, frame) -> list[Detection]:
        if not self._model:
            return []

        results = self._model.predict(
            source=frame,
            conf=self.settings.detection_confidence,
            iou=self.settings.iou_threshold,
            verbose=False,
        )
        return self._to_detections(results)

    def track(self, frame) -> list[Detection]:
        if not self._model:
            return []

        results = self._model.track(
            source=frame,
            conf=self.settings.detection_confidence,
            iou=self.settings.iou_threshold,
            tracker=self.settings.yolo_tracker_config,
            persist=True,
            verbose=False,
        )
        return self._to_detections(results)

    def _to_detections(self, results) -> list[Detection]:
        detections: list[Detection] = []
        if not results:
            return detections

        boxes = results[0].boxes
        if boxes is None:
            return detections

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        classes = boxes.cls.cpu().numpy().astype(int)
        ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else None

        for idx, coords in enumerate(xyxy):
            cls_idx = int(classes[idx])
            class_name = self._class_map.get(cls_idx, str(cls_idx))
            if class_name not in self.settings.target_classes:
                continue
            track_id = int(ids[idx]) if ids is not None and idx < len(ids) else None
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=float(confs[idx]),
                    x1=float(coords[0]),
                    y1=float(coords[1]),
                    x2=float(coords[2]),
                    y2=float(coords[3]),
                    track_id=track_id,
                )
            )
        return detections
