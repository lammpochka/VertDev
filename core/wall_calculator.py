from dataclasses import dataclass, field

from core.calculator import PointDeviation, sign

from core.wall_matcher import WallSegmentMatch
from core.wall_segment import WallSegment
from readers.survey_reader import SurveyPoint

@dataclass
class WallPairDeviation:
    upper: PointDeviation | None
    lower: PointDeviation | None

    pair_axis_position: float

@dataclass
class WallSegmentDeviations:
    match: WallSegmentMatch
    pairs: list[WallPairDeviation] = field(
        default_factory=list
    )

@dataclass
class WallPointPair:
    upper_point: SurveyPoint | None
    lower_point: SurveyPoint | None

    pair_axis_position: float

@dataclass
class WallSegmentPairs:
    match: WallSegmentMatch

    pairs: list[WallPointPair] = field(
        default_factory=list
    )

def point_axis_position(
    segment: WallSegment,
    point: SurveyPoint,
) -> float:
    """
    Координата точки вдоль сегмента.

    Для горизонтального сегмента — X.
    Для вертикального — Y.
    """
    if segment.orientation == "X":
        return point.x

    return point.y

def create_pair(
    segment: WallSegment,
    upper_point: SurveyPoint | None,
    lower_point: SurveyPoint | None,
) -> WallPointPair:
    """
    Создаёт пару В/Н.

    Положение пары — среднее положение существующих
    точек вдоль сегмента.
    """
    positions = []

    if upper_point is not None:
        positions.append(
            point_axis_position(
                segment,
                upper_point,
            )
        )

    if lower_point is not None:
        positions.append(
            point_axis_position(
                segment,
                lower_point,
            )
        )

    pair_axis_position = (
        sum(positions) / len(positions)
    )

    return WallPointPair(
        upper_point=upper_point,
        lower_point=lower_point,
        pair_axis_position=pair_axis_position,
    )

def pair_level_points(
    match: WallSegmentMatch,
) -> WallSegmentPairs:
    """
    Формирует пары В/Н по близости точек
    вдоль сегмента.

    Каждая нижняя точка используется только один раз.
    Оставшиеся точки становятся одиночными парами.
    """
    segment = match.segment

    upper_points = sorted(
        match.upper_points,
        key=lambda point: point_axis_position(
            segment,
            point,
        ),
    )

    lower_points = sorted(
        match.lower_points,
        key=lambda point: point_axis_position(
            segment,
            point,
        ),
    )

    unused_lower = list(lower_points)
    pairs: list[WallPointPair] = []

    for upper_point in upper_points:
        if not unused_lower:
            pairs.append(
                create_pair(
                    segment=segment,
                    upper_point=upper_point,
                    lower_point=None,
                )
            )
            continue

        upper_position = point_axis_position(
            segment,
            upper_point,
        )

        nearest_lower = min(
            unused_lower,
            key=lambda point: abs(
                point_axis_position(
                    segment,
                    point,
                )
                - upper_position
            ),
        )

        unused_lower.remove(nearest_lower)

        pairs.append(
            create_pair(
                segment=segment,
                upper_point=upper_point,
                lower_point=nearest_lower,
            )
        )

    # Нижние точки, которым не хватило верхней.
    for lower_point in unused_lower:
        pairs.append(
            create_pair(
                segment=segment,
                upper_point=None,
                lower_point=lower_point,
            )
        )

    pairs.sort(
        key=lambda pair: pair.pair_axis_position
    )

    return WallSegmentPairs(
        match=match,
        pairs=pairs,
    )

def build_wall_pairs(
    matches: list[WallSegmentMatch],
) -> list[WallSegmentPairs]:
    """
    Формирует пары для всех сегментов,
    на которых найдены точки.
    """
    results = []

    for match in matches:
        if not match.points:
            continue

        results.append(
            pair_level_points(match)
        )

    return results
def wall_point_deviation(
    segment: WallSegment,
    point: SurveyPoint,
    level: str,
) -> PointDeviation:
    """
    Считает отклонение точки перпендикулярно
    проектному сегменту стены.
    """
    if segment.orientation == "X":
        deviation_m = point.y - segment.start_y

        return PointDeviation(
            point=point,
            value_mm=round(abs(deviation_m) * 1000),
            dx=0,
            dy=sign(deviation_m),
            level=level,
            surface="wall",
        )

    deviation_m = point.x - segment.start_x

    return PointDeviation(
        point=point,
        value_mm=round(abs(deviation_m) * 1000),
        dx=sign(deviation_m),
        dy=0,
        level=level,
        surface="wall",
    )

def calculate_wall_deviations(
    segment_pairs: list[WallSegmentPairs],
) -> list[WallSegmentDeviations]:
    """
    Считает отклонения всех сформированных пар В/Н.
    """
    results: list[WallSegmentDeviations] = []

    for segment_result in segment_pairs:
        segment = segment_result.match.segment
        calculated_pairs: list[WallPairDeviation] = []

        for pair in segment_result.pairs:
            upper_deviation = None

            if pair.upper_point is not None:
                upper_deviation = wall_point_deviation(
                    segment=segment,
                    point=pair.upper_point,
                    level="В",
                )

            lower_deviation = None

            if pair.lower_point is not None:
                lower_deviation = wall_point_deviation(
                    segment=segment,
                    point=pair.lower_point,
                    level="Н",
                )

            calculated_pairs.append(
                WallPairDeviation(
                    upper=upper_deviation,
                    lower=lower_deviation,
                    pair_axis_position=(
                        pair.pair_axis_position
                    ),
                )
            )

        results.append(
            WallSegmentDeviations(
                match=segment_result.match,
                pairs=calculated_pairs,
            )
        )

    return results

def limit_wall_deviations(
    results: list[WallSegmentDeviations],
    limit_mm: int,
) -> None:
    """
    Ограничивает отклонения стен по логике торца пилона.

    Для каждой пары В/Н независимо:
    1. каждое значение ограничивается по модулю;
    2. если разность подписанных отклонений превышает допуск,
       превышение вычитается из нижнего отклонения.

    Никаких соседних пар, соседних сегментов или «длинной стороны»
    при этом не используется.
    """
    from core.calculator import (
        _adjust_long_side_pair,
        _limit_deviation_value,
    )

    for segment_result in results:
        for pair in segment_result.pairs:
            if pair.upper is not None:
                _limit_deviation_value(pair.upper, limit_mm)

            if pair.lower is not None:
                _limit_deviation_value(pair.lower, limit_mm)

            if pair.upper is not None and pair.lower is not None:
                _adjust_long_side_pair(
                    pair.upper,
                    pair.lower,
                    limit_mm,
                    lower_is_second=True,
                )
