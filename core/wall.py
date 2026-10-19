from dataclasses import dataclass
from core.wall_segment import WallSegment

@dataclass
class WallContour:
    points: list[tuple[float, float]]

    segments: list[WallSegment]

    min_x: float
    max_x: float
    min_y: float
    max_y: float

    center_x: float
    center_y: float