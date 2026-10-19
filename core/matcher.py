from dataclasses import dataclass, field
from enum import Enum

from core.pylon import Pylon
from readers.survey_reader import SurveyPoint

import config.config as app_config


DUPLICATE_TOLERANCE = 0.0001

# Размеры областей классификации граней, м.
# Торцевая область: 50 мм по нормали в обе стороны
# от фактической грани и 30 мм за каждый конец торца.

# Насколько область длинной грани может заходить внутрь/наружу
# относительно самой грани. Это значение лучше передавать
# из настроек программы.

class MatchStatus(Enum):
    OK = "OK"
    MISSING = "MISSING"
    EXTRA = "EXTRA"

@dataclass
class PylonMatch:
    pylon: Pylon
    points: list[SurveyPoint]
    status: MatchStatus

@dataclass
class PylonLevels:
    pylon: Pylon
    upper_points: list[SurveyPoint]
    lower_points: list[SurveyPoint]
    middle_z: float | None
    match_status: MatchStatus

@dataclass
class LevelSides:
    long_side_points: list[SurveyPoint]
    end_point: SurveyPoint | None

@dataclass
class LevelDiagnostic:
    level_name: str

    source_points: list[SurveyPoint] = field(
        default_factory=list
    )

    selected_long_points: list[SurveyPoint] = field(
        default_factory=list
    )

    selected_end_point: SurveyPoint | None = None

    rejected_points: list[SurveyPoint] = field(
        default_factory=list
    )

    missing_positions: list[str] = field(
        default_factory=list
    )

@dataclass
class ClassifiedPylon:
    pylon: Pylon
    upper: LevelSides
    lower: LevelSides

    upper_diagnostic: LevelDiagnostic
    lower_diagnostic: LevelDiagnostic

    original_point_count: int

@dataclass
class PylonDiagnostic:
    number: int

    center_x: float
    center_y: float

    total_points: int
    upper_point_count: int
    lower_point_count: int

    processed: bool
    status: str

    upper_selected: list[str] = field(
        default_factory=list
    )
    lower_selected: list[str] = field(
        default_factory=list
    )

    upper_rejected: list[str] = field(
        default_factory=list
    )
    lower_rejected: list[str] = field(
        default_factory=list
    )

    missing_positions: list[str] = field(
        default_factory=list
    )

def deduplicate_points(
    points: list[SurveyPoint],
    tolerance: float = DUPLICATE_TOLERANCE,
) -> list[SurveyPoint]:
    """
    Удаляет повторяющиеся точки по X, Y и Z.

    Номер точки не используется как уникальный признак.
    """
    unique_points: list[SurveyPoint] = []

    for point in points:
        duplicate_found = False

        for saved_point in unique_points:
            same_x = (
                abs(point.x - saved_point.x)
                <= tolerance
            )

            same_y = (
                abs(point.y - saved_point.y)
                <= tolerance
            )

            same_z = (
                abs(point.z - saved_point.z)
                <= tolerance
            )

            if same_x and same_y and same_z:
                duplicate_found = True
                break

        if not duplicate_found:
            unique_points.append(point)

    return unique_points

def point_is_near_pylon(
    point: SurveyPoint,
    pylon: Pylon,
    margin: float,
) -> bool:
    """
    Проверяет, находится ли точка внутри расширенной
    прямоугольной области вокруг пилона.
    """
    if pylon.orientation == "X":
        size_x = pylon.length
        size_y = pylon.width
    else:
        size_x = pylon.width
        size_y = pylon.length

    half_x = size_x / 2
    half_y = size_y / 2

    min_x = pylon.center_x - half_x - margin
    max_x = pylon.center_x + half_x + margin

    min_y = pylon.center_y - half_y - margin
    max_y = pylon.center_y + half_y + margin

    return (
        min_x <= point.x <= max_x
        and min_y <= point.y <= max_y
    )

def match_points_to_pylons(
    pylons: list[Pylon],
    survey_points: list[SurveyPoint],
    margin: float = app_config.SEARCH_MARGIN,
) -> list[PylonMatch]:
    """
    Для каждого пилона собирает все точки-кандидаты
    в расширенной области поиска.
    """
    unique_points = deduplicate_points(survey_points)

    matches: list[PylonMatch] = []

    for pylon in pylons:
        nearby_points = [
            point
            for point in unique_points
            if point_is_near_pylon(
                point,
                pylon,
                margin,
            )
        ]

        if len(nearby_points) == 6:
            status = MatchStatus.OK

        elif len(nearby_points) < 6:
            status = MatchStatus.MISSING

        else:
            status = MatchStatus.EXTRA

        matches.append(
            PylonMatch(
                pylon=pylon,
                points=nearby_points,
                status=status,
            )
        )

    return matches

def split_points_by_height(
    matches: list[PylonMatch],
) -> list[PylonLevels]:
    """
    Делит точки каждого пилона на верхние и нижние.

    Пилоны без найденных точек тоже сохраняются,
    чтобы попасть в диагностику.
    """
    results: list[PylonLevels] = []

    for match in matches:

        # Пилон без единой найденной точки
        if not match.points:
            results.append(
                PylonLevels(
                    pylon=match.pylon,
                    upper_points=[],
                    lower_points=[],
                    middle_z=None,
                    match_status=match.status,
                )
            )
            continue

        # Этот блок обязательно должен быть
        # ВНЕ условия if not match.points
        middle_z = (
            sum(point.z for point in match.points)
            / len(match.points)
        )

        upper_points = [
            point
            for point in match.points
            if point.z > middle_z
        ]

        lower_points = [
            point
            for point in match.points
            if point.z < middle_z
        ]

        results.append(
            PylonLevels(
                pylon=match.pylon,
                upper_points=upper_points,
                lower_points=lower_points,
                middle_z=middle_z,
                match_status=match.status,
            )
        )

    return results

def face_region_bounds(
    pylon: Pylon,
    face_type: str,
    face_key: int,
) -> tuple[float, float, float, float]:
    """
    Возвращает границы прямоугольной зоны соответствия:
    (min_x, max_x, min_y, max_y).

    face_type:
        "long" — длинная грань;
        "end"  — торец.

    face_key:
        -1 — грань с меньшей координатой;
        +1 — грань с большей координатой.

    Для каждой зоны учитывается направление наружной нормали:
    margin_inside уходит внутрь пилона, margin_outside — наружу.
    """
    half_length = pylon.length / 2
    half_width = pylon.width / 2

    if face_type == "long":
        tangential_half = max(
            0.0,
            half_length - app_config.END_FACE_NORMAL_MARGIN_INSIDE,
        )

        if pylon.orientation == "X":
            face = pylon.center_y + face_key * half_width

            # Внутрь — противоположно face_key,
            # наружу — по face_key.
            a = face + face_key * app_config.MARGIN_OUTSIDE
            b = face - face_key * app_config.MARGIN_INSIDE

            return (
                pylon.center_x - tangential_half,
                pylon.center_x + tangential_half,
                min(a, b),
                max(a, b),
            )

        face = pylon.center_x + face_key * half_width
        a = face + face_key * app_config.MARGIN_OUTSIDE
        b = face - face_key * app_config.MARGIN_INSIDE

        return (
            min(a, b),
            max(a, b),
            pylon.center_y - tangential_half,
            pylon.center_y + tangential_half,
        )

    tangential = app_config.END_FACE_TANGENTIAL_MARGIN

    if pylon.orientation == "X":
        face = pylon.center_x + face_key * half_length

        a = face + face_key * app_config.END_FACE_NORMAL_MARGIN_OUTSIDE
        b = face - face_key * app_config.END_FACE_NORMAL_MARGIN_INSIDE

        return (
            min(a, b),
            max(a, b),
            pylon.center_y - half_width - tangential,
            pylon.center_y + half_width + tangential,
        )

    face = pylon.center_y + face_key * half_length
    a = face + face_key * app_config.END_FACE_NORMAL_MARGIN_OUTSIDE
    b = face - face_key * app_config.END_FACE_NORMAL_MARGIN_INSIDE

    return (
        pylon.center_x - half_width - tangential,
        pylon.center_x + half_width + tangential,
        min(a, b),
        max(a, b),
    )


def _face_bounds(
    pylon: Pylon,
    face_type: str,
    face_key: int,
):
    """Совместимый внутренний алиас для получения границ зоны."""
    return face_region_bounds(pylon, face_type, face_key)


def point_in_face_region(
    pylon: Pylon,
    point: SurveyPoint,
    face_type: str,
    face_key: int,
    margin_inside: float = None,
    margin_outside: float = None,
) -> bool:
    """Проверяет попадание точки в область конкретной грани."""
    # Аргументы margin_* оставлены для совместимости со старым API.
    # Фактические размеры берутся из config.py, чтобы GUI-настройки
    # применялись без перезапуска.
    x_min, x_max, y_min, y_max = face_region_bounds(
        pylon,
        face_type,
        face_key,
    )

    return (
        x_min <= point.x <= x_max
        and y_min <= point.y <= y_max
    )


def distance_to_long_side(
    pylon: Pylon,
    point: SurveyPoint,
) -> float:
    """Расстояние точки до ближайшей длинной грани."""
    half_width = pylon.width / 2
    if pylon.orientation == "X":
        edge_1 = pylon.center_y - half_width
        edge_2 = pylon.center_y + half_width
        return min(abs(point.y - edge_1), abs(point.y - edge_2))

    edge_1 = pylon.center_x - half_width
    edge_2 = pylon.center_x + half_width
    return min(abs(point.x - edge_1), abs(point.x - edge_2))


def distance_to_end(
    pylon: Pylon,
    point: SurveyPoint,
) -> float:
    """Расстояние точки до ближайшего торца."""
    half_length = pylon.length / 2
    if pylon.orientation == "X":
        end_1 = pylon.center_x - half_length
        end_2 = pylon.center_x + half_length
        return min(abs(point.x - end_1), abs(point.x - end_2))

    end_1 = pylon.center_y - half_length
    end_2 = pylon.center_y + half_length
    return min(abs(point.y - end_1), abs(point.y - end_2))


def classify_candidate_face(
    pylon: Pylon,
    point: SurveyPoint,
    margin_inside: float = app_config.MARGIN_INSIDE,
    margin_outside: float = app_config.MARGIN_OUTSIDE,
) -> str:
    """
    Определяет грань по прямоугольным областям.

    1. Сначала проверяются торцевые области — они имеют приоритет.
    2. Затем проверяются области длинных граней.
    3. Если точка не попала ни в одну область, возвращается ``none``.
    """
    for face_key in (-1, 1):
        if point_in_face_region(
            pylon, point, "end", face_key, margin_inside, margin_outside
        ):
            return "end"

    for face_key in (-1, 1):
        if point_in_face_region(
            pylon, point, "long", face_key, margin_inside, margin_outside
        ):
            return "long"

    return "none"


def point_deviation_from_long_face(
    pylon: Pylon,
    point: SurveyPoint,
) -> float:
    """
    Абсолютное отклонение от ближайшей длинной грани.
    """
    return distance_to_long_side(
        pylon,
        point,
    )

def point_deviation_from_end_face(
    pylon: Pylon,
    point: SurveyPoint,
) -> float:
    """
    Абсолютное отклонение от ближайшего торца.
    """
    return distance_to_end(
        pylon,
        point,
    )

def long_face_key(
    pylon: Pylon,
    point: SurveyPoint,
) -> int:
    """
    Определяет конкретную длинную грань:

    -1 — грань с меньшей координатой;
    +1 — грань с большей координатой.
    """
    if pylon.orientation == "X":
        return -1 if point.y < pylon.center_y else 1

    return -1 if point.x < pylon.center_x else 1

def end_face_key(
    pylon: Pylon,
    point: SurveyPoint,
) -> int:
    """
    Определяет конкретный торец:

    -1 — торец с меньшей координатой;
    +1 — торец с большей координатой.
    """
    if pylon.orientation == "X":
        return -1 if point.x < pylon.center_x else 1

    return -1 if point.y < pylon.center_y else 1

def choose_common_face(
    pylon: Pylon,
    upper_points: list[SurveyPoint],
    lower_points: list[SurveyPoint],
    face_type: str,
) -> int | None:
    """
    Выбирает одну общую грань для В и Н.

    Приоритет:
    1. На грани присутствуют и В, и Н.
    2. На грани больше пригодных точек.
    3. При полном равенстве выбирается грань
       с большей суммой отклонений.
    """
    if face_type == "long":
        face_key_function = long_face_key
        deviation_function = (
            point_deviation_from_long_face
        )
    else:
        face_key_function = end_face_key
        deviation_function = (
            point_deviation_from_end_face
        )

    best_face: int | None = None
    best_score = None

    for face_key in (-1, 1):
        upper_on_face = [
            point
            for point in upper_points
            if face_key_function(
                pylon,
                point,
            ) == face_key
        ]

        lower_on_face = [
            point
            for point in lower_points
            if face_key_function(
                pylon,
                point,
            ) == face_key
        ]

        if not upper_on_face and not lower_on_face:
            continue

        both_levels_present = (
            int(bool(upper_on_face))
            + int(bool(lower_on_face))
        )

        if face_type == "long":
            useful_count = (
                min(len(upper_on_face), 2)
                + min(len(lower_on_face), 2)
            )
        else:
            useful_count = (
                min(len(upper_on_face), 1)
                + min(len(lower_on_face), 1)
            )

        total_count = (
            len(upper_on_face)
            + len(lower_on_face)
        )

        deviation_sum = sum(
            deviation_function(
                pylon,
                point,
            )
            for point in (
                upper_on_face
                + lower_on_face
            )
        )

        score = (
            both_levels_present,
            useful_count,
            total_count,
            deviation_sum,
        )

        if best_score is None or score > best_score:
            best_score = score
            best_face = face_key

    return best_face

def long_axis_offset(
    pylon: Pylon,
    point: SurveyPoint,
) -> float:
    """
    Положение точки вдоль длинной оси относительно
    центра пилона.

    Отрицательное значение — первая половина.
    Положительное — вторая половина.
    """
    if pylon.orientation == "X":
        return point.x - pylon.center_x

    return point.y - pylon.center_y

def choose_long_side_points(
    pylon: Pylon,
    candidates: list[SurveyPoint],
) -> list[SurveyPoint]:
    """
    Выбирает точки длинной стороны.

    Из левой половины выбирает одну точку с максимальным отклонением.
    Из правой половины выбирает одну точку с максимальным отклонением.

    Возвращает максимум 2 точки (по одной с каждой стороны).
    """
    if not candidates:
        return []

    # Разделяем на левую и правую половины
    negative_half = []
    positive_half = []
    for point in candidates:
        if long_axis_offset(pylon, point) < 0:
            negative_half.append(point)
        else:
            positive_half.append(point)

    selected = []

    # Выбираем лучшую точку из левой половины (если есть)
    if negative_half:
        best_left = max(
            negative_half,
            key=lambda p: point_deviation_from_long_face(pylon, p)
        )
        selected.append(best_left)

    # Выбираем лучшую точку из правой половины (если есть)
    if positive_half:
        best_right = max(
            positive_half,
            key=lambda p: point_deviation_from_long_face(pylon, p)
        )
        selected.append(best_right)

    # Сортируем по оси, чтобы порядок был слева направо
    selected.sort(key=lambda p: long_axis_offset(pylon, p))
    return selected

def choose_end_point(
    pylon: Pylon,
    candidates: list[SurveyPoint],
) -> SurveyPoint | None:
    """
    Из торцевых кандидатов выбирает точку с
    наибольшим абсолютным отклонением.
    """
    if not candidates:
        return None

    return max(
        candidates,
        key=lambda point: (
            point_deviation_from_end_face(
                pylon,
                point,
            )
        ),
    )

def classify_level_points_smart(
    pylon: Pylon,
    points: list[SurveyPoint],
    level_name: str,
    selected_long_face: int | None,
    selected_end_face: int | None,
) -> tuple[LevelSides, LevelDiagnostic]:
    """
    Выбирает точки только на заранее выбранных
    общей длинной грани и общем торце.
    """
    diagnostic = LevelDiagnostic(
        level_name=level_name,
        source_points=list(points),
    )

    long_candidates: list[SurveyPoint] = []
    end_candidates: list[SurveyPoint] = []

    for point in points:
        face_type = classify_candidate_face(
            pylon,
            point,
        )

        if face_type == "long":
            if (
                selected_long_face is not None
                and long_face_key(
                    pylon,
                    point,
                ) == selected_long_face
            ):
                long_candidates.append(point)

        else:
            if (
                selected_end_face is not None
                and end_face_key(
                    pylon,
                    point,
                ) == selected_end_face
            ):
                end_candidates.append(point)

    selected_long = choose_long_side_points(
        pylon,
        long_candidates,
    )

    selected_end = choose_end_point(
        pylon,
        end_candidates,
    )

    diagnostic.selected_long_points = (
        selected_long
    )
    diagnostic.selected_end_point = (
        selected_end
    )

    selected_points = list(selected_long)

    if selected_end is not None:
        selected_points.append(selected_end)

    diagnostic.rejected_points = [
        point
        for point in points
        if point not in selected_points
    ]

    if len(selected_long) < 2:
        missing_count = 2 - len(selected_long)

        for number in range(missing_count):
            diagnostic.missing_positions.append(
                f"{level_name}: "
                f"длинная сторона "
                f"{len(selected_long) + number + 1}"
            )

    if selected_end is None:
        diagnostic.missing_positions.append(
            f"{level_name}: торец"
        )

    sides = LevelSides(
        long_side_points=selected_long,
        end_point=selected_end,
    )

    return sides, diagnostic

def point_names(
    points: list[SurveyPoint],
) -> list[str]:
    return [
        str(point.name)
        for point in points
    ]

def classify_pylon_points_with_diagnostics(
    levels: list[PylonLevels],
) -> tuple[
    list[ClassifiedPylon],
    list[PylonDiagnostic],
]:
    """
    Классифицирует пилоны и одновременно создаёт
    подробную диагностику для каждого из них.
    """
    results: list[ClassifiedPylon] = []
    diagnostics: list[PylonDiagnostic] = []

    for number, level in enumerate(
        levels,
        start=1,
    ):
        all_upper_long = [
            point
            for point in level.upper_points
            if classify_candidate_face(
                level.pylon,
                point,
            ) == "long"
        ]

        all_lower_long = [
            point
            for point in level.lower_points
            if classify_candidate_face(
                level.pylon,
                point,
            ) == "long"
        ]

        all_upper_end = [
            point
            for point in level.upper_points
            if classify_candidate_face(
                level.pylon,
                point,
            ) == "end"
        ]

        all_lower_end = [
            point
            for point in level.lower_points
            if classify_candidate_face(
                level.pylon,
                point,
            ) == "end"
        ]

        selected_long_face = choose_common_face(
            pylon=level.pylon,
            upper_points=all_upper_long,
            lower_points=all_lower_long,
            face_type="long",
        )

        selected_end_face = choose_common_face(
            pylon=level.pylon,
            upper_points=all_upper_end,
            lower_points=all_lower_end,
            face_type="end",
        )

        upper, upper_diagnostic = (
            classify_level_points_smart(
                pylon=level.pylon,
                points=level.upper_points,
                level_name="В",
                selected_long_face=(
                    selected_long_face
                ),
                selected_end_face=(
                    selected_end_face
                ),
            )
        )

        lower, lower_diagnostic = (
            classify_level_points_smart(
                pylon=level.pylon,
                points=level.lower_points,
                level_name="Н",
                selected_long_face=(
                    selected_long_face
                ),
                selected_end_face=(
                    selected_end_face
                ),
            )
        )

        selected_point_count = (
            len(upper.long_side_points)
            + len(lower.long_side_points)
            + (1 if upper.end_point is not None else 0)
            + (1 if lower.end_point is not None else 0)
        )

        processed = selected_point_count > 0

        missing_positions = (
            upper_diagnostic.missing_positions
            + lower_diagnostic.missing_positions
        )

        rejected_count = (
            len(upper_diagnostic.rejected_points)
            + len(lower_diagnostic.rejected_points)
        )

        if missing_positions:
            status = "MISSING"
        elif rejected_count > 0:
            status = "EXTRA"
        else:
            status = "OK"

        upper_selected_points = list(
            upper_diagnostic.selected_long_points
        )

        if (
            upper_diagnostic.selected_end_point
            is not None
        ):
            upper_selected_points.append(
                upper_diagnostic.selected_end_point
            )

        lower_selected_points = list(
            lower_diagnostic.selected_long_points
        )

        if (
            lower_diagnostic.selected_end_point
            is not None
        ):
            lower_selected_points.append(
                lower_diagnostic.selected_end_point
            )

        diagnostics.append(
            PylonDiagnostic(
                number=number,
                center_x=level.pylon.center_x,
                center_y=level.pylon.center_y,
                total_points=(
                    len(level.upper_points)
                    + len(level.lower_points)
                ),
                upper_point_count=len(
                    level.upper_points
                ),
                lower_point_count=len(
                    level.lower_points
                ),
                processed=processed,
                status=status,
                upper_selected=point_names(
                    upper_selected_points
                ),
                lower_selected=point_names(
                    lower_selected_points
                ),
                upper_rejected=point_names(
                    upper_diagnostic.rejected_points
                ),
                lower_rejected=point_names(
                    lower_diagnostic.rejected_points
                ),
                missing_positions=missing_positions,
            )
        )
        results.append(
            ClassifiedPylon(
                pylon=level.pylon,
                upper=upper,
                lower=lower,
                upper_diagnostic=upper_diagnostic,
                lower_diagnostic=lower_diagnostic,
                original_point_count=(
                    len(level.upper_points)
                    + len(level.lower_points)
                ),
            )
        )

    return results, diagnostics

def classify_pylon_points(
    levels: list[PylonLevels],
) -> list[ClassifiedPylon]:
    """
    Старый совместимый вызов без получения диагностики.
    """
    classified, _ = (
        classify_pylon_points_with_diagnostics(
            levels
        )
    )

    return classified