from dataclasses import dataclass

@dataclass
class WallSegment:
    start_x: float
    start_y: float

    end_x: float
    end_y: float

    center_x: float
    center_y: float

    length: float

    orientation: str   # "X" или "Y"