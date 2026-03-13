from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Detection:
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    track_id: int | None = None

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass
class TrackedObject:
    track_id: int
    class_name: str
    confidence: float
    box: tuple[float, float, float, float]


@dataclass
class PlateResult:
    text: str | None
    confidence: float | None
