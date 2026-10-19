import math
from dataclasses import dataclass
from typing import List, Tuple
from readers.survey_reader import SurveyPoint

@dataclass
class TransformParams:
    tx: float
    ty: float
    angle: float
    cos_a: float
    sin_a: float

def compute_transform(
    msk1_x, msk1_y, psk1_x, psk1_y,
    msk2_x, msk2_y, psk2_x, psk2_y,
) -> TransformParams:
    dx_msk = msk2_x - msk1_x
    dy_msk = msk2_y - msk1_y
    len_msk = math.hypot(dx_msk, dy_msk)
    if len_msk < 1e-9:
        raise ValueError("Расстояние между опорными точками в МСК слишком мало")

    dx_psk = psk2_x - psk1_x
    dy_psk = psk2_y - psk1_y
    len_psk = math.hypot(dx_psk, dy_psk)
    if len_psk < 1e-9:
        raise ValueError("Расстояние между опорными точками в ПСК слишком мало")

    scale = len_psk / len_msk
    if abs(scale - 1.0) > 0.001:
        raise ValueError("Масштаб не равен 1 (возможно, ошибка в координатах)")

    angle_msk = math.atan2(dy_msk, dx_msk)
    angle_psk = math.atan2(dy_psk, dx_psk)
    angle = angle_psk - angle_msk

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    tx = psk1_x - (msk1_x * cos_a - msk1_y * sin_a)
    ty = psk1_y - (msk1_x * sin_a + msk1_y * cos_a)

    return TransformParams(tx=tx, ty=ty, angle=angle, cos_a=cos_a, sin_a=sin_a)

def apply_transform_to_point(x, y, params):
    x_new = x * params.cos_a - y * params.sin_a + params.tx
    y_new = x * params.sin_a + y * params.cos_a + params.ty
    return x_new, y_new

def apply_transform(points: List[SurveyPoint], params: TransformParams) -> List[SurveyPoint]:
    transformed = []
    for p in points:
        nx, ny = apply_transform_to_point(p.x, p.y, params)
        transformed.append(SurveyPoint(name=p.name, x=nx, y=ny, z=p.z))
    return transformed