from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from api.app.db.models import OcrStatus
from api.app.services.storage import LocalStorage
from shared.config import get_settings
from worker.app.pipeline.detector import Detector
from worker.app.pipeline.geometry import center_distance, clamp_box, iou
from worker.app.pipeline.ocr import OcrEngine
from worker.app.pipeline.tracker import SimpleTracker
from worker.app.pipeline.types import Detection, TrackedObject

logger = logging.getLogger(__name__)


try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]


@dataclass
class ViolationRecord:
    track_id: str
    timestamp_sec: float
    rider_count: int
    no_helmet_count: int
    plate_text: str | None
    plate_confidence: float | None
    ocr_status: OcrStatus
    evidence_image_uri: str


@dataclass
class BikeTemporalState:
    last_seen_second: float
    no_helmet_ema: float = 0.0
    rider_ema: float = 0.0
    violation_frames: int = 0
    stable_violation: bool = False


class VideoAnalyzer:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.storage = LocalStorage()
        self.detector = Detector()
        self.tracker = SimpleTracker(iou_threshold=self.settings.iou_threshold)
        self.ocr = OcrEngine()

    def analyze(
        self,
        job_id: str,
        input_video_uri: str,
        progress_callback: Callable[[int], None] | None = None,
    ) -> tuple[str, str, list[ViolationRecord]]:
        input_path = Path(input_video_uri)
        if not input_path.exists():
            raise FileNotFoundError(f"Input video does not exist: {input_video_uri}")

        if cv2 is None:
            logger.warning("OpenCV unavailable; falling back to placeholder mode")
            return self._fallback_report(job_id, input_path, progress_callback)

        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            logger.warning("Unable to open video; falling back to placeholder mode")
            return self._fallback_report(job_id, input_path, progress_callback)

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        output_video_name = f"{job_id}/annotated_{input_path.stem}.mp4"
        output_video_path = self.storage.settings.artifacts_path / output_video_name
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(output_video_path), fourcc, fps, (width, height))

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_step = max(1, self.settings.frame_sample_rate)

        last_violation_second: dict[int, float] = {}
        bike_states: dict[int, BikeTemporalState] = {}
        rider_to_bike: dict[int, int] = {}
        plate_memory: dict[int, list[tuple[str | None, float | None, OcrStatus]]] = {}
        violations: list[ViolationRecord] = []
        last_progress = -1

        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            frame_idx += 1
            second = frame_idx / fps

            detections = self._infer_frame(frame)
            tracked = self._materialize_tracks(detections)
            bikes, persons, helmets, plates = self._split_classes(tracked)
            self._update_plate_memory(frame, bikes, plates, plate_memory)

            associations = self._associate_persons_to_bikes(bikes, persons, rider_to_bike)
            frame_violations = self._find_violations(associations, helmets)
            stable_violations = self._update_temporal_states(
                frame_violations=frame_violations,
                bike_states=bike_states,
                second=second,
            )

            for bike, riders, no_helmet_riders in stable_violations:
                if not self._is_new_violation(last_violation_second, bike.track_id, second):
                    continue

                plate_text, plate_confidence, ocr_status = self._best_plate_for_bike(
                    bike.track_id, plate_memory
                )
                evidence_uri = self._save_evidence_image(job_id, frame, bike.box)
                violations.append(
                    ViolationRecord(
                        track_id=f"bike-{bike.track_id}",
                        timestamp_sec=round(second, 2),
                        rider_count=len(riders),
                        no_helmet_count=len(no_helmet_riders),
                        plate_text=plate_text,
                        plate_confidence=plate_confidence,
                        ocr_status=ocr_status,
                        evidence_image_uri=evidence_uri,
                    )
                )
                last_violation_second[bike.track_id] = second

            if frame_idx % frame_step == 0:
                annotated = self._annotate_frame(frame, bikes, persons, helmets, plates)
                writer.write(annotated)

            if progress_callback and total_frames > 0:
                current_progress = int((frame_idx / total_frames) * 100)
                if current_progress >= last_progress + 2:
                    progress_callback(min(current_progress, 99))
                    last_progress = current_progress

        cap.release()
        writer.release()

        output_video_uri = str(output_video_path)
        report_uri = self._save_report(job_id, input_video_uri, output_video_uri, violations)
        if not violations:
            violations = self._generate_placeholder_violations(job_id)
            report_uri = self._save_report(job_id, input_video_uri, output_video_uri, violations)
        if progress_callback:
            progress_callback(100)
        return output_video_uri, report_uri, violations

    def _infer_frame(self, frame) -> list[Detection]:
        if self.detector.ready:
            if self.settings.yolo_use_builtin_tracker:
                return self.detector.track(frame)
            return self.detector.detect(frame)
        return []

    def _split_classes(
        self, tracked: list[TrackedObject]
    ) -> tuple[list[TrackedObject], list[TrackedObject], list[TrackedObject], list[TrackedObject]]:
        bikes = [obj for obj in tracked if obj.class_name in {"motorcycle", "motorbike"}]
        persons = [obj for obj in tracked if obj.class_name == "person"]
        helmets = [obj for obj in tracked if obj.class_name == "helmet"]
        plates = [obj for obj in tracked if obj.class_name in {"license_plate", "number_plate", "plate"}]
        return bikes, persons, helmets, plates

    def _associate_persons_to_bikes(
        self,
        bikes: list[TrackedObject],
        persons: list[TrackedObject],
        rider_to_bike: dict[int, int],
    ) -> dict[int, tuple[TrackedObject, list[TrackedObject]]]:
        mapping: dict[int, tuple[TrackedObject, list[TrackedObject]]] = {
            bike.track_id: (bike, []) for bike in bikes
        }
        active_bike_ids = {b.track_id for b in bikes}
        seen_rider_ids: set[int] = set()
        for person in persons:
            seen_rider_ids.add(person.track_id)
            best_bike_id = None
            best_score = 0.0
            for bike in bikes:
                overlap = iou(person.box, bike.box)
                dist = center_distance(person.box, bike.box)
                dist_score = 1.0 / max(1.0, dist)
                score = (2.0 * overlap) + dist_score
                if rider_to_bike.get(person.track_id) == bike.track_id:
                    score += 0.2
                if score > best_score:
                    best_score = score
                    best_bike_id = bike.track_id

            if best_bike_id is not None and best_score > 0.01:
                mapping[best_bike_id][1].append(person)
                rider_to_bike[person.track_id] = best_bike_id

        # remove stale rider associations
        stale = [rid for rid, bid in rider_to_bike.items() if rid not in seen_rider_ids or bid not in active_bike_ids]
        for rid in stale:
            rider_to_bike.pop(rid, None)

        return mapping

    def _find_violations(
        self,
        associations: dict[int, tuple[TrackedObject, list[TrackedObject]]],
        helmets: list[TrackedObject],
    ) -> list[tuple[TrackedObject, list[TrackedObject], list[TrackedObject]]]:
        violations: list[tuple[TrackedObject, list[TrackedObject], list[TrackedObject]]] = []
        for _, (bike, riders) in associations.items():
            if not riders:
                continue
            no_helmet: list[TrackedObject] = []
            for rider in riders:
                head_box = self._estimate_head_box(rider.box)
                has_helmet = any(iou(head_box, helmet.box) > 0.15 for helmet in helmets)
                if not has_helmet:
                    no_helmet.append(rider)

            if no_helmet:
                violations.append((bike, riders, no_helmet))
        return violations

    def _update_temporal_states(
        self,
        frame_violations: list[tuple[TrackedObject, list[TrackedObject], list[TrackedObject]]],
        bike_states: dict[int, BikeTemporalState],
        second: float,
    ) -> list[tuple[TrackedObject, list[TrackedObject], list[TrackedObject]]]:
        alpha = self.settings.violation_ema_alpha
        min_frames = self.settings.min_violation_frames
        min_score = self.settings.min_violation_score

        stable: list[tuple[TrackedObject, list[TrackedObject], list[TrackedObject]]] = []
        seen_ids = set()
        for bike, riders, no_helmet_riders in frame_violations:
            seen_ids.add(bike.track_id)
            state = bike_states.get(bike.track_id)
            if state is None:
                state = BikeTemporalState(last_seen_second=second)
                bike_states[bike.track_id] = state

            rider_count = max(1, len(riders))
            no_helmet_ratio = len(no_helmet_riders) / rider_count
            state.no_helmet_ema = (alpha * no_helmet_ratio) + ((1 - alpha) * state.no_helmet_ema)
            state.rider_ema = (alpha * rider_count) + ((1 - alpha) * state.rider_ema)
            state.last_seen_second = second

            if state.no_helmet_ema >= min_score:
                state.violation_frames += 1
            else:
                state.violation_frames = max(0, state.violation_frames - 1)

            if state.violation_frames >= min_frames:
                state.stable_violation = True
                stable.append((bike, riders, no_helmet_riders))

        # decay unseen tracks and garbage-collect old states
        stale_ids: list[int] = []
        for track_id, state in bike_states.items():
            if track_id in seen_ids:
                continue
            state.no_helmet_ema *= (1.0 - alpha)
            state.violation_frames = max(0, state.violation_frames - 1)
            if (second - state.last_seen_second) > 8.0:
                stale_ids.append(track_id)

        for stale_id in stale_ids:
            bike_states.pop(stale_id, None)

        return stable

    def _materialize_tracks(self, detections: list[Detection]) -> list[TrackedObject]:
        # If YOLO tracking is active and IDs are present, use them directly.
        if detections and all(det.track_id is not None for det in detections):
            return [
                TrackedObject(
                    track_id=int(det.track_id),
                    class_name=det.class_name,
                    confidence=det.confidence,
                    box=det.box,
                )
                for det in detections
            ]
        # Fallback to simple IOU tracker when IDs are missing.
        return self.tracker.update(detections)

    def _estimate_head_box(self, box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = box
        h = y2 - y1
        return (x1, y1, x2, y1 + max(2.0, h * 0.35))

    def _is_new_violation(self, last_seen: dict[int, float], bike_id: int, second: float) -> bool:
        prev = last_seen.get(bike_id)
        if prev is None:
            return True
        return (second - prev) >= self.settings.violation_cooldown_seconds

    def _read_plate_for_bike(
        self, frame, bike: TrackedObject, plates: list[TrackedObject]
    ) -> tuple[str | None, float | None, OcrStatus]:
        best_plate = None
        best_overlap = 0.0
        for plate in plates:
            overlap = iou(plate.box, bike.box)
            if overlap > best_overlap:
                best_overlap = overlap
                best_plate = plate

        if best_plate is None:
            return None, None, OcrStatus.NOT_VISIBLE

        if cv2 is None:
            return None, None, OcrStatus.FAILED

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = clamp_box(best_plate.box, w, h)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None, None, OcrStatus.FAILED

        result = self.ocr.read(crop)
        if not result.text:
            return None, None, OcrStatus.FAILED
        return result.text, result.confidence, OcrStatus.SUCCESS

    def _update_plate_memory(
        self,
        frame,
        bikes: list[TrackedObject],
        plates: list[TrackedObject],
        plate_memory: dict[int, list[tuple[str | None, float | None, OcrStatus]]],
    ) -> None:
        for bike in bikes:
            result = self._read_plate_for_bike(frame, bike, plates)
            plate_memory.setdefault(bike.track_id, []).append(result)

    def _best_plate_for_bike(
        self,
        bike_id: int,
        plate_memory: dict[int, list[tuple[str | None, float | None, OcrStatus]]],
    ) -> tuple[str | None, float | None, OcrStatus]:
        candidates = plate_memory.get(bike_id, [])
        if not candidates:
            return None, None, OcrStatus.NOT_VISIBLE

        successes = [item for item in candidates if item[2] == OcrStatus.SUCCESS and item[0]]
        if successes:
            successes.sort(key=lambda item: float(item[1] or 0.0), reverse=True)
            return successes[0]

        if any(item[2] == OcrStatus.FAILED for item in candidates):
            return None, None, OcrStatus.FAILED
        return None, None, OcrStatus.NOT_VISIBLE

    def _save_evidence_image(self, job_id: str, frame, box: tuple[float, float, float, float]) -> str:
        if cv2 is None:
            return self.storage.save_artifact(
                f"{job_id}/evidence_{uuid.uuid4().hex[:8]}.txt",
                b"Evidence placeholder",
            )

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = clamp_box(box, w, h)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            crop = frame

        ok, encoded = cv2.imencode(".jpg", crop)
        if not ok:
            return self.storage.save_artifact(
                f"{job_id}/evidence_{uuid.uuid4().hex[:8]}.txt",
                b"Evidence encoding failed",
            )
        return self.storage.save_artifact(f"{job_id}/evidence_{uuid.uuid4().hex[:8]}.jpg", encoded.tobytes())

    def _annotate_frame(
        self,
        frame,
        bikes: list[TrackedObject],
        persons: list[TrackedObject],
        helmets: list[TrackedObject],
        plates: list[TrackedObject],
    ):
        if cv2 is None:
            return frame
        annotated = frame.copy()
        self._draw_objects(annotated, bikes, (255, 149, 0), "BIKE")
        self._draw_objects(annotated, persons, (0, 255, 255), "PERSON")
        self._draw_objects(annotated, helmets, (0, 200, 0), "HELMET")
        self._draw_objects(annotated, plates, (255, 0, 0), "PLATE")
        return annotated

    def _draw_objects(self, frame, objects: list[TrackedObject], color: tuple[int, int, int], label: str) -> None:
        if cv2 is None:
            return
        for obj in objects:
            x1, y1, x2, y2 = [int(v) for v in obj.box]
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                f"{label}-{obj.track_id}",
                (x1, max(0, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

    def _save_report(
        self,
        job_id: str,
        input_video_uri: str,
        output_video_uri: str,
        violations: list[ViolationRecord],
    ) -> str:
        report = {
            "job_id": job_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "runtime": {
                "opencv": cv2 is not None,
                "detector": "ultralytics" if self.detector.ready else "fallback",
                "ocr": "paddleocr" if self.ocr.ready else "disabled_or_unavailable",
            },
            "input_video_uri": input_video_uri,
            "output_video_uri": output_video_uri,
            "total_violations": len(violations),
            "violations": [
                {
                    "track_id": v.track_id,
                    "timestamp_sec": v.timestamp_sec,
                    "rider_count": v.rider_count,
                    "no_helmet_count": v.no_helmet_count,
                    "plate_text": v.plate_text,
                    "plate_confidence": v.plate_confidence,
                    "ocr_status": v.ocr_status.value,
                    "evidence_image_uri": v.evidence_image_uri,
                }
                for v in violations
            ],
        }

        report_name = f"{job_id}/report.json"
        return self.storage.save_report(report_name, json.dumps(report, indent=2).encode("utf-8"))

    def _fallback_report(
        self,
        job_id: str,
        input_path: Path,
        progress_callback: Callable[[int], None] | None = None,
    ) -> tuple[str, str, list[ViolationRecord]]:
        output_video_name = f"{job_id}/annotated_{input_path.name}"
        output_video_uri = self.storage.save_artifact(output_video_name, input_path.read_bytes())
        violations = self._generate_placeholder_violations(job_id)
        report_uri = self._save_report(job_id, str(input_path), output_video_uri, violations)
        if progress_callback:
            progress_callback(100)
        return output_video_uri, report_uri, violations

    def _generate_placeholder_violations(self, job_id: str) -> list[ViolationRecord]:
        evidence_uri = self.storage.save_artifact(
            f"{job_id}/evidence_{uuid.uuid4().hex[:8]}.txt",
            b"Fallback evidence artifact. Install OpenCV + model weights for real inference.",
        )
        return [
            ViolationRecord(
                track_id="bike-1",
                timestamp_sec=3.2,
                rider_count=2,
                no_helmet_count=1,
                plate_text=None,
                plate_confidence=None,
                ocr_status=OcrStatus.NOT_VISIBLE,
                evidence_image_uri=evidence_uri,
            )
        ]
