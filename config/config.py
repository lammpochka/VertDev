import json
import shutil
import sys
from pathlib import Path
from typing import Any


def get_app_directory() -> Path:
    """Возвращает папку приложения (или корень проекта при запуске из исходников)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = get_app_directory()
PROJECT_ROOT = APP_DIR
CONFIG_DIR = APP_DIR / "config"
CONFIG_PATH = CONFIG_DIR / "settings.json"


def get_bundled_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "config" / "settings.json"
    return Path(__file__).resolve().parent / "settings.json"


DEFAULT_CONFIG_PATH = get_bundled_config_path()


def ensure_external_config() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_PATH.exists():
        return

    if not DEFAULT_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Не найдена встроенная копия настроек: {DEFAULT_CONFIG_PATH}"
        )

    shutil.copy2(DEFAULT_CONFIG_PATH, CONFIG_PATH)


def load_settings() -> dict[str, Any]:
    ensure_external_config()

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Ошибка в settings.json, строка {error.lineno}, "
            f"столбец {error.colno}: {error.msg}"
        ) from error


def project_path(relative_path: str) -> str:
    return str(PROJECT_ROOT / relative_path)


def _apply_settings(settings: dict[str, Any]) -> None:
    """Обновляет все runtime-настройки из уже прочитанного JSON."""
    global SETTINGS
    global DXF_FILE, SURVEY_FILE, OUTPUT_FILE, OUTPUT_LAYER, WARNING_LAYER
    global SEARCH_MARGIN
    global MARGIN_INSIDE, MARGIN_OUTSIDE
    global END_FACE_NORMAL_MARGIN_INSIDE
    global END_FACE_NORMAL_MARGIN_OUTSIDE
    global END_FACE_TANGENTIAL_MARGIN
    global TEXT_HEIGHT, TEXT_OFFSET, VALUE_LEVEL_GAP
    global TOP_TEXT, BOTTOM_TEXT, TEXT_STYLE
    global ARROW_LENGTH, ARROW_SIZE, ARROW_BODY_WIDTH
    global WALL_OFFSET, PAIR_SPACING
    global WARNING_OFFSET, WARNING_WIDTH, WARNING_HEIGHT, WARNING_TEXT_HEIGHT
    global TOP_COLOR, BOTTOM_COLOR, WARNING_COLOR
    global MAX_PYLON_WIDTH, SEARCH_WALL_CONTOURS, WALL_SEARCH_MARGIN
    global SHORT_PYLONS_ENABLED, SHORT_PYLON_MAX_LENGTH
    global TOLERANCE_GENERATION_ENABLED, TOLERANCE_GENERATION_LIMIT_MM
    global DIMENSIONS_ENABLED
    global DIMENSION_ETALON_DXF, DIMENSION_STYLE_NAME
    global DIMENSION_RANDOM_MIN_MM, DIMENSION_RANDOM_MAX_MM
    global DIMENSION_LONG_RANDOM_MIN_MM, DIMENSION_LONG_RANDOM_MAX_MM
    global DIMENSION_END_RANDOM_MIN_MM, DIMENSION_END_RANDOM_MAX_MM
    global DIMENSION_SEARCH_INITIAL_OFFSET_M, DIMENSION_SEARCH_STEP_M, DIMENSION_SEARCH_MAX_DISTANCE_M
    global DIMENSION_RAY_COUNT, DIMENSION_RAY_LENGTH_M
    global TRANSFORM_SETTINGS, TRANSFORM_ENABLED, TRANSFORM_KEYS
    global TRANSFORM_ACTIVE_KEY
    global TRANSFORM_POINT1_MSK_X, TRANSFORM_POINT1_MSK_Y
    global TRANSFORM_POINT1_PSK_X, TRANSFORM_POINT1_PSK_Y
    global TRANSFORM_POINT2_MSK_X, TRANSFORM_POINT2_MSK_Y
    global TRANSFORM_POINT2_PSK_X, TRANSFORM_POINT2_PSK_Y

    SETTINGS = settings

    files = settings["files"]
    DXF_FILE = project_path(files["dxf_file"])
    SURVEY_FILE = project_path(files["survey_file"])
    OUTPUT_FILE = project_path(files["output_file"])
    OUTPUT_LAYER = files["output_layer"]
    WARNING_LAYER = files["warning_layer"]

    search = settings["search"]
    SEARCH_MARGIN = float(search["margin"])

    matcher = settings["matcher"]
    MARGIN_INSIDE = float(matcher["margin_inside"])
    MARGIN_OUTSIDE = float(matcher["margin_outside"])
    END_FACE_NORMAL_MARGIN_INSIDE = float(
        matcher["end_face_normal_margin_inside"]
    )
    END_FACE_NORMAL_MARGIN_OUTSIDE = float(
        matcher["end_face_normal_margin_outside"]
    )
    END_FACE_TANGENTIAL_MARGIN = float(
        matcher["end_face_tangential_margin"]
    )

    text = settings["text"]
    TEXT_HEIGHT = float(text["height"])
    TEXT_OFFSET = float(text["offset"])
    VALUE_LEVEL_GAP = float(text["value_level_gap"])
    TOP_TEXT = text["top_text"]
    BOTTOM_TEXT = text["bottom_text"]
    TEXT_STYLE = str(text.get("style", "Standard"))

    arrow = settings["arrow"]
    ARROW_LENGTH = float(arrow["length"])
    ARROW_SIZE = float(arrow["size"])
    ARROW_BODY_WIDTH = float(arrow["body_width"])
    WALL_OFFSET = float(arrow["wall_offset"])
    PAIR_SPACING = float(arrow["pair_spacing"])

    warning = settings["warning"]
    WARNING_OFFSET = float(warning["offset"])
    WARNING_WIDTH = float(warning["width"])
    WARNING_HEIGHT = float(warning["height"])
    WARNING_TEXT_HEIGHT = float(warning["text_height"])

    colors = settings["colors"]
    TOP_COLOR = int(colors["top"])
    BOTTOM_COLOR = int(colors["bottom"])
    WARNING_COLOR = int(colors["warning"])

    geometry = settings.get("geometry", {})
    MAX_PYLON_WIDTH = float(geometry.get("max_pylon_width", 0.50))
    SEARCH_WALL_CONTOURS = bool(geometry.get("search_wall_contours", True))

    walls = settings.get("walls", {})
    WALL_SEARCH_MARGIN = float(walls.get("search_margin", 0.35))

    short_pylons = settings.get("short_pylons", {})
    SHORT_PYLONS_ENABLED = bool(short_pylons.get("enabled", False))
    SHORT_PYLON_MAX_LENGTH = float(
        short_pylons.get("max_length_mm", 500)
    ) / 1000.0

    tolerance_generation = settings.get("tolerance_generation", {})
    TOLERANCE_GENERATION_ENABLED = bool(
        tolerance_generation.get("enabled", False)
    )
    dimensions = settings.get("dimensions", {})
    DIMENSIONS_ENABLED = bool(dimensions.get("enabled", True))
    DIMENSION_ETALON_DXF = str(dimensions.get("etalon_dxf", ""))
    DIMENSION_STYLE_NAME = str(dimensions.get("style_name", "ОСНОВА")).strip() or "ОСНОВА"
    DIMENSION_RANDOM_MIN_MM = int(float(dimensions.get("random_min_mm", -3)))
    DIMENSION_RANDOM_MAX_MM = int(float(dimensions.get("random_max_mm", 3)))
    DIMENSION_LONG_RANDOM_MIN_MM = int(float(dimensions.get("long_random_min_mm", -6)))
    DIMENSION_LONG_RANDOM_MAX_MM = int(float(dimensions.get("long_random_max_mm", 6)))
    DIMENSION_END_RANDOM_MIN_MM = int(float(dimensions.get("end_random_min_mm", -3)))
    DIMENSION_END_RANDOM_MAX_MM = int(float(dimensions.get("end_random_max_mm", 3)))
    DIMENSION_SEARCH_INITIAL_OFFSET_M = float(dimensions.get("search_initial_offset_m", 0.4))
    DIMENSION_SEARCH_STEP_M = float(dimensions.get("search_step_m", 0.2))
    DIMENSION_SEARCH_MAX_DISTANCE_M = float(
        dimensions.get("search_max_distance_m", 1.5)
    )
    DIMENSION_RAY_COUNT = int(float(dimensions.get("ray_count", 4)))
    DIMENSION_RAY_LENGTH_M = float(dimensions.get("ray_length_m", 5.0))
    if DIMENSION_RAY_COUNT < 1:
        DIMENSION_RAY_COUNT = 4
    if DIMENSION_RAY_LENGTH_M <= 0:
        DIMENSION_RAY_LENGTH_M = 5.0
    if DIMENSION_SEARCH_INITIAL_OFFSET_M <= 0:
        DIMENSION_SEARCH_INITIAL_OFFSET_M = 0.4
    if DIMENSION_SEARCH_STEP_M <= 0:
        DIMENSION_SEARCH_STEP_M = 0.2
    if DIMENSION_SEARCH_MAX_DISTANCE_M <= 0:
        DIMENSION_SEARCH_MAX_DISTANCE_M = 1.5
    if DIMENSION_LONG_RANDOM_MIN_MM > DIMENSION_LONG_RANDOM_MAX_MM:
        DIMENSION_LONG_RANDOM_MIN_MM, DIMENSION_LONG_RANDOM_MAX_MM = DIMENSION_LONG_RANDOM_MAX_MM, DIMENSION_LONG_RANDOM_MIN_MM
    if DIMENSION_END_RANDOM_MIN_MM > DIMENSION_END_RANDOM_MAX_MM:
        DIMENSION_END_RANDOM_MIN_MM, DIMENSION_END_RANDOM_MAX_MM = DIMENSION_END_RANDOM_MAX_MM, DIMENSION_END_RANDOM_MIN_MM
    if DIMENSION_RANDOM_MIN_MM > DIMENSION_RANDOM_MAX_MM:
        DIMENSION_RANDOM_MIN_MM, DIMENSION_RANDOM_MAX_MM = (
            DIMENSION_RANDOM_MAX_MM, DIMENSION_RANDOM_MIN_MM
        )

    TOLERANCE_GENERATION_LIMIT_MM = int(
        float(tolerance_generation.get("limit_mm", 10))
    )
    if TOLERANCE_GENERATION_LIMIT_MM <= 0:
        TOLERANCE_GENERATION_LIMIT_MM = 10

    TRANSFORM_SETTINGS = settings.get("transform", {})
    TRANSFORM_ENABLED = bool(TRANSFORM_SETTINGS.get("enabled", False))

    TRANSFORM_KEYS = TRANSFORM_SETTINGS.get("keys", {})
    if not isinstance(TRANSFORM_KEYS, dict) or not TRANSFORM_KEYS:
        legacy_fields = (
            "point1_msk_x", "point1_msk_y",
            "point1_psk_x", "point1_psk_y",
            "point2_msk_x", "point2_msk_y",
            "point2_psk_x", "point2_psk_y",
        )
        if any(field in TRANSFORM_SETTINGS for field in legacy_fields):
            TRANSFORM_KEYS = {
                "По умолчанию": {
                    field: TRANSFORM_SETTINGS.get(field, 0.0)
                    for field in legacy_fields
                }
            }
        else:
            TRANSFORM_KEYS = {}

    TRANSFORM_ACTIVE_KEY = TRANSFORM_SETTINGS.get("active_key")
    if TRANSFORM_ACTIVE_KEY not in TRANSFORM_KEYS:
        TRANSFORM_ACTIVE_KEY = next(iter(TRANSFORM_KEYS), None)

    active_transform = TRANSFORM_KEYS.get(TRANSFORM_ACTIVE_KEY, {})

    TRANSFORM_POINT1_MSK_X = float(active_transform.get("point1_msk_x", 0.0))
    TRANSFORM_POINT1_MSK_Y = float(active_transform.get("point1_msk_y", 0.0))
    TRANSFORM_POINT1_PSK_X = float(active_transform.get("point1_psk_x", 0.0))
    TRANSFORM_POINT1_PSK_Y = float(active_transform.get("point1_psk_y", 0.0))
    TRANSFORM_POINT2_MSK_X = float(active_transform.get("point2_msk_x", 0.0))
    TRANSFORM_POINT2_MSK_Y = float(active_transform.get("point2_msk_y", 0.0))
    TRANSFORM_POINT2_PSK_X = float(active_transform.get("point2_psk_x", 0.0))
    TRANSFORM_POINT2_PSK_Y = float(active_transform.get("point2_psk_y", 0.0))


def reload_settings() -> dict[str, Any]:
    """Перечитывает settings.json без перезапуска приложения."""
    settings = load_settings()
    _apply_settings(settings)
    return settings


# Первичная загрузка при старте.
_apply_settings(load_settings())
