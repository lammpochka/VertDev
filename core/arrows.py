from dataclasses import dataclass

from core.calculator import (
    PointDeviation,
    PylonDeviations,
)

import config.config as app_config

@dataclass
class Arrow:
    start_x: float
    start_y: float

    end_x: float
    end_y: float

    text_x: float
    text_y: float

    value_text: str
    level_text: str

    color: int

    # Геометрический ключ пилона-владельца; у стрелок стен остаётся None.
    pylon_key: tuple | None = None

def nearest_long_face(pylon, point) -> tuple[int, int]:
    """
    Возвращает внешнюю нормаль длинной грани.

    Возможные результаты:
    (0, 1)   — верхняя грань
    (0, -1)  — нижняя грань
    (1, 0)   — правая грань
    (-1, 0)  — левая грань
    """
    if pylon.orientation == "X":
        if point.y >= pylon.center_y:
            return 0, 1

        return 0, -1

    if point.x >= pylon.center_x:
        return 1, 0

    return -1, 0

def nearest_end_face(pylon, point) -> tuple[int, int]:
    """
    Возвращает внешнюю нормаль ближайшего торца.
    """
    if pylon.orientation == "X":
        if point.x >= pylon.center_x:
            return 1, 0

        return -1, 0

    if point.y >= pylon.center_y:
        return 0, 1

    return 0, -1

def face_point(
    pylon,
    axis_position: float,
    normal_x: int,
    normal_y: int,
) -> tuple[float, float]:
    """
    Определяет точку непосредственно на проектной грани.
    """

    half_length = pylon.length / 2
    half_width = pylon.width / 2

    if pylon.orientation == "X":
        if normal_y != 0:
            # Длинная горизонтальная грань
            x = axis_position
            y = pylon.center_y + normal_y * half_width
        else:
            # Вертикальный торец
            x = pylon.center_x + normal_x * half_length
            y = axis_position

    else:
        if normal_x != 0:
            # Длинная вертикальная грань
            x = pylon.center_x + normal_x * half_width
            y = axis_position
        else:
            # Горизонтальный торец
            x = axis_position
            y = pylon.center_y + normal_y * half_length

    return x, y

def create_arrow_from_anchor(
    anchor_x: float,
    anchor_y: float,
    deviation: PointDeviation,
    normal_x: int,
    normal_y: int,
) -> Arrow:
    """
    Создаёт стрелку от готовой точки на проектной грани.

    Используется и пилонами, и стенами.
    """
    near_x = anchor_x + normal_x * app_config.WALL_OFFSET
    near_y = anchor_y + normal_y * app_config.WALL_OFFSET

    far_x = near_x + normal_x * app_config.ARROW_LENGTH
    far_y = near_y + normal_y * app_config.ARROW_LENGTH

    same_direction = (
        deviation.dx == normal_x
        and deviation.dy == normal_y
    )

    if same_direction:
        start_x, start_y = near_x, near_y
        end_x, end_y = far_x, far_y
    else:
        start_x, start_y = far_x, far_y
        end_x, end_y = near_x, near_y

    text_x = far_x + normal_x * app_config.TEXT_OFFSET
    text_y = far_y + normal_y * app_config.TEXT_OFFSET

    color = (
        app_config.TOP_COLOR
        if deviation.level == "В"
        else app_config.BOTTOM_COLOR
    )

    return Arrow(
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
        text_x=text_x,
        text_y=text_y,
        value_text=str(deviation.value_mm),
        level_text=deviation.level,
        color=color,
    )

def create_arrow(
    pylon,
    deviation: PointDeviation,
    axis_position: float,
    normal_x: int,
    normal_y: int,
) -> Arrow:
    """
    Создаёт стрелку для пилона.

    Сначала определяет точку проектной грани,
    затем использует универсальный построитель.
    """
    wall_x, wall_y = face_point(
        pylon=pylon,
        axis_position=axis_position,
        normal_x=normal_x,
        normal_y=normal_y,
    )

    arrow = create_arrow_from_anchor(
        anchor_x=wall_x,
        anchor_y=wall_y,
        deviation=deviation,
        normal_x=normal_x,
        normal_y=normal_y,
    )
    # Сохраняем владельца сразу при создании стрелки. Позже не нужно
    # угадывать принадлежность по близости координат.
    arrow.pylon_key = (
        pylon.center_x,
        pylon.center_y,
        pylon.length,
        pylon.width,
        pylon.orientation,
    )
    return arrow

def long_axis_coordinate(pylon, point) -> float:
    """
    Координата точки вдоль продольной оси пилона.
    """
    if pylon.orientation == "X":
        return point.x

    return point.y

def end_axis_coordinate(pylon, point) -> float:
    """
    Координата точки вдоль торцевой грани.
    """
    if pylon.orientation == "X":
        return point.y

    return point.x

def select_long_point_for_short_pylon(points: list[PointDeviation]) -> PointDeviation | None:
    """
    Выбирает одну точку длинной грани для короткого пилона.

    Если matcher нашёл две точки на одной длинной грани,
    берём точку с максимальным абсолютным отклонением.
    Это позволяет не потерять большее отклонение при переходе
    от двух виджетов к одному.
    """
    if not points:
        return None

    return max(
        points,
        key=lambda deviation: deviation.value_mm,
    )


def pair_axis_positions(
    pair_center: float,
    axis_is_horizontal: bool,
) -> tuple[float, float]:
    """
    Возвращает положения В и Н внутри пары.

    На горизонтальной грани:
    В слева, Н справа.

    На вертикальной грани:
    В сверху, Н снизу.
    """
    if axis_is_horizontal:
        upper_position = pair_center - app_config.PAIR_SPACING / 2
        lower_position = pair_center + app_config.PAIR_SPACING / 2
    else:
        upper_position = pair_center + app_config.PAIR_SPACING / 2
        lower_position = pair_center - app_config.PAIR_SPACING / 2

    return upper_position, lower_position

def generate_arrows(
    results: list[PylonDeviations],
) -> list[Arrow]:
    """
    Создаёт стрелки только для реально найденных точек.

    Обычный пилон:
    - 2 виджета (В/Н) на выбранной длинной грани;
    - 1 виджет (В/Н) на торце.

    Короткий пилон:
    - 1 виджет (В/Н) на длинной грани;
    - торцевой виджет не изменяется.

    Неполный пилон:
    - рисуются только существующие стрелки.
    """
    arrows: list[Arrow] = []

    for result in results:
        pylon = result.pylon

        # Для обычного пилона виджеты располагаются в двух четвертях.
        # Для короткого пилона — один виджет строго по центру длинной грани.
        is_short_pylon = (
            app_config.SHORT_PYLONS_ENABLED
            and pylon.length < app_config.SHORT_PYLON_MAX_LENGTH
        )

        if pylon.orientation == "X":
            if is_short_pylon:
                pair_centers = [pylon.center_x]
            else:
                pair_centers = [
                    pylon.center_x - pylon.length / 4,
                    pylon.center_x + pylon.length / 4,
                ]
        else:
            if is_short_pylon:
                pair_centers = [pylon.center_y]
            else:
                pair_centers = [
                    pylon.center_y - pylon.length / 4,
                    pylon.center_y + pylon.length / 4,
                ]

        # ------------------------------------------
        # Длинная сторона — верхние точки
        # ------------------------------------------

        upper_points = result.upper_long
        if is_short_pylon:
            selected_upper = select_long_point_for_short_pylon(
                upper_points
            )
            upper_points = (
                [selected_upper]
                if selected_upper is not None
                else []
            )

        for upper in upper_points:
            if is_short_pylon:
                pair_center = pair_centers[0]
            else:
                point_offset = long_axis_coordinate(
                    pylon,
                    upper.point,
                )

                pylon_center_axis = (
                    pylon.center_x
                    if pylon.orientation == "X"
                    else pylon.center_y
                )

                # Определяем, относится точка
                # к первой или второй четверти.
                slot_index = (
                    0
                    if point_offset < pylon_center_axis
                    else 1
                )

                pair_center = pair_centers[slot_index]

            normal_x, normal_y = nearest_long_face(
                pylon,
                upper.point,
            )

            upper_axis, _ = pair_axis_positions(
                pair_center=pair_center,
                axis_is_horizontal=(
                    pylon.orientation == "X"
                ),
            )

            arrows.append(
                create_arrow(
                    pylon=pylon,
                    deviation=upper,
                    axis_position=upper_axis,
                    normal_x=normal_x,
                    normal_y=normal_y,
                )
            )

        # ------------------------------------------
        # Длинная сторона — нижние точки
        # ------------------------------------------

        lower_points = result.lower_long
        if is_short_pylon:
            selected_lower = select_long_point_for_short_pylon(
                lower_points
            )
            lower_points = (
                [selected_lower]
                if selected_lower is not None
                else []
            )

        for lower in lower_points:
            if is_short_pylon:
                pair_center = pair_centers[0]
            else:
                point_offset = long_axis_coordinate(
                    pylon,
                    lower.point,
                )

                pylon_center_axis = (
                    pylon.center_x
                    if pylon.orientation == "X"
                    else pylon.center_y
                )

                slot_index = (
                    0
                    if point_offset < pylon_center_axis
                    else 1
                )

                pair_center = pair_centers[slot_index]

            normal_x, normal_y = nearest_long_face(
                pylon,
                lower.point,
            )

            _, lower_axis = pair_axis_positions(
                pair_center=pair_center,
                axis_is_horizontal=(
                    pylon.orientation == "X"
                ),
            )

            arrows.append(
                create_arrow(
                    pylon=pylon,
                    deviation=lower,
                    axis_position=lower_axis,
                    normal_x=normal_x,
                    normal_y=normal_y,
                )
            )

        # ------------------------------------------
        # Торец
        # ------------------------------------------

        # Центр торцевой грани берём от проекта,
        # а не от фактических точек.
        if pylon.orientation == "X":
            end_pair_center = pylon.center_y
        else:
            end_pair_center = pylon.center_x

        upper_end_axis, lower_end_axis = (
            pair_axis_positions(
                pair_center=end_pair_center,
                axis_is_horizontal=(
                    pylon.orientation == "Y"
                ),
            )
        )

        # Верхняяторцевая стрелка
        if result.upper_end is not None:
            normal_x, normal_y = nearest_end_face(
                pylon,
                result.upper_end.point,
            )

            arrows.append(
                create_arrow(
                    pylon=pylon,
                    deviation=result.upper_end,
                    axis_position=upper_end_axis,
                    normal_x=normal_x,
                    normal_y=normal_y,
                )
            )

        # Нижняя торцевая стрелка
        if result.lower_end is not None:
            normal_x, normal_y = nearest_end_face(
                pylon,
                result.lower_end.point,
            )

            arrows.append(
                create_arrow(
                    pylon=pylon,
                    deviation=result.lower_end,
                    axis_position=lower_end_axis,
                    normal_x=normal_x,
                    normal_y=normal_y,
                )
            )

    return arrows