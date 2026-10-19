import ezdxf
import math

from core.wall_segment import WallSegment

import config.config as app_config
from core.pylon import Pylon
from core.wall import WallContour

def normalize_duplicate_points_with_diagnostics(
    points: list[tuple[float, float]],
    tolerance: float = 0.01,
) -> tuple[list[tuple[float, float]], list[dict]]:
    """Удаляет повторяющиеся соседние вершины и повторную замыкающую точку."""
    if not points:
        return [], []

    normalized: list[tuple[float, float]] = []
    removals: list[dict] = []

    for index, point in enumerate(points):
        if normalized:
            previous = normalized[-1]
            if (
                abs(point[0] - previous[0]) <= tolerance
                and abs(point[1] - previous[1]) <= tolerance
            ):
                removals.append({
                    "index": index + 1,
                    "point": point,
                    "reason": "повтор соседней вершины",
                    "previous": previous,
                    "tolerance": tolerance,
                })
                continue

        normalized.append(point)

    # Последняя вершина замкнутой полилинии иногда повторяет первую.
    if len(normalized) >= 2:
        first = normalized[0]
        last = normalized[-1]
        if (
            abs(first[0] - last[0]) <= tolerance
            and abs(first[1] - last[1]) <= tolerance
        ):
            removed = normalized.pop()
            removals.append({
                "index": len(points),
                "point": removed,
                "reason": "повтор первой вершины в конце замкнутого контура",
                "previous": normalized[-1] if normalized else None,
                "tolerance": tolerance,
            })

    return normalized, removals


def normalized_points(
    points: list[tuple[float, float]],
    tolerance: float = 0.01,
) -> list[tuple[float, float]]:
    """Возвращает точки без повторяющихся соседних/замыкающих вершин."""
    normalized, _ = normalize_duplicate_points_with_diagnostics(points, tolerance)
    return normalized


def remove_collinear_points_with_diagnostics(
    points: list[tuple[float, float]],
    tolerance: float = 0.0001,
) -> tuple[list[tuple[float, float]], list[dict], list[dict]]:
    """Удаляет коллинеарные вершины после предварительного удаления дублей."""
    points, normalization_removed = normalize_duplicate_points_with_diagnostics(points)

    if len(points) <= 3:
        return points, [], normalization_removed

    cleaned: list[tuple[float, float]] = []
    removals: list[dict] = []

    for index in range(len(points)):
        previous_point = points[index - 1]
        current_point = points[index]
        next_point = points[(index + 1) % len(points)]

        previous_x, previous_y = previous_point
        current_x, current_y = current_point
        next_x, next_y = next_point

        first_vector_x = current_x - previous_x
        first_vector_y = current_y - previous_y
        second_vector_x = next_x - current_x
        second_vector_y = next_y - current_y

        cross_product = (
            first_vector_x * second_vector_y
            - first_vector_y * second_vector_x
        )

        if abs(cross_product) <= tolerance:
            removals.append({
                "index": index + 1,
                "point": current_point,
                "previous": previous_point,
                "next": next_point,
                "vector_in": (first_vector_x, first_vector_y),
                "vector_out": (second_vector_x, second_vector_y),
                "cross_product": cross_product,
                "tolerance": tolerance,
            })
            continue

        cleaned.append(current_point)

    return cleaned, removals, normalization_removed


def remove_collinear_points(
    points: list[tuple[float, float]],
    tolerance: float = 0.0001,
) -> list[tuple[float, float]]:
    cleaned, _, _ = remove_collinear_points_with_diagnostics(points, tolerance)
    return cleaned

def is_axis_aligned_rectangle(
    points: list[tuple[float, float]],
    tolerance: float = 0.001,
) -> bool:
    """
    Проверяет, является ли контур прямоугольником,
    ориентированным вдоль осей X/Y.
    """
    points = normalized_points(points)

    if len(points) != 4:
        return False

    for index in range(4):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % 4]

        horizontal = abs(y2 - y1) <= tolerance
        vertical = abs(x2 - x1) <= tolerance

        if not horizontal and not vertical:
            return False

        # Нулевая сторона.
        if (
            abs(x2 - x1) <= tolerance
            and abs(y2 - y1) <= tolerance
        ):
            return False

    return True

def diagnose_axis_aligned_rectangle(
    points: list[tuple[float, float]],
    tolerance: float = 0.001,
) -> tuple[bool, str]:
    """Возвращает результат проверки прямоугольника и причину отказа."""
    points = normalized_points(points)

    if len(points) != 4:
        return False, f"после очистки не 4 вершины (получено {len(points)})"

    for index in range(4):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % 4]

        dx = x2 - x1
        dy = y2 - y1

        horizontal = abs(dy) <= tolerance
        vertical = abs(dx) <= tolerance

        if not horizontal and not vertical:
            return (
                False,
                f"сторона {index + 1} не горизонтальная/вертикальная "
                f"(dx={dx:.6f}, dy={dy:.6f}, допуск={tolerance:.6f})",
            )

        if abs(dx) <= tolerance and abs(dy) <= tolerance:
            return (
                False,
                f"сторона {index + 1} имеет нулевую длину "
                f"(dx={dx:.6f}, dy={dy:.6f})",
            )

    return True, "прямоугольник X/Y"


def build_segments(points):
    segments = []

    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]

        dx = x2 - x1
        dy = y2 - y1

        length = math.hypot(dx, dy)

        if length < 0.001:
            continue

        if abs(dx) >= abs(dy):
            orientation = "X"
        else:
            orientation = "Y"

        segments.append(
            WallSegment(
                start_x=x1,
                start_y=y1,

                end_x=x2,
                end_y=y2,

                center_x=(x1 + x2) / 2,
                center_y=(y1 + y2) / 2,

                length=length,

                orientation=orientation,
            )
        )

    return segments

def create_wall_contour(
    points: list[tuple[float, float]],
) -> WallContour:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    segments = build_segments(points)
    return WallContour(
        segments=segments,
        points=points,
        min_x=min_x,
        max_x=max_x,
        min_y=min_y,
        max_y=max_y,
        center_x=(min_x + max_x) / 2,
        center_y=(min_y + max_y) / 2,
    )

def read_geometry(
    filename: str,
) -> tuple[list[Pylon], list[WallContour]]:
    """
    Разделяет замкнутые полилинии DXF на:

    1. Пилоны:
       - прямоугольник;
       - короткая сторона не больше app_config.MAX_PYLON_WIDTH.

    2. Стеновые контуры:
       - непрямоугольные замкнутые полилинии;
       - прямоугольники с короткой стороной больше
         app_config.MAX_PYLON_WIDTH.
    """
    document = ezdxf.readfile(filename)
    modelspace = document.modelspace()

    pylons: list[Pylon] = []
    wall_contours: list[WallContour] = []
    geometry_diagnostics: list[dict] = []

    contour_number = 0

    for entity in modelspace:
        if entity.dxftype() != "LWPOLYLINE":
            continue

        if not entity.closed:
            continue

        contour_number += 1

        raw_points = [
            (point[0], point[1])
            for point in entity.get_points()
        ]

        normalized_raw_points = normalized_points(raw_points)
        points, collinear_removals, normalization_removed = (
            remove_collinear_points_with_diagnostics(raw_points)
        )

        print(
            f"Контур: было {len(raw_points)} вершин, "
            f"стало {len(points)}"
        )

        if len(points) < 3:
            continue

        if len(points) < 3:
            continue

        xs = [point[0] for point in points]
        ys = [point[1] for point in points]

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        size_x = max_x - min_x
        size_y = max_y - min_y

        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        if size_x >= size_y:
            length = size_x
            width = size_y
            orientation = "X"
        else:
            length = size_y
            width = size_x
            orientation = "Y"

        rectangle, rectangle_reason = diagnose_axis_aligned_rectangle(
            points
        )

        width_ok = width <= app_config.MAX_PYLON_WIDTH

        is_pylon = (
            rectangle
            and width_ok
        )

        if is_pylon:
            classification = "ПИЛОН"
            reason = "прямоугольник X/Y и ширина в пределах допуска"
        else:
            classification = "СТЕНА"
            if not rectangle:
                reason = rectangle_reason
            else:
                reason = (
                    f"ширина {width:.6f} > "
                    f"MAX_PYLON_WIDTH {app_config.MAX_PYLON_WIDTH:.6f}"
                )

        geometry_diagnostics.append({
            "number": contour_number,
            "raw_vertices": len(raw_points),
            "normalized_vertices": len(normalized_raw_points),
            "cleaned_vertices": len(points),
            "raw_points": raw_points,
            "normalized_points": normalized_raw_points,
            "cleaned_points": points,
            "normalization_removed": normalization_removed,
            "collinear_removals": collinear_removals,
            "size_x": size_x,
            "size_y": size_y,
            "length": length,
            "width": width,
            "orientation": orientation,
            "rectangle": rectangle,
            "rectangle_reason": rectangle_reason,
            "width_ok": width_ok,
            "classification": classification,
            "reason": reason,
            "max_pylon_width": app_config.MAX_PYLON_WIDTH,
            "entity_handle": getattr(entity.dxf, "handle", ""),
        })

        if is_pylon:
            pylons.append(
                Pylon(
                    center_x,
                    center_y,
                    length,
                    width,
                    orientation,
                    points,
                )
            )

        elif app_config.SEARCH_WALL_CONTOURS:
            wall_contours.append(
                create_wall_contour(points)
            )

    return pylons, wall_contours, geometry_diagnostics

def read_pylons(
    filename: str,
) -> list[Pylon]:
    """
    Совместимость со старым кодом.

    Возвращает только пилоны.
    """
    pylons, _, _ = read_geometry(filename)

    return pylons

def read_wall_contours(
    filename: str,
) -> list[WallContour]:
    """
    Возвращает только стеновые контуры.
    """
    _, wall_contours, _ = read_geometry(filename)

    return wall_contours