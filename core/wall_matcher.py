from dataclasses import dataclass, field

import config.config as app_config
from core.wall import WallContour
from core.wall_segment import WallSegment
from readers.survey_reader import SurveyPoint

ENDPOINT_MARGIN = 0.03

@dataclass
class WallSegmentMatch:
    contour_number: int
    segment_number: int

    contour: WallContour
    segment: WallSegment

    points: list[SurveyPoint] = field(
        default_factory=list
    )

    upper_points: list[SurveyPoint] = field(
        default_factory=list
    )

    lower_points: list[SurveyPoint] = field(
        default_factory=list
    )

    middle_z: float | None = None

@dataclass
class SegmentCandidate:
    """
    Связь точки с сегментом-кандидатом.
    """
    point: SurveyPoint
    match: WallSegmentMatch
    perpendicular_distance: float

def collect_segments(
    wall_contours: list[WallContour],
) -> list[WallSegmentMatch]:
    """
    Создаёт запись для каждого сегмента
    каждого стенового контура.
    """
    matches: list[WallSegmentMatch] = []

    for contour_number, contour in enumerate(
        wall_contours,
        start=1,
    ):
        for segment_number, segment in enumerate(
            contour.segments,
            start=1,
        ):
            matches.append(
                WallSegmentMatch(
                    contour_number=contour_number,
                    segment_number=segment_number,
                    contour=contour,
                    segment=segment,
                )
            )

    return matches

def point_is_in_segment_corridor(
    point: SurveyPoint,
    segment: WallSegment,
    margin: float,
    endpoint_margin: float = ENDPOINT_MARGIN,
) -> bool:
    """
    Проверяет, находится ли точка в прямоугольной
    зоне поиска конкретного сегмента.

    margin:
        допустимое расстояние поперёк стены.

    endpoint_margin:
        небольшой запас за началом и концом сегмента.
    """
    min_x = min(
        segment.start_x,
        segment.end_x,
    )
    max_x = max(
        segment.start_x,
        segment.end_x,
    )

    min_y = min(
        segment.start_y,
        segment.end_y,
    )
    max_y = max(
        segment.start_y,
        segment.end_y,
    )

    if segment.orientation == "X":
        inside_length = (
            min_x - endpoint_margin
            <= point.x
            <= max_x + endpoint_margin
        )

        inside_width = (
            abs(point.y - segment.start_y)
            <= margin
        )

        return inside_length and inside_width

    inside_length = (
        min_y - endpoint_margin
        <= point.y
        <= max_y + endpoint_margin
    )

    inside_width = (
        abs(point.x - segment.start_x)
        <= margin
    )

    return inside_length and inside_width

def perpendicular_distance_to_segment(
    point: SurveyPoint,
    segment: WallSegment,
) -> float:
    """
    Возвращает расстояние до проектной линии
    перпендикулярно сегменту.

    Для горизонтальной стены сравнивается Y.
    Для вертикальной стены сравнивается X.
    """
    if segment.orientation == "X":
        return abs(
            point.y - segment.start_y
        )

    return abs(
        point.x - segment.start_x
    )

def collect_segment_candidates(
    matches: list[WallSegmentMatch],
    survey_points: list[SurveyPoint],
    margin: float,
) -> list[SegmentCandidate]:
    """
    Каждый сегмент собирает все точки,
    попавшие в его поисковый коридор.
    """
    candidates: list[SegmentCandidate] = []

    for match in matches:
        for point in survey_points:
            if not point_is_in_segment_corridor(
                point=point,
                segment=match.segment,
                margin=margin,
            ):
                continue

            candidates.append(
                SegmentCandidate(
                    point=point,
                    match=match,
                    perpendicular_distance=(
                        perpendicular_distance_to_segment(point,
                            match.segment,
                        )
                    ),
                )
            )

    return candidates

def assign_unique_candidates(
    matches: list[WallSegmentMatch],
    candidates: list[SegmentCandidate],
) -> None:
    """
    Если точка попала в коридоры нескольких сегментов,
    оставляет её у сегмента с минимальным
    перпендикулярным расстоянием.

    Одна точка назначается только одному сегменту.
    """
    candidates_by_point: dict[
        int,
        list[SegmentCandidate],
    ] = {}

    for candidate in candidates:
        point_key = id(candidate.point)

        candidates_by_point.setdefault(
            point_key,
            [],
        ).append(candidate)

    for point_candidates in (
        candidates_by_point.values()
    ):
        best_candidate = min(
            point_candidates,
            key=lambda item: (
                item.perpendicular_distance
            ),
        )

        best_candidate.match.points.append(
            best_candidate.point
        )

def split_wall_points_by_height(
    matches: list[WallSegmentMatch],
) -> list[WallSegmentMatch]:
    """
    Делит точки каждого сегмента на В и Н
    относительно средней отметки Z.
    """
    for match in matches:
        if not match.points:
            match.middle_z = None
            match.upper_points = []
            match.lower_points = []
            continue

        match.middle_z = (
            sum(
                point.z
                for point in match.points
            )
            / len(match.points)
        )

        match.upper_points = [
            point
            for point in match.points
            if point.z > match.middle_z
        ]

        match.lower_points = [
            point
            for point in match.points
            if point.z < match.middle_z
        ]

    return matches

def match_wall_points(
    wall_contours: list[WallContour],
    survey_points: list[SurveyPoint],
    margin: float = app_config.WALL_SEARCH_MARGIN,
) -> list[WallSegmentMatch]:
    """
    Новый матчер стен.

    1. Каждый сегмент создаёт свою область поиска.
    2. Сегменты собирают точки-кандидаты.
    3. Дубли в углах разрешаются по минимальному
       перпендикулярному расстоянию.
    4. Точки делятся на В и Н.
    """
    matches = collect_segments(
        wall_contours
    )

    candidates = collect_segment_candidates(
        matches=matches,
        survey_points=survey_points,
        margin=margin,
    )

    assign_unique_candidates(
        matches=matches,
        candidates=candidates,
    )

    return split_wall_points_by_height(
        matches
    )