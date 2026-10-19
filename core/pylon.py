from dataclasses import dataclass

@dataclass
class Pylon:
    center_x: float
    center_y: float

    length: float
    width: float

    orientation: str

    vertices: list