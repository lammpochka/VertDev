from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path
from random import randint

import ezdxf
from ezdxf.enums import TextEntityAlignment

from core.arrows import Arrow
from core.pylon import Pylon
from core.wall import WallContour
from readers.survey_reader import SurveyPoint

from core.matcher import PylonDiagnostic, face_region_bounds

import config.config as app_config
DIAGNOSTIC_LAYER = "VERTDEV_DIAGNOSTIC"
SEARCH_AREA_LAYER = "search_area"
SURVEY_POINTS_LAYER = "survey_points"

DIM_LONG_PROJECT_LAYER = "VD_DIM_LONG_PROJECT"
DIM_LONG_FACT_LAYER = "VD_DIM_LONG_FACT"
DIM_END_PROJECT_LAYER = "VD_DIM_END_PROJECT"
DIM_END_FACT_LAYER = "VD_DIM_END_FACT"
DIMSTYLE_NAME = "VERTDEV_DIM"
LEVEL_LETTERS_LAYER = "VERTDEV_LEVELS"

DIAGNOSTIC_COLOR = 3
DIAGNOSTIC_LINEWEIGHT = 50

COLOR_OK = 3          # зелёный
COLOR_MISSING = 1     # красный
COLOR_EXTRA = 2       # желтый (совпадает с WARNING_COLOR)

WARNING_COLOR = 2

# Отступ рамки примерно равен полному размеру
# одного виджета отклонения.
def diagnostic_text_height() -> float:
    return app_config.TEXT_HEIGHT * 1.5


def diagnostic_offset() -> float:
    return (
        app_config.WALL_OFFSET
        + app_config.ARROW_LENGTH
        + app_config.TEXT_OFFSET
        + app_config.TEXT_HEIGHT * 4 * 0.7
    )


def diagnostic_number_gap() -> float:
    return app_config.TEXT_HEIGHT

def select_text_style(document) -> str:
    """
    Возвращает выбранный текстовый стиль.

    Если нужного стиля в DXF нет,
    используется обязательный стиль Standard.
    """
    if app_config.TEXT_STYLE in document.styles:
        return app_config.TEXT_STYLE

    return "Standard"

def ensure_output_layer(document) -> None:
    """
    Создаёт слой результата, если такого слоя ещё нет.
    """
    if app_config.OUTPUT_LAYER not in document.layers:
        document.layers.add(
            app_config.OUTPUT_LAYER,
            color=7,
            linetype="CONTINUOUS",
        )

def ensure_level_letters_layer(document) -> None:
    """Создаёт отдельный слой для букв В/Н у стрелок отклонений."""
    if LEVEL_LETTERS_LAYER not in document.layers:
        document.layers.add(
            LEVEL_LETTERS_LAYER,
            color=7,
            linetype="CONTINUOUS",
        )

def ensure_diagnostic_layer(document) -> None:
    """
    Создаёт служебный слой диагностики.
    """
    if DIAGNOSTIC_LAYER not in document.layers:
        document.layers.add(
            DIAGNOSTIC_LAYER,
            color=DIAGNOSTIC_COLOR,
            linetype="CONTINUOUS",
            lineweight=DIAGNOSTIC_LINEWEIGHT,
        )

def ensure_search_area_layer(document) -> None:
    """
    Создаёт слой зон поиска соответствий.
    """
    if SEARCH_AREA_LAYER not in document.layers:
        document.layers.add(
            SEARCH_AREA_LAYER,
            color=6,
            linetype="CONTINUOUS",
            lineweight=25,
        )

def ensure_survey_points_layer(document) -> None:
    """Создаёт отдельный слой для визуализации всех точек съёмки."""
    if SURVEY_POINTS_LAYER not in document.layers:
        document.layers.add(
            SURVEY_POINTS_LAYER,
            color=4,
            linetype="CONTINUOUS",
        )

def arrow_direction(arrow: Arrow) -> tuple[float, float]:
    """
    Возвращает единичный вектор от начала стрелки
    к её наконечнику.
    """
    dx = arrow.end_x - arrow.start_x
    dy = arrow.end_y - arrow.start_y

    length = hypot(dx, dy)

    if length == 0:
        raise ValueError("Стрелка имеет нулевую длину.")

    return dx / length, dy / length

def outward_direction(arrow: Arrow) -> tuple[float, float]:
    """
    Определяет направление от пилона наружу.

    text_x и text_y всегда находятся с наружной стороны,
    независимо от направления наконечника.
    """
    reference_x = (arrow.start_x + arrow.end_x) / 2
    reference_y = (arrow.start_y + arrow.end_y) / 2

    dx = arrow.text_x - reference_x
    dy = arrow.text_y - reference_y

    length = hypot(dx, dy)

    if length == 0:
        return arrow_direction(arrow)

    return dx / length, dy / length

def text_rotation(arrow: Arrow) -> float:
    """
    Текст располагается вдоль линии оформления.

    Горизонтальные стрелки: 0 градусов.
    Вертикальные стрелки: 90 градусов.
    """
    outward_x, outward_y = outward_direction(arrow)

    angle = degrees(atan2(outward_y, outward_x))

    # Не допускаем перевёрнутого текста.
    if angle > 90:
        angle -= 180
    elif angle <= -90:
        angle += 180

    return angle

def estimated_text_length(text: str) -> float:
    """
    Приблизительная длина однострочного текста.

    Нужна только для размещения буквы после числа.
    """
    
    #return max(len(text), 1) * app_config.TEXT_HEIGHT * 0.65
    return 0.17


def draw_text_parts(modelspace, arrow: Arrow, text_style: str) -> None:
    """
    Рисует число и букву отдельными объектами.

    Текст размещается от стрелки наружу независимо
    от того, куда направлена стрелка.
    """
    outward_x, outward_y = outward_direction(arrow)
    rotation = text_rotation(arrow)

    value_length = estimated_text_length(
        arrow.value_text
    )

    level_length = estimated_text_length(
        arrow.level_text
    )

    # arrow.text_x/text_y — начало текстовой зоны
    # сразу после стрелки.
    value_center_x = (
        arrow.text_x
        + outward_x * value_length / 2
    )

    value_center_y = (
        arrow.text_y
        + outward_y * value_length / 2
    )

    level_center_x = (
        arrow.text_x
        + outward_x
        * (
            value_length
            + app_config.VALUE_LEVEL_GAP
            + level_length / 2
        )
    )

    level_center_y = (
        arrow.text_y
        + outward_y
        * (
            value_length
            + app_config.VALUE_LEVEL_GAP
            + level_length / 2
        )
    )

    attributes = {
        "height": app_config.TEXT_HEIGHT,
        "rotation": rotation,
        "layer": app_config.OUTPUT_LAYER,
        "color": arrow.color,
        "style": text_style,
    }

    value_entity = modelspace.add_text(
        arrow.value_text,
        dxfattribs=attributes,
    )

    value_entity.set_placement(
        (value_center_x, value_center_y),
        align=TextEntityAlignment.MIDDLE_CENTER,
    )

    level_attributes = dict(attributes)
    level_attributes["layer"] = LEVEL_LETTERS_LAYER
    level_entity = modelspace.add_text(
        arrow.level_text,
        dxfattribs=level_attributes,
    )

    level_entity.set_placement(
        (level_center_x, level_center_y),
        align=TextEntityAlignment.MIDDLE_CENTER,
    )
def draw_outline_arrow(
    modelspace,
    arrow: Arrow,
) -> None:
    """
    Рисует тонкую контурную стрелку с острым наконечником.

    Внешние углы наконечника уходят назад,
    за основание треугольника.
    """

    direction_x, direction_y = arrow_direction(arrow)

    # Перпендикуляр к направлению стрелки.
    perpendicular_x = -direction_y
    perpendicular_y = direction_x

    # Ширина тела стрелки.
    body_half_width = app_config.ARROW_BODY_WIDTH / 2

    # Половина ширины наконечника.
    head_half_width = app_config.ARROW_SIZE * 0.42

    # Насколько основание наконечника уходит назад
    # относительно его условного треугольника.
    back_offset = app_config.ARROW_SIZE * 0.30

    # Основание наконечника.
    base_x = (
        arrow.end_x
        - direction_x * app_config.ARROW_SIZE * 2.2
    )
    base_y = (
        arrow.end_y
        - direction_y * app_config.ARROW_SIZE * 2.2
    )

    # Точки, куда уходят внешние углы наконечника.
    #
    # Они находятся ЗА основанием треугольника,
    # то есть ближе к хвосту стрелки.
    corner_center_x = (
        base_x
        - direction_x * back_offset
    )
    corner_center_y = (
        base_y
        - direction_y * back_offset
    )

    # Хвост стрелки.
    tail_left = (
        arrow.start_x
        + perpendicular_x * body_half_width,
        arrow.start_y
        + perpendicular_y * body_half_width,
    )

    tail_right = (
        arrow.start_x
        - perpendicular_x * body_half_width,
        arrow.start_y
        - perpendicular_y * body_half_width,
    )

    # Место, где тело стрелки соединяется
    # с наконечником.
    neck_left = (
        base_x
        + perpendicular_x * body_half_width,
        base_y
        + perpendicular_y * body_half_width,
    )

    neck_right = (
        base_x
        - perpendicular_x * body_half_width,
        base_y
        - perpendicular_y * body_half_width,
    )

    # Внешние углы наконечника.
    head_left = (
        corner_center_x
        + perpendicular_x * head_half_width,
        corner_center_y
        + perpendicular_y * head_half_width,
    )

    head_right = (
        corner_center_x
        - perpendicular_x * head_half_width,
        corner_center_y
        - perpendicular_y * head_half_width,
    )

    # Остриё.
    tip = (
        arrow.end_x,
        arrow.end_y,
    )

    points = [
        tail_left,
        neck_left,
        head_left,
        tip,
        head_right,
        neck_right,
        tail_right,
    ]

    modelspace.add_lwpolyline(
        points,
        close=True,
        dxfattribs={
            "layer": app_config.OUTPUT_LAYER,
            "color": arrow.color,
        },
    )
def draw_arrow(
    modelspace,
    arrow: Arrow,
    text_style: str,
) -> None:
    draw_outline_arrow(modelspace, arrow)

    draw_text_parts(
        modelspace,
        arrow,
        text_style,
    )

def pylon_frame_bounds(
    pylon: Pylon,
    offset: float | None = None,
) -> tuple[float, float, float, float]:
    """
    Возвращает границы диагностической рамки:

    min_x, min_y, max_x, max_y.
    """
    if offset is None:
        offset = diagnostic_offset()

    if pylon.orientation == "X":
        size_x = pylon.length
        size_y = pylon.width
    else:
        size_x = pylon.width
        size_y = pylon.length

    half_x = size_x / 2
    half_y = size_y / 2

    min_x = pylon.center_x - half_x - offset
    max_x = pylon.center_x + half_x + offset

    min_y = pylon.center_y - half_y - offset
    max_y = pylon.center_y + half_y + offset

    return min_x, min_y, max_x, max_y

def draw_pylon_diagnostic_frame(
    modelspace,
    pylon: Pylon,
    number: int,
    color: int,           # <-- теперь передаём цвет напрямую
    text_style: str,
) -> None:
    """
    Рисует диагностическую рамку вокруг пилона
    и его номер внутри левого верхнего угла.
    """
    min_x, min_y, max_x, max_y = pylon_frame_bounds(pylon)

    frame_points = [
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    ]

    modelspace.add_lwpolyline(
        frame_points,
        close=True,
        dxfattribs={
            "layer": DIAGNOSTIC_LAYER,
            "color": color,
            "lineweight": DIAGNOSTIC_LINEWEIGHT,
        },
    )

    number_x = min_x + diagnostic_number_gap()
    number_y = max_y - diagnostic_number_gap()

    number_entity = modelspace.add_text(
        str(number),
        dxfattribs={
            "height": diagnostic_text_height(),
            "layer": DIAGNOSTIC_LAYER,
            "color": color,
            "style": text_style,
        },
    )

    number_entity.set_placement(
        (number_x, number_y),
        align=TextEntityAlignment.TOP_LEFT,
    )

def draw_search_area_frame(
    modelspace,
    pylon: Pylon,
    face_type: str,
    face_key: int,
) -> None:
    """
    Рисует прямоугольную зону поиска соответствий
    вокруг одной грани пилона.
    """
    min_x, max_x, min_y, max_y = face_region_bounds(
        pylon,
        face_type,
        face_key,
    )

    points = [
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
    ]

    modelspace.add_lwpolyline(
        points,
        close=True,
        dxfattribs={
            "layer": SEARCH_AREA_LAYER,
            "color": 6,
            "lineweight": 25,
        },
    )


def draw_pylon_search_areas(
    modelspace,
    pylon: Pylon,
) -> None:
    """Рисует все четыре зоны поиска одного пилона."""
    for face_type in ("long", "end"):
        for face_key in (-1, 1):
            draw_search_area_frame(
                modelspace,
                pylon,
                face_type,
                face_key,
            )




def ensure_dimension_layers(document) -> None:
    """Создаёт четыре отдельных слоя для проектных и фактических размеров."""
    layers = (
        DIM_LONG_PROJECT_LAYER,
        DIM_LONG_FACT_LAYER,
        DIM_END_PROJECT_LAYER,
        DIM_END_FACT_LAYER,
    )
    for layer_name in layers:
        if layer_name not in document.layers:
            document.layers.add(
                layer_name,
                color=7,
                linetype="CONTINUOUS",
            )


def _copy_table_entry(target_table, source_entry, name: str | None = None):
    """Копирует табличную запись ezdxf без handle/owner."""
    attrs = source_entry.dxfattribs().copy()
    attrs.pop("handle", None)
    attrs.pop("owner", None)
    if name is not None:
        attrs["name"] = name
    entry_name = name or source_entry.dxf.name

    if entry_name in target_table:
        return target_table.get(entry_name)

    return target_table.add(entry_name, dxfattribs=attrs)


def import_dimension_style(document, etalon_path: str, style_name: str) -> str:
    """
    Импортирует указанный DIMSTYLE из эталонного DXF.

    Также подтягивает используемый им текстовый стиль и типы линий,
    если их нет в результирующем документе.
    """
    if not etalon_path:
        raise ValueError("Не выбран эталонный DXF с размером.")

    path = Path(etalon_path)
    if not path.is_absolute():
        path = app_config.PROJECT_ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"Эталонный DXF не найден: {path}")

    source = ezdxf.readfile(path)

    requested_name = (style_name or "").strip()
    if not requested_name:
        raise ValueError("Не указано имя размерного стиля в эталонном DXF.")

    source_style = next(
        (style for style in source.dimstyles
         if style.dxf.name.upper() == requested_name.upper()),
        None,
    )
    if source_style is None:
        raise ValueError(
            f"В эталонном DXF не найден размерный стиль «{requested_name}»."
        )
    style_name = source_style.dxf.name

    # Копируем текстовый стиль, на который ссылается DIMSTYLE.
    text_style_name = source_style.dxf.get("dimtxsty", "Standard")
    if text_style_name in source.styles:
        _copy_table_entry(document.styles, source.styles.get(text_style_name))

    # Копируем используемые типы линий, если они заданы именами.
    for attr_name in ("dimltype", "dimltex1", "dimltex2"):
        ltype_name = source_style.dxf.get(attr_name, "")
        if ltype_name and ltype_name in source.linetypes:
            _copy_table_entry(
                document.linetypes,
                source.linetypes.get(ltype_name),
            )

    if style_name in document.dimstyles:
        # Эталонный стиль уже мог быть перенесён ранее.
        return style_name

    _copy_table_entry(document.dimstyles, source_style)
    return style_name


def _pylon_bounds(pylon: Pylon) -> tuple[float, float, float, float]:
    """Возвращает min_x, min_y, max_x, max_y для неповернутого пилона."""
    half_x = (pylon.length if pylon.orientation == "X" else pylon.width) / 2
    half_y = (pylon.width if pylon.orientation == "X" else pylon.length) / 2
    return (
        pylon.center_x - half_x,
        pylon.center_y - half_y,
        pylon.center_x + half_x,
        pylon.center_y + half_y,
    )


def _dimension_geometry(
    pylon: Pylon,
    kind: str,
    side_sign: int = 1,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float], float]:
    """Возвращает точки измерения и положение размерной линии.

    side_sign задаёт сторону нормали: +1 — вверх/вправо, -1 — вниз/влево.
    Для длинного размера обе точки лежат именно на выбранной длинной грани.
    """
    min_x, min_y, max_x, max_y = _pylon_bounds(pylon)
    offset = app_config.TEXT_HEIGHT * 2.0

    if kind == "long":
        if pylon.orientation == "X":
            y = pylon.center_y + side_sign * (max_y - min_y) / 2
            p1 = (min_x, y)
            p2 = (max_x, y)
            location = (pylon.center_x, y + side_sign * offset)
            angle = 0.0
        else:
            x = pylon.center_x + side_sign * (max_x - min_x) / 2
            p1 = (x, min_y)
            p2 = (x, max_y)
            location = (x + side_sign * offset, pylon.center_y)
            angle = 90.0
    else:
        # Для торцевого размера side_sign выбирает конкретный торец пилона:
        # +1 — правая/верхняя грань, -1 — левая/нижняя.
        if pylon.orientation == "X":
            edge_x = max_x if side_sign > 0 else min_x
            p1 = (edge_x, min_y)
            p2 = (edge_x, max_y)
            location = (edge_x + side_sign * offset, pylon.center_y)
            angle = 90.0
        else:
            edge_y = max_y if side_sign > 0 else min_y
            p1 = (min_x, edge_y)
            p2 = (max_x, edge_y)
            location = (pylon.center_x, edge_y + side_sign * offset)
            angle = 0.0

    return p1, p2, location, angle


def _dimension_project_mm(pylon: Pylon, kind: str) -> int:
    value_m = pylon.length if kind == "long" else pylon.width
    return int(round(value_m * 1000))


def _dimension_actual_mm(project_mm: int, pylon: Pylon, kind: str,
                         dimension_values: dict | None = None,
                         dimension_deviation_means: dict | None = None,
                         dimension_diagnostics: list | None = None) -> int:
    """Определяет размер и сохраняет подробную диагностику выбора значения."""
    key = (round(float(pylon.center_x), 4), round(float(pylon.center_y), 4))
    means = (dimension_deviation_means or {}).get(key, {})
    mean_deviation = float(means.get(kind, 0.0))
    values = dimension_values or {}
    entry = values.get(key, {})
    raw = entry.get(kind, "") if isinstance(entry, dict) else ""
    record = {
        "pylon_x": float(pylon.center_x),
        "pylon_y": float(pylon.center_y),
        "kind": kind,
        "project_mm": int(project_mm),
        "generation_enabled": bool(app_config.TOLERANCE_GENERATION_ENABLED),
        "signed_deviations": list(means.get(f"{kind}_values", [])),
        "mean_deviation": mean_deviation,
        "manual_value": str(raw),
    }
    if app_config.TOLERANCE_GENERATION_ENABLED:
        if kind == "long":
            minimum = app_config.DIMENSION_LONG_RANDOM_MIN_MM
            maximum = app_config.DIMENSION_LONG_RANDOM_MAX_MM
        else:
            minimum = app_config.DIMENSION_END_RANDOM_MIN_MM
            maximum = app_config.DIMENSION_END_RANDOM_MAX_MM
        if mean_deviation < 0:
            low, high = min(minimum, 0), 0
        elif mean_deviation > 0:
            low, high = 0, max(maximum, 0)
        else:
            low = high = 0
        offset = randint(low, high)
        actual = project_mm + offset
        record.update({"random_range": f"{low}..{high}", "offset_mm": offset, "actual_mm": actual})
    else:
        try:
            actual = int(round(float(raw))) if str(raw).strip() else project_mm
        except (TypeError, ValueError):
            actual = project_mm
        record.update({"random_range": "не применяется", "offset_mm": actual - project_mm,
                       "actual_mm": actual, "manual_fallback": not bool(str(raw).strip())})
    if dimension_diagnostics is not None:
        dimension_diagnostics.append(record)
    return actual


def _box_intersects(a: tuple[float, float, float, float],
                    b: tuple[float, float, float, float]) -> bool:
    """Пересечение двух осевых прямоугольников (касание тоже считается)."""
    return not (
        a[2] < b[0] or b[2] < a[0]
        or a[3] < b[1] or b[3] < a[1]
    )


def _expanded_box(points: list[tuple[float, float]], padding_ratio: float = 0.0
                  ) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad_x = (max_x - min_x) * padding_ratio
    pad_y = (max_y - min_y) * padding_ratio
    return min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y


def _arrow_collision_box(arrow: Arrow) -> tuple[float, float, float, float]:
    """Коллизия виджета: стрелка + число + буква, с запасом 5%."""
    out_x, out_y = outward_direction(arrow)
    perp_x, perp_y = -out_y, out_x
    value_len = estimated_text_length(arrow.value_text)
    level_len = estimated_text_length(arrow.level_text)
    text_len = value_len + app_config.VALUE_LEVEL_GAP + level_len
    text_end_x = arrow.text_x + out_x * text_len
    text_end_y = arrow.text_y + out_y * text_len
    half_h = app_config.TEXT_HEIGHT / 2
    points = [
        (arrow.start_x, arrow.start_y),
        (arrow.end_x, arrow.end_y),
        (arrow.text_x + perp_x * half_h, arrow.text_y + perp_y * half_h),
        (arrow.text_x - perp_x * half_h, arrow.text_y - perp_y * half_h),
        (text_end_x + perp_x * half_h, text_end_y + perp_y * half_h),
        (text_end_x - perp_x * half_h, text_end_y - perp_y * half_h),
    ]
    return _expanded_box(points, 0.05)


def _dimension_collision_box(
    pylon: Pylon,
    kind: str,
    side_sign: int,
    distance: float,
    project_mm: int,
    actual_mm: int,
    reverse: bool = False,
) -> tuple[float, float, float, float]:
    """Только текст размера: высота 3H, длина текста + 15%."""
    p1, p2, _location, _angle = _dimension_geometry(pylon, kind, side_sign)
    if reverse:
        p1, p2 = p2, p1
    center_x = (p1[0] + p2[0]) / 2
    center_y = (p1[1] + p2[1]) / 2

    # Нормаль в координатах XY. Для p1->p2 слева направо она направлена вверх;
    # для p1->p2 снизу вверх — влево.
    if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]):
        normal_x, normal_y = 0.0, float(side_sign)
    else:
        normal_x, normal_y = float(side_sign), 0.0
    center_x += normal_x * distance
    center_y += normal_y * distance

    # Смещение текста торцевого размера вдоль размерной линии учитываем
    # и при вычислении области коллизии.
    if kind == "end":
        text_shift = 0.420
        axis_dx = p2[0] - p1[0]
        axis_dy = p2[1] - p1[1]
        axis_length = hypot(axis_dx, axis_dy)
        if axis_length > 0:
            center_x += axis_dx / axis_length * text_shift
            center_y += axis_dy / axis_length * text_shift

    text_height = app_config.TEXT_HEIGHT
    text_length = max(len(str(project_mm)), len(str(actual_mm))) * text_height * 0.65
    text_length *= 1.15
    half_length = text_length / 2
    half_height = text_height * 1.5

    if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]):
        return (
            center_x - half_length, center_y - half_height,
            center_x + half_length, center_y + half_height,
        )
    return (
        center_x - half_height, center_y - half_length,
        center_x + half_height, center_y + half_length,
    )


def _ray_segment_intersects(
    origin: tuple[float, float],
    direction: tuple[float, float],
    max_length: float,
    a: tuple[float, float],
    b: tuple[float, float],
) -> bool:
    """Проверяет пересечение конечного луча с отрезком контура."""
    ox, oy = origin
    dx, dy = direction
    sx, sy = b[0] - a[0], b[1] - a[1]
    denom = dx * sy - dy * sx
    if abs(denom) < 1e-10:
        return False
    qx, qy = a[0] - ox, a[1] - oy
    t = (qx * sy - qy * sx) / denom
    u = (qx * dy - qy * dx) / denom
    return -1e-9 <= t <= max_length + 1e-9 and -1e-9 <= u <= 1.0 + 1e-9


def _side_has_pylon_in_ray_fan(
    pylon: Pylon,
    side_sign: int,
    all_pylons: list[Pylon],
    wall_contours: list[WallContour] | None = None,
) -> bool:
    """Сторона внутренняя, если хотя бы один луч пересекает контур другого пилона."""
    min_x, min_y, max_x, max_y = _pylon_bounds(pylon)
    if pylon.orientation == "X":
        origin = (pylon.center_x, pylon.center_y + side_sign * (max_y - min_y) / 2)
        base_angle = 90.0 if side_sign > 0 else -90.0
    else:
        origin = (pylon.center_x + side_sign * (max_x - min_x) / 2, pylon.center_y)
        base_angle = 0.0 if side_sign > 0 else 180.0

    ray_count = max(1, int(app_config.DIMENSION_RAY_COUNT))
    ray_length = float(app_config.DIMENSION_RAY_LENGTH_M)
    if ray_count == 1:
        angles = [0.0]
    else:
        angles = [-45.0 + 90.0 * i / (ray_count - 1) for i in range(ray_count)]

    for delta in angles:
        angle = radians(base_angle + delta)
        direction = (cos(angle), sin(angle))
        for other in all_pylons:
            if other is pylon:
                continue
            ox1, oy1, ox2, oy2 = _pylon_bounds(other)
            contour = [
                ((ox1, oy1), (ox2, oy1)),
                ((ox2, oy1), (ox2, oy2)),
                ((ox2, oy2), (ox1, oy2)),
                ((ox1, oy2), (ox1, oy1)),
            ]
            if any(
                _ray_segment_intersects(origin, direction, ray_length, a, b)
                for a, b in contour
            ):
                return True
        # Проверяем также реальные сегменты стен.
        for wall in wall_contours or []:
            for segment in wall.segments:
                a = (segment.start_x, segment.start_y)
                b = (segment.end_x, segment.end_y)
                if _ray_segment_intersects(origin, direction, ray_length, a, b):
                    return True
    return False


def _end_side_has_pylon_in_ray_fan(
    pylon: Pylon,
    side_sign: int,
    all_pylons: list[Pylon],
    wall_contours: list[WallContour] | None = None,
) -> bool:
    """Проверяет сторону торцевого размера лучами от выбранного торца."""
    min_x, min_y, max_x, max_y = _pylon_bounds(pylon)
    if pylon.orientation == "X":
        # Начинаем именно с того торца, который проверяем.
        edge_x = max_x if side_sign > 0 else min_x
        origin = (edge_x, pylon.center_y)
        base_angle = 0.0 if side_sign > 0 else 180.0
    else:
        # Для ориентации Y проверяем верхний или нижний торец соответственно.
        edge_y = max_y if side_sign > 0 else min_y
        origin = (pylon.center_x, edge_y)
        base_angle = 90.0 if side_sign > 0 else -90.0

    ray_count = max(1, int(app_config.DIMENSION_RAY_COUNT))
    ray_length = float(app_config.DIMENSION_RAY_LENGTH_M)
    if ray_count == 1:
        angles = [0.0]
    else:
        angles = [-45.0 + 90.0 * i / (ray_count - 1) for i in range(ray_count)]

    for delta in angles:
        angle = radians(base_angle + delta)
        direction = (cos(angle), sin(angle))
        for other in all_pylons:
            if other is pylon:
                continue
            ox1, oy1, ox2, oy2 = _pylon_bounds(other)
            contour = [
                ((ox1, oy1), (ox2, oy1)),
                ((ox2, oy1), (ox2, oy2)),
                ((ox2, oy2), (ox1, oy2)),
                ((ox1, oy2), (ox1, oy1)),
            ]
            if any(_ray_segment_intersects(origin, direction, ray_length, a, b) for a, b in contour):
                return True
        # Проверяем также реальные сегменты стен.
        for wall in wall_contours or []:
            for segment in wall.segments:
                a = (segment.start_x, segment.start_y)
                b = (segment.end_x, segment.end_y)
                if _ray_segment_intersects(origin, direction, ray_length, a, b):
                    return True
    return False


def _draw_dimension_pair(
    modelspace,
    pylon: Pylon,
    kind: str,
    dimstyle: str,
    side_sign: int,
    distance: float,
    project_mm: int,
    actual_mm: int,
    red: bool = False,
    reverse: bool = False,
) -> None:
    p1, p2, _location, _angle = _dimension_geometry(pylon, kind, side_sign)
    if reverse:
        p1, p2 = p2, p1
    # add_aligned_dim: положительное расстояние направлено влево от p1->p2.
    # Для горизонтального отрезка это вверх; для вертикального снизу вверх — влево.
    direction_sign = -1 if reverse else 1
    if abs(p2[0] - p1[0]) >= abs(p2[1] - p1[1]):
        signed_distance = distance * side_sign * direction_sign
    else:
        signed_distance = -distance * side_sign * direction_sign
    color = 1 if red else 256  # 256 = BYLAYER
    project_layer = DIM_LONG_PROJECT_LAYER if kind == "long" else DIM_END_PROJECT_LAYER
    fact_layer = DIM_LONG_FACT_LAYER if kind == "long" else DIM_END_FACT_LAYER

    project_dim = modelspace.add_aligned_dim(
        p1=p1, p2=p2, distance=signed_distance, text="<>", dimstyle=dimstyle,
        dxfattribs={"layer": project_layer, "color": color},
    )
    project_dim.render()
    fact_dim = modelspace.add_aligned_dim(
        p1=p1, p2=p2, distance=signed_distance, text=rf"\X{actual_mm}", dimstyle=dimstyle,
        dxfattribs={"layer": fact_layer, "color": color},
    )
    fact_dim.render()


def _find_free_long_dimension_position(
    pylon: Pylon,
    side_sign: int,
    project_mm: int,
    actual_mm: int,
    occupied_boxes: list[tuple[float, float, float, float]],
) -> float | None:
    """Ищет свободное место от 2H до максимального отступа включительно."""
    step = float(app_config.DIMENSION_SEARCH_STEP_M)
    max_distance = float(app_config.DIMENSION_SEARCH_MAX_DISTANCE_M)
    initial = float(app_config.DIMENSION_SEARCH_INITIAL_OFFSET_M)
    if step <= 0 or max_distance < initial:
        return None

    distance = initial
    while distance <= max_distance + 1e-9:
        candidate = _dimension_collision_box(
            pylon, "long", side_sign, distance, project_mm, actual_mm
        )
        if not any(_box_intersects(candidate, box) for box in occupied_boxes):
            return distance
        distance += step
    return None


def draw_pylon_long_dimension(
    modelspace,
    pylon: Pylon,
    dimstyle: str,
    all_pylons: list[Pylon],
    occupied_boxes: list[tuple[float, float, float, float]],
    wall_contours: list[WallContour] | None = None,
    dimension_values: dict | None = None,
    dimension_deviation_means: dict | None = None,
    dimension_diagnostics: list | None = None,
) -> None:
    """Размещает длинный размер с проверкой допустимой стороны и коллизий."""
    project_long = _dimension_project_mm(pylon, "long")
    actual_long = _dimension_actual_mm(project_long, pylon, "long", dimension_values, dimension_deviation_means, dimension_diagnostics)
    allowed = {
        side: _side_has_pylon_in_ray_fan(pylon, side, all_pylons, wall_contours)
        for side in (1, -1)
    }

    chosen_side = None
    chosen_distance = None
    red = False

    # Цвет размера показывает именно проблему размещения, а не результат
    # эвристики определения внутренней/внешней стороны. Если лучи не нашли
    # соседей ни с одной стороны, всё равно пробуем обе стороны на коллизии.
    preferred_sides = [side for side in (1, -1) if allowed[side]]
    sides_to_try = preferred_sides or [1, -1]
    first_side, second_side = sides_to_try[0], sides_to_try[-1]
    initial_distance = float(app_config.DIMENSION_SEARCH_INITIAL_OFFSET_M)

    for side in sides_to_try:
        box = _dimension_collision_box(
            pylon, "long", side, initial_distance, project_long, actual_long
        )
        if not any(_box_intersects(box, occupied) for occupied in occupied_boxes):
            chosen_side, chosen_distance = side, initial_distance
            break

    # Если начальные позиции заняты, ищем свободное место дальше от пилона.
    if chosen_side is None:
        for side in sides_to_try:
            distance = _find_free_long_dimension_position(
                pylon, side, project_long, actual_long, occupied_boxes
            )
            if distance is not None:
                chosen_side, chosen_distance = side, distance
                break

    if chosen_side is None:
        # Свободного места не найдено — размер действительно проблемный.
        chosen_side = first_side
        chosen_distance = float(app_config.DIMENSION_SEARCH_MAX_DISTANCE_M)
        red = True

    _draw_dimension_pair(
        modelspace, pylon, "long", dimstyle, chosen_side,
        float(chosen_distance), project_long, actual_long, red=red,
    )
    occupied_boxes.append(_dimension_collision_box(
        pylon, "long", chosen_side, float(chosen_distance),
        project_long, actual_long,
    ))



def _move_end_widgets_to_special_position(
    pylon: Pylon,
    arrows: list[Arrow],
    occupied_boxes: list[tuple[float, float, float, float]],
    side_sign: int,
) -> bool:
    """Сдвигает пару торцевых виджетов на половину расстояния между стрелками.

    Перемещение зависит от взаимного расстояния стрелок, а не от их абсолютных
    координат относительно центра пилона, чтобы исключить многометровые скачки.
    """
    min_x, min_y, max_x, max_y = _pylon_bounds(pylon)
    edge_x = max_x if side_sign > 0 else min_x
    edge_y = max_y if side_sign > 0 else min_y
    candidates = []
    tolerance = max(app_config.WALL_OFFSET + app_config.ARROW_LENGTH + 0.1, 0.5)
    pylon_key = (
        pylon.center_x,
        pylon.center_y,
        pylon.length,
        pylon.width,
        pylon.orientation,
    )

    for index, arrow in enumerate(arrows):
        # Не ищем подходящие по координатам стрелки соседних пилонов.
        if arrow.pylon_key != pylon_key:
            continue
        nx, ny = outward_direction(arrow)
        if pylon.orientation == "X":
            if abs(nx) < 0.8:
                continue
            ref_x = (arrow.start_x + arrow.end_x) / 2
            if abs(ref_x - edge_x) <= tolerance:
                candidates.append((abs(arrow.start_y - pylon.center_y), index, arrow, "x"))
        else:
            if abs(ny) < 0.8:
                continue
            ref_y = (arrow.start_y + arrow.end_y) / 2
            if abs(ref_y - edge_y) <= tolerance:
                candidates.append((abs(arrow.start_x - pylon.center_x), index, arrow, "y"))

    if len(candidates) < 2:
        return False

    candidates.sort(key=lambda item: item[0])
    pair = candidates[:2]
    axis = pair[0][3]
    if pair[1][3] != axis:
        return False

    coords = [arrow.start_y if axis == "x" else arrow.start_x
              for _distance, _index, arrow, _axis in pair]
    separation = abs(coords[1] - coords[0])
    if separation <= 1e-9:
        return False

    midpoint = (coords[0] + coords[1]) / 2
    center = pylon.center_y if axis == "x" else pylon.center_x
    direction = 1.0 if center > midpoint else -1.0
    shift = direction * separation / 2


    for _distance, index, arrow, _axis in pair:
        if axis == "x":
            arrow.start_y += shift
            arrow.end_y += shift
            arrow.text_y += shift
        else:
            arrow.start_x += shift
            arrow.end_x += shift
            arrow.text_x += shift
        if index < len(occupied_boxes):
            occupied_boxes[index] = _arrow_collision_box(arrow)
    return True


def draw_pylon_end_dimension(
    modelspace,
    pylon: Pylon,
    dimstyle: str,
    occupied_boxes: list[tuple[float, float, float, float]],
    arrows: list[Arrow],
    all_pylons: list[Pylon],
    wall_contours: list[WallContour] | None = None,
    dimension_values: dict | None = None,
    dimension_deviation_means: dict | None = None,
    dimension_diagnostics: list | None = None,
) -> None:
    """Ищет место для торцевого размера; при крайнем конфликте сдвигает торцевые виджеты."""
    project_end = _dimension_project_mm(pylon, "end")
    actual_end = _dimension_actual_mm(project_end, pylon, "end", dimension_values, dimension_deviation_means, dimension_diagnostics)
    # Базовый отступ общий для торцевых и длинных размеров.
    initial = float(app_config.DIMENSION_SEARCH_INITIAL_OFFSET_M)
    step = float(app_config.DIMENSION_SEARCH_STEP_M)
    max_distance = float(app_config.DIMENSION_SEARCH_MAX_DISTANCE_M)

    # Сначала предпочитаем сторону, которую лучи определили как внутреннюю.
    sides_by_priority = [1, -1]
    allowed = {
        side: _end_side_has_pylon_in_ray_fan(pylon, side, all_pylons, wall_contours)
        for side in sides_by_priority
    }
    eligible_sides = [side for side in sides_by_priority if allowed[side]]
    # Цвет показывает проблему размещения. Отсутствие найденной лучами
    # внутренней стороны само по себе не делает размер красным.
    red = False
    sides_to_try = eligible_sides or sides_by_priority
    chosen_side = None
    chosen_distance = None

    # Если доступна только одна сторона и на ней мешают именно виджеты,
    # сразу освобождаем торец и увеличиваем отступ размера на 88% длины виджета.
    if len(sides_to_try) == 1 and eligible_sides:
        only_side = sides_to_try[0]
        standard_box = _dimension_collision_box(
            pylon, "end", only_side, initial, project_end, actual_end
        )
        widget_conflict = any(
            _box_intersects(standard_box, _arrow_collision_box(arrow))
            for arrow in arrows
        )
        if widget_conflict:
            import logging
            moved = _move_end_widgets_to_special_position(
                pylon, arrows, occupied_boxes, only_side
            )
            if moved:
                chosen_side = only_side
                chosen_distance = initial + diagnostic_offset() * 0.88

    # Сначала проверяем стандартный отступ на допустимых сторонах.
    for side in sides_to_try:
        box = _dimension_collision_box(pylon, "end", side, initial, project_end, actual_end)
        if not any(_box_intersects(box, occupied) for occupied in occupied_boxes):
            chosen_side, chosen_distance = side, initial
            break

    # Затем увеличиваем отступ по той же сетке, что и для длинных размеров.
    if chosen_side is None and step > 0 and max_distance >= initial:
        for side in sides_to_try:
            distance = initial + step
            while distance <= max_distance + 1e-9:
                box = _dimension_collision_box(pylon, "end", side, distance, project_end, actual_end)
                if not any(_box_intersects(box, occupied) for occupied in occupied_boxes):
                    chosen_side, chosen_distance = side, distance
                    break
                distance += step
            if chosen_side is not None:
                break

    if chosen_side is None:
        # Сторону сменить/освободить не удалось: двигаем только торцевые виджеты.
        chosen_side = sides_to_try[0]
        import logging
        moved = _move_end_widgets_to_special_position(
            pylon, arrows, occupied_boxes, chosen_side
        )
        # Берём реальный размер области виджета с запасом, уменьшая его на 12%.
        widget_length = diagnostic_offset() * 0.88
        chosen_distance = initial + widget_length
        if not moved:
            # Если подходящие стрелки не найдены, не делаем вид, что сдвиг состоялся.
            red = True

    reverse = False
    # Если размер пришлось поставить на альтернативную сторону, проверяем,
    # не попадает ли его текст на виджеты. При конфликте пробуем развернуть
    # направление размерной линии (конечная -> начальная), сохраняя ту же сторону.
    if chosen_side != sides_to_try[0]:
        normal_box = _dimension_collision_box(
            pylon, "end", chosen_side, float(chosen_distance),
            project_end, actual_end,
        )
        reversed_box = _dimension_collision_box(
            pylon, "end", chosen_side, float(chosen_distance),
            project_end, actual_end, reverse=True,
        )
        normal_hits = sum(
            1 for arrow in arrows
            if _box_intersects(normal_box, _arrow_collision_box(arrow))
        )
        reversed_hits = sum(
            1 for arrow in arrows
            if _box_intersects(reversed_box, _arrow_collision_box(arrow))
        )
        if reversed_hits < normal_hits:
            reverse = True

    _draw_dimension_pair(
        modelspace, pylon, "end", dimstyle, chosen_side,
        float(chosen_distance), project_end, actual_end, red=red,
        reverse=reverse,
    )
    occupied_boxes.append(_dimension_collision_box(
        pylon, "end", chosen_side, float(chosen_distance), project_end,
        actual_end, reverse=reverse,
    ))


def draw_survey_points(
    modelspace,
    survey_points: list[SurveyPoint],
) -> None:
    """
    Рисует все точки съёмки как настоящие DXF POINT.

    X/Y берутся из координат, использованных программой при обработке,
    а Z записывается непосредственно в координату точки. Поэтому высота
    каждой точки остаётся доступной в свойствах объекта CAD.
    """
    for point in survey_points:
        modelspace.add_point(
            (point.x, point.y, point.z),
            dxfattribs={
                "layer": SURVEY_POINTS_LAYER,
                "color": 4,
            },
        )


def write_result_dxf(
    source_file: str,
    output_file: str,
    arrows: list[Arrow],
    pylons: list[Pylon],
    diagnostics: list[PylonDiagnostic],
    survey_points: list[SurveyPoint] | None = None,
    wall_contours: list[WallContour] | None = None,
    dimension_values: dict | None = None,
    dimension_deviation_means: dict | None = None,
    dimension_diagnostics: list | None = None,
) -> Path:
    """
    Открывает исходный DXF, добавляет стрелки
    и сохраняет результат в новый файл.
    """
    source_path = Path(source_file)
    output_path = Path(output_file)

    if not source_path.exists():
        raise FileNotFoundError(
            f"Исходный DXF не найден: {source_path}"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    document = ezdxf.readfile(source_path)
    modelspace = document.modelspace()
    print("Текстовые стили в DXF:")
    text_style = select_text_style(document)
    ensure_output_layer(document)
    ensure_level_letters_layer(document)
    ensure_diagnostic_layer(document)
    ensure_search_area_layer(document)
    ensure_survey_points_layer(document)
    ensure_dimension_layers(document)

    dimension_style = import_dimension_style(
        document,
        app_config.DIMENSION_ETALON_DXF,
        app_config.DIMENSION_STYLE_NAME,
    )

    if survey_points is not None:
        draw_survey_points(
            modelspace,
            survey_points,
        )

    # Карта занятости начинается с виджетов отклонений: стрелка + число + буква.
    occupied_boxes = [_arrow_collision_box(arrow) for arrow in arrows]

    if app_config.DIMENSIONS_ENABLED:
        # Сначала длинные размеры, затем торцевые — так сохраняется карта коллизий.
        for pylon in pylons:
            draw_pylon_long_dimension(
                modelspace, pylon, dimension_style, pylons, occupied_boxes, wall_contours, dimension_values, dimension_deviation_means, dimension_diagnostics
            )

        for pylon in pylons:
            draw_pylon_end_dimension(
                modelspace, pylon, dimension_style, occupied_boxes, arrows, pylons, wall_contours, dimension_values, dimension_deviation_means, dimension_diagnostics
            )

    # ВАЖНО: рисуем виджеты после размещения размеров. Если торцевой
    # алгоритм сдвинул Arrow, draw_arrow запишет в DXF уже новые координаты.
    for arrow in arrows:
        draw_arrow(
            modelspace,
            arrow,
            text_style,
        )

    diagnostics_by_number = {
    diagnostic.number: diagnostic
    for diagnostic in diagnostics
}

    for pylon in pylons:
        draw_pylon_search_areas(
            modelspace,
            pylon,
        )

    for number, pylon in enumerate(pylons, start=1):
        diagnostic = diagnostics_by_number.get(number)
    
        # Определяем цвет в зависимости от статуса
        if diagnostic is None:
            color = COLOR_MISSING   # если нет диагностики – считаем проблемой
        else:
            if diagnostic.status == "OK":
                color = COLOR_OK
            elif diagnostic.status == "MISSING":
                color = COLOR_MISSING
            elif diagnostic.status == "EXTRA":
                color = COLOR_EXTRA
            else:
                color = COLOR_EXTRA   # на всякий случай
        
        draw_pylon_diagnostic_frame(
            modelspace=modelspace,
            pylon=pylon,
            number=number,
            color=color,
            text_style=text_style,
        )
        

   


    document.saveas(output_path)

    return output_path