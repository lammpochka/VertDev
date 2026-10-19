from core.arrows import (
    Arrow,
    create_arrow_from_anchor,
    pair_axis_positions,
)
from core.wall_calculator import (
    WallSegmentDeviations,
)

def segment_anchor(
    segment,
    axis_position: float,
) -> tuple[float, float]:
    """
    Возвращает точку непосредственно
    на проектном сегменте стены.
    """
    if segment.orientation == "X":
        return axis_position, segment.start_y

    return segment.start_x, axis_position

def contour_signed_area(contour) -> float:
    """
    Знак площади определяет направление обхода контура.

    Положительное значение — против часовой стрелки.
    Отрицательное — по часовой стрелке.
    """
    area = 0.0
    points = contour.points

    for index in range(len(points)):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % len(points)]

        area += x1 * y2 - x2 * y1

    return area / 2

def outward_segment_normal(
    contour,
    segment,
) -> tuple[int, int]:
    """
    Возвращает внешнюю нормаль сегмента независимо
    от направления фактического отклонения точки.
    """
    dx = segment.end_x - segment.start_x
    dy = segment.end_y - segment.start_y

    area = contour_signed_area(contour)

    if area > 0:
        # Контур идёт против часовой стрелки:
        # наружу находится справа от сегмента.
        normal_x = dy
        normal_y = -dx
    else:
        # Контур идёт по часовой стрелке:
        # наружу находится слева от сегмента.
        normal_x = -dy
        normal_y = dx

    if abs(normal_x) >= abs(normal_y):
        return (
            1 if normal_x > 0 else -1,
            0,
        )

    return (
        0,
        1 if normal_y > 0 else -1,
    )

def generate_wall_arrows(
    results: list[WallSegmentDeviations],
) -> list[Arrow]:
    """
    Создаёт для стен такие же пары стрелок В/Н,
    как для пилонов.
    """
    arrows: list[Arrow] = []

    for result in results:
        segment = result.match.segment
        normal_x, normal_y = outward_segment_normal(
            result.match.contour,
            segment,
            )

        axis_is_horizontal = (
            segment.orientation == "X"
        )

        for pair in result.pairs:
            upper_axis, lower_axis = (
                pair_axis_positions(
                    pair_center=pair.pair_axis_position,
                    axis_is_horizontal=axis_is_horizontal,
                )
            )

            if pair.upper is not None:
                anchor_x, anchor_y = segment_anchor(
                    segment,
                    upper_axis,
                )

                arrows.append(
                    create_arrow_from_anchor(
                        anchor_x=anchor_x,
                        anchor_y=anchor_y,
                        deviation=pair.upper,
                        normal_x=normal_x,
                        normal_y=normal_y,
                    )
                )

            if pair.lower is not None:
                anchor_x, anchor_y = segment_anchor(
                    segment,
                    lower_axis,
                )

                arrows.append(
                    create_arrow_from_anchor(
                        anchor_x=anchor_x,
                        anchor_y=anchor_y,
                        deviation=pair.lower,
                        normal_x=normal_x,
                        normal_y=normal_y,
                    )
                )

    return arrows