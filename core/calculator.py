from dataclasses import dataclass
import random

from core.matcher import ClassifiedPylon
from readers.survey_reader import SurveyPoint
import config.config as app_config

@dataclass
class PointDeviation:
    point: SurveyPoint
    value_mm: int
    dx: int
    dy: int
    level: str
    surface: str

@dataclass
class PylonDeviations:
    pylon: object
    upper_long: list[PointDeviation]
    lower_long: list[PointDeviation]
    upper_end: PointDeviation | None
    lower_end: PointDeviation | None

def sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0

def long_side_deviation(
    pylon,
    point: SurveyPoint,
    level: str,
) -> PointDeviation:
    """
    Отклонение точки от ближайшей длинной грани пилона.
    Направление задаётся в координатах AutoCAD.
    """
    if pylon.orientation == "X":
        half_width = pylon.width / 2

        lower_edge = pylon.center_y - half_width
        upper_edge = pylon.center_y + half_width

        if abs(point.y - lower_edge) <= abs(point.y - upper_edge):
            project_coordinate = lower_edge
        else:
            project_coordinate = upper_edge

        deviation_m = point.y - project_coordinate

        return PointDeviation(
            point=point,
            value_mm=round(abs(deviation_m) * 1000),
            dx=0,
            dy=sign(deviation_m),
            level=level,
            surface="long",
        )

    half_width = pylon.width / 2

    left_edge = pylon.center_x - half_width
    right_edge = pylon.center_x + half_width

    if abs(point.x - left_edge) <= abs(point.x - right_edge):
        project_coordinate = left_edge
    else:
        project_coordinate = right_edge

    deviation_m = point.x - project_coordinate

    return PointDeviation(
        point=point,
        value_mm=round(abs(deviation_m) * 1000),
        dx=sign(deviation_m),
        dy=0,
        level=level,
        surface="long",
    )

def end_deviation(
    pylon,
    point: SurveyPoint,
    level: str,
) -> PointDeviation:
    """
    Отклонение точки от ближайшего торца пилона.
    """
    if pylon.orientation == "X":
        half_length = pylon.length / 2

        left_end = pylon.center_x - half_length
        right_end = pylon.center_x + half_length

        if abs(point.x - left_end) <= abs(point.x - right_end):
            project_coordinate = left_end
        else:
            project_coordinate = right_end

        deviation_m = point.x - project_coordinate

        return PointDeviation(
            point=point,
            value_mm=round(abs(deviation_m) * 1000),
            dx=sign(deviation_m),
            dy=0,
            level=level,
            surface="end",
        )

    half_length = pylon.length / 2

    lower_end = pylon.center_y - half_length
    upper_end = pylon.center_y + half_length

    if abs(point.y - lower_end) <= abs(point.y - upper_end):
        project_coordinate = lower_end
    else:
        project_coordinate = upper_end

    deviation_m = point.y - project_coordinate

    return PointDeviation(
        point=point,
        value_mm=round(abs(deviation_m) * 1000),
        dx=0,
        dy=sign(deviation_m),
        level=level,
        surface="end",
    )


def _limit_deviation_value(deviation: PointDeviation, limit_mm: int) -> None:
    """Ограничивает модуль отклонения, сохраняя его направление."""
    if deviation.value_mm > limit_mm:
        deviation.value_mm = limit_mm


def _reduce_deviation_magnitude(
    deviation: PointDeviation,
    amount_mm: int,
) -> None:
    """Уменьшает модуль отклонения, не меняя его направление."""
    if amount_mm <= 0:
        return

    deviation.value_mm -= amount_mm


def _adjust_long_side_pair(
    first: PointDeviation,
    second: PointDeviation,
    limit_mm: int,
    *,
    lower_is_second: bool,
) -> None:
    """
    Проверяет одну пару отклонений.

    Если отклонения разных уровней, уменьшается модуль нижнего.
    Для пары одного уровня уменьшается модуль большего отклонения.
    """
    difference = abs(first.value_mm * first_sign(first) - second.value_mm * first_sign(second))
    if difference <= limit_mm:
        return

    excess = difference - limit_mm

    if lower_is_second:
        _reduce_deviation_magnitude(second, excess)
        return

    if abs(first.value_mm) >= abs(second.value_mm):
        _reduce_deviation_magnitude(first, excess)
    else:
        _reduce_deviation_magnitude(second, excess)


def first_sign(deviation: PointDeviation) -> int:
    """Возвращает знак отклонения по его направлению."""
    if deviation.dx != 0:
        return 1 if deviation.dx > 0 else -1
    if deviation.dy != 0:
        return 1 if deviation.dy > 0 else -1
    return 0


def _long_axis_position(pylon, point: SurveyPoint) -> float:
    """Возвращает координату точки вдоль длинной оси пилона."""
    return point.x if pylon.orientation == "X" else point.y


def _pair_centers(pylon) -> list[float]:
    """Возвращает центры виджетов длинной стороны."""
    if (
        app_config.SHORT_PYLONS_ENABLED
        and pylon.length < app_config.SHORT_PYLON_MAX_LENGTH
    ):
        return [
            pylon.center_x
            if pylon.orientation == "X"
            else pylon.center_y
        ]

    axis_center = (
        pylon.center_x
        if pylon.orientation == "X"
        else pylon.center_y
    )
    return [
        axis_center - pylon.length / 4,
        axis_center + pylon.length / 4,
    ]


def _slot_index(pylon, point: SurveyPoint, slot_count: int) -> int:
    """Определяет виджет длинной стороны, к которому относится точка."""
    if slot_count == 1:
        return 0

    axis_center = (
        pylon.center_x
        if pylon.orientation == "X"
        else pylon.center_y
    )
    return 0 if _long_axis_position(pylon, point) < axis_center else 1


def _long_side_normal(pylon, point: SurveyPoint) -> tuple[int, int]:
    """Возвращает внешнюю нормаль длинной грани."""
    if pylon.orientation == "X":
        return (0, 1) if point.y >= pylon.center_y else (0, -1)
    return (1, 0) if point.x >= pylon.center_x else (-1, 0)


def _end_normal(pylon, point: SurveyPoint) -> tuple[int, int]:
    """Возвращает внешнюю нормаль торцевой грани."""
    if pylon.orientation == "X":
        return (1, 0) if point.x >= pylon.center_x else (-1, 0)
    return (0, 1) if point.y >= pylon.center_y else (0, -1)


def _signed_outward_value(pylon, deviation: PointDeviation) -> int:
    """
    Переводит текущее хранение (модуль + направление)
    в условный знак: + наружу, - внутрь.
    """
    normal = (
        _long_side_normal(pylon, deviation.point)
        if deviation.surface == "long"
        else _end_normal(pylon, deviation.point)
    )
    direction = (deviation.dx, deviation.dy)
    same_direction = direction == normal
    return deviation.value_mm if same_direction else -deviation.value_mm


def _make_generated_deviation(
    pylon,
    *,
    level: str,
    surface: str,
    axis_position: float,
    signed_value_mm: int,
    normal: tuple[int, int],
) -> PointDeviation:
    """Создаёт искусственное отклонение в нужном месте виджета."""
    normal_x, normal_y = normal
    half_width = pylon.width / 2
    half_length = pylon.length / 2

    if surface == "long":
        if pylon.orientation == "X":
            x = axis_position
            y = pylon.center_y + normal_y * half_width
        else:
            x = pylon.center_x + normal_x * half_width
            y = axis_position
    else:
        if pylon.orientation == "X":
            x = pylon.center_x + normal_x * half_length
            y = axis_position
        else:
            x = axis_position
            y = pylon.center_y + normal_y * half_length

    value_mm = abs(int(signed_value_mm))
    if signed_value_mm >= 0:
        dx, dy = normal
    else:
        dx, dy = -normal_x, -normal_y

    point = SurveyPoint(
        name="GEN",
        x=x,
        y=y,
        z=0.0,
    )

    return PointDeviation(
        point=point,
        value_mm=value_mm,
        dx=dx,
        dy=dy,
        level=level,
        surface=surface,
    )


def _generate_from_reference(
    pylon,
    reference: PointDeviation | None,
    *,
    level: str,
    surface: str,
    axis_position: float,
    fallback_mm: int = 10,
) -> PointDeviation:
    """Генерирует отклонение от существующего значения либо случайно."""
    if reference is not None:
        signed_value = (
            _signed_outward_value(pylon, reference)
            + random.randint(-3, 3)
        )
        normal = (
            _long_side_normal(pylon, reference.point)
            if surface == "long"
            else _end_normal(pylon, reference.point)
        )
    else:
        signed_value = random.randint(-fallback_mm, fallback_mm)
        # Если вообще нет ни одной точки на этой поверхности,
        # выбираем положительную (+наружу) грань как базовую.
        normal = (
            (0, 1) if pylon.orientation == "X" else (1, 0)
        ) if surface == "long" else (
            (1, 0) if pylon.orientation == "X" else (0, 1)
        )

    return _make_generated_deviation(
        pylon,
        level=level,
        surface=surface,
        axis_position=axis_position,
        signed_value_mm=signed_value,
        normal=normal,
    )


def _fill_missing_end_deviations(
    result: PylonDeviations,
) -> None:
    """Заполняет пропуски торца, не обращаясь к длинной стороне."""
    pylon = result.pylon

    if pylon.orientation == "X":
        axis_position = pylon.center_y
    else:
        axis_position = pylon.center_x

    original_upper = result.upper_end
    original_lower = result.lower_end

    if original_upper is None:
        result.upper_end = _generate_from_reference(
            pylon,
            original_lower,
            level="В",
            surface="end",
            axis_position=axis_position,
        )

    if original_lower is None:
        result.lower_end = _generate_from_reference(
            pylon,
            original_upper,
            level="Н",
            surface="end",
            axis_position=axis_position,
        )


def _fill_missing_long_deviations(
    result: PylonDeviations,
) -> None:
    """
    Заполняет пропуски длинной стороны.

    Приоритет для каждого пропуска:
    1. противоположный уровень в том же виджете;
    2. тот же уровень в соседнем виджете;
    3. противоположный уровень в соседнем виджете;
    4. случайное значение от -10 до +10.

    Торцевые значения здесь намеренно никогда не используются.
    """
    pylon = result.pylon
    centers = _pair_centers(pylon)
    slot_count = len(centers)

    upper = [None] * slot_count
    lower = [None] * slot_count

    for deviation in result.upper_long:
        slot = _slot_index(pylon, deviation.point, slot_count)
        if upper[slot] is None:
            upper[slot] = deviation

    for deviation in result.lower_long:
        slot = _slot_index(pylon, deviation.point, slot_count)
        if lower[slot] is None:
            lower[slot] = deviation

    original_upper = upper.copy()
    original_lower = lower.copy()

    for slot in range(slot_count):
        if upper[slot] is None:
            references = [
                original_lower[slot],
                original_upper[1 - slot] if slot_count == 2 else None,
                original_lower[1 - slot] if slot_count == 2 else None,
            ]
            reference = next(
                (item for item in references if item is not None),
                None,
            )
            upper[slot] = _generate_from_reference(
                pylon,
                reference,
                level="В",
                surface="long",
                axis_position=centers[slot],
            )

        if lower[slot] is None:
            references = [
                original_upper[slot],
                original_lower[1 - slot] if slot_count == 2 else None,
                original_upper[1 - slot] if slot_count == 2 else None,
            ]
            reference = next(
                (item for item in references if item is not None),
                None,
            )
            lower[slot] = _generate_from_reference(
                pylon,
                reference,
                level="Н",
                surface="long",
                axis_position=centers[slot],
            )

    result.upper_long = upper
    result.lower_long = lower


def generate_tolerance_for_pylon(result: PylonDeviations, limit_mm: int) -> None:
    """
    Сначала заполняет отсутствующие отклонения искусственными значениями,
    затем ограничивает допуском весь набор и проверяет пары.

    Это важно: сгенерированные значения тоже не должны иметь возможности
    выйти за заданный допуск.
    """
    # Сначала закрываем все пропуски. С этого момента в наборе находятся
    # и реальные, и сгенерированные отклонения.
    _fill_missing_long_deviations(result)
    _fill_missing_end_deviations(result)

    all_deviations = (
        result.upper_long
        + result.lower_long
        + ([result.upper_end] if result.upper_end is not None else [])
        + ([result.lower_end] if result.lower_end is not None else [])
    )

    # Теперь ограничиваем уже ВСЕ значения, включая сгенерированные.
    for deviation in all_deviations:
        _limit_deviation_value(deviation, limit_mm)

    upper = result.upper_long
    lower = result.lower_long

    if len(upper) >= 2:
        _adjust_long_side_pair(upper[0], upper[1], limit_mm, lower_is_second=False)

    if len(lower) >= 2:
        _adjust_long_side_pair(lower[0], lower[1], limit_mm, lower_is_second=False)

    for upper_deviation in upper[:2]:
        for lower_deviation in lower[:2]:
            _adjust_long_side_pair(
                upper_deviation,
                lower_deviation,
                limit_mm,
                lower_is_second=True,
            )

    if result.upper_end is not None and result.lower_end is not None:
        _adjust_long_side_pair(
            result.upper_end,
            result.lower_end,
            limit_mm,
            lower_is_second=True,
        )



def generate_tolerance(results: list[PylonDeviations]) -> None:
    """Применяет генерацию допуска ко всем рассчитанным пилонам."""
    limit_mm = app_config.TOLERANCE_GENERATION_LIMIT_MM

    for result in results:
        generate_tolerance_for_pylon(result, limit_mm)


def calculate_deviations(
    classified_pylons: list[ClassifiedPylon],
) -> list[PylonDeviations]:
    results = []

    for item in classified_pylons:
        upper_long = [
            long_side_deviation(item.pylon, point, "В")
            for point in item.upper.long_side_points
        ]

        lower_long = [
            long_side_deviation(item.pylon, point, "Н")
            for point in item.lower.long_side_points
        ]

        upper_end = None

        if item.upper.end_point is not None:
            upper_end = end_deviation(
            item.pylon,
            item.upper.end_point,
            "В",
            )

        lower_end = None
        
        if item.lower.end_point is not None:
            lower_end = end_deviation(
            item.pylon,
            item.lower.end_point,
            "Н",
        )

        results.append(
            PylonDeviations(
                pylon=item.pylon,
                upper_long=upper_long,


lower_long=lower_long,
                upper_end=upper_end,
                lower_end=lower_end,
            )
        )

    return results