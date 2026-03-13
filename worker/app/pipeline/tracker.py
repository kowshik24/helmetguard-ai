from __future__ import annotations

from worker.app.pipeline.geometry import iou
from worker.app.pipeline.types import Detection, TrackedObject


class SimpleTracker:
    def __init__(self, iou_threshold: float = 0.35) -> None:
        self.iou_threshold = iou_threshold
        self.next_id = 1
        self.last_objects: list[TrackedObject] = []

    def update(self, detections: list[Detection]) -> list[TrackedObject]:
        tracked: list[TrackedObject] = []

        for det in detections:
            if det.track_id is not None:
                tracked.append(
                    TrackedObject(
                        track_id=det.track_id,
                        class_name=det.class_name,
                        confidence=det.confidence,
                        box=det.box,
                    )
                )
                continue

            matched_id = self._match(det)
            if matched_id is None:
                matched_id = self.next_id
                self.next_id += 1

            tracked.append(
                TrackedObject(
                    track_id=matched_id,
                    class_name=det.class_name,
                    confidence=det.confidence,
                    box=det.box,
                )
            )

        self.last_objects = tracked
        return tracked

    def _match(self, det: Detection) -> int | None:
        best_id: int | None = None
        best_iou = 0.0
        for obj in self.last_objects:
            if obj.class_name != det.class_name:
                continue
            current = iou(obj.box, det.box)
            if current >= self.iou_threshold and current > best_iou:
                best_iou = current
                best_id = obj.track_id
        return best_id
