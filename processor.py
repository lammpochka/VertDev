from pathlib import Path
from typing import Any

from readers.dxf_reader import read_geometry
from readers.survey_reader import read_survey

from core.wall_calculator import (
    build_wall_pairs,
    calculate_wall_deviations,
    limit_wall_deviations,
)
from core.wall_arrows import generate_wall_arrows
from core.wall_matcher import match_wall_points

import config.config as app_config

from core.arrows import generate_arrows
from core.calculator import calculate_deviations, generate_tolerance, _signed_outward_value
from core.matcher import (
    classify_pylon_points_with_diagnostics,
    match_points_to_pylons,
    split_points_by_height,
)
from core.warnings import generate_warning_marks
from writers.dxf_writer import write_result_dxf

def create_output_path(source_dxf: str, tolerance_enabled: bool | None = None) -> Path:
    """
    Создаёт уникальное имя результата в папке output.
    """
    source_path = Path(source_dxf)
    output_directory = app_config.PROJECT_ROOT / "output"
    output_directory.mkdir(parents=True, exist_ok=True)

    if tolerance_enabled is None:
        tolerance_enabled = bool(app_config.TOLERANCE_GENERATION_ENABLED)
    mode_suffix = "DOPUSK" if tolerance_enabled else "FACT"
    base_name = f"{source_path.stem}_VERTDEV_{mode_suffix}"
    output_path = output_directory / f"{base_name}.dxf"

    number = 1
    while output_path.exists():
        output_path = output_directory / f"{base_name}_{number}.dxf"
        number += 1

    return output_path

def process_project(
    dxf_file: str,
    survey_file: str,
    dimension_values: dict | None = None,
) -> dict[str, Any]:
    """
    Выполняет полный расчёт VertDev и сохраняет новый DXF.
    """

    # Перечитываем settings.json перед каждым запуском расчёта.
    app_config.reload_settings()

    dxf_path = Path(dxf_file)
    survey_path = Path(survey_file)

    if not dxf_path.exists():
        raise FileNotFoundError(f"DXF-файл не найден: {dxf_path}")
    if not survey_path.exists():
        raise FileNotFoundError(f"TXT-файл не найден: {survey_path}")

    # ---- 1. ЧТЕНИЕ ГЕОМЕТРИИ И СЪЁМКИ ----
    pylons, wall_contours, geometry_diagnostics = read_geometry(str(dxf_path))
    survey_points = read_survey(str(survey_path))

    print(f"Пилонов: {len(pylons)}")
    print(f"Стеновых контуров: {len(wall_contours)}")
    print(f"Точек съёмки: {len(survey_points)}")

    # ---- 2. ТРАНСФОРМАЦИЯ КООРДИНАТ (ЕСЛИ ВКЛЮЧЕНА) ----
    if app_config.TRANSFORM_ENABLED:
        from core.transform import compute_transform, apply_transform

        try:
            params = compute_transform(
                app_config.TRANSFORM_POINT1_MSK_X, app_config.TRANSFORM_POINT1_MSK_Y,
                app_config.TRANSFORM_POINT1_PSK_X, app_config.TRANSFORM_POINT1_PSK_Y,
                app_config.TRANSFORM_POINT2_MSK_X, app_config.TRANSFORM_POINT2_MSK_Y,
                app_config.TRANSFORM_POINT2_PSK_X, app_config.TRANSFORM_POINT2_PSK_Y,
            )

            # ПРИМЕНЯЕМ ТРАНСФОРМАЦИЮ КО ВСЕМ ТОЧКАМ СЪЁМКИ
            survey_points = apply_transform(survey_points, params)
            print("Трансформация координат применена (МСК -> ПСК)")

            # ОТЛАДОЧНЫЙ ВЫВОД ПЕРВЫХ 5 ТОЧЕК ПОСЛЕ ПРЕОБРАЗОВАНИЯ
            print("Первые 5 точек после трансформации:")
            for p in survey_points[:5]:
                print(f"  {p.name}: X={p.x:.3f}, Y={p.y:.3f}")

        except Exception as e:
            print(f"Ошибка трансформации: {e}. Использую исходные координаты.")
    else:
        print("Трансформация координат ОТКЛЮЧЕНА.")

    # ---- 3. СОПОСТАВЛЕНИЕ СТЕН (ЕСЛИ ЕСТЬ) ----
    if wall_contours:
        wall_matches = match_wall_points(wall_contours, survey_points)
        print(f"Сопоставлений со стенами: {len(wall_matches)}")

        # ОТЛАДКА: покажем, сколько точек попало на каждый сегмент
        for i, match in enumerate(wall_matches[:5]):
            print(f"  Сегмент {i+1}: точек={len(match.points)}")
    else:
        wall_matches = []
        print("Стены отсутствуют, пропускаем обработку стен.")

    # ---- 4. СОПОСТАВЛЕНИЕ ПИЛОНОВ ----
    matches = match_points_to_pylons(
        pylons=pylons,
        survey_points=survey_points,
        margin=app_config.SEARCH_MARGIN,
    )

    warnings = generate_warning_marks(matches)


# ---- 5. КЛАССИФИКАЦИЯ И РАСЧЁТ ОТКЛОНЕНИЙ ----
    levels = split_points_by_height(matches)
    classified, diagnostics = classify_pylon_points_with_diagnostics(levels)
    deviations = calculate_deviations(classified)

    # Генерация допуска — полностью отдельный необязательный этап.
    # При выключенной галочке основной расчёт не изменяется.
    if app_config.TOLERANCE_GENERATION_ENABLED:
        generate_tolerance(deviations)
        print(
            f"Генерация допуска включена: X={app_config.TOLERANCE_GENERATION_LIMIT_MM} мм"
        )

    # ---- 6. СТЕНЫ: ПАРЫ, ОТКЛОНЕНИЯ, СТРЕЛКИ ----
    wall_pairs = build_wall_pairs(wall_matches)
    wall_deviations = calculate_wall_deviations(wall_pairs)

    # Для стен генерации пропущенных отклонений НЕТ.
    # Если генерация допуска включена, только ограничиваем уже
    # существующие значения по логике торцевой пары: В/Н внутри
    # одного и того же виджета, без обращения к соседним парам.
    if app_config.TOLERANCE_GENERATION_ENABLED:
        limit_wall_deviations(
            wall_deviations,
            app_config.TOLERANCE_GENERATION_LIMIT_MM,
        )
        print(
            f"Ограничение стен по логике торца: "
            f"{app_config.TOLERANCE_GENERATION_LIMIT_MM} мм"
        )

    wall_arrows = generate_wall_arrows(wall_deviations)

    # ---- 7. ОБЪЕДИНЕНИЕ СТРЕЛОК ----
    arrows = generate_arrows(deviations)
    arrows.extend(wall_arrows)

    # Размеры изменяются по отклонениям граней, которые влияют на
    # соответствующее направление габарита:
    # длинный размер — по отклонениям торцов;
    # торцевой (короткий) размер — по отклонениям длинных сторон.
    # Знак нормализован относительно пилона: + наружу, - внутрь.
    dimension_deviation_means = {}
    for item in deviations:
        pylon = item.pylon
        key = (round(float(pylon.center_x), 4), round(float(pylon.center_y), 4))
        end_values = [d for d in (item.upper_end, item.lower_end) if d is not None]
        long_values = list(item.upper_long) + list(item.lower_long)
        signed_end = [_signed_outward_value(pylon, d) for d in end_values]
        signed_long = [_signed_outward_value(pylon, d) for d in long_values]
        dimension_deviation_means[key] = {
            # Длина пилона меняется при смещении торцов.
            "long": (sum(signed_end) / len(signed_end)) if signed_end else 0.0,
            "long_values": signed_end,
            # Ширина пилона меняется при смещении длинных сторон.
            "end": (sum(signed_long) / len(signed_long)) if signed_long else 0.0,
            "end_values": signed_long,
        }

    # ---- 8. СОХРАНЕНИЕ РЕЗУЛЬТАТА ----
    output_path = create_output_path(str(dxf_path), app_config.TOLERANCE_GENERATION_ENABLED)
    dimension_diagnostics = []
    write_result_dxf(
        source_file=str(dxf_path),
        output_file=str(output_path),
        arrows=arrows,
        pylons=pylons,
        diagnostics=diagnostics,
        survey_points=survey_points,
        wall_contours=wall_contours,
        dimension_values=dimension_values or {},
        dimension_deviation_means=dimension_deviation_means,
        dimension_diagnostics=dimension_diagnostics,
    )

    # ---- 9. ВОЗВРАТ РЕЗУЛЬТАТОВ ----
    return {
        "output_path": output_path,
        "pylon_count": len(pylons),
        "survey_point_count": len(survey_points),
        "match_count": len(matches),
        "processed_count": len(classified),
        "arrow_count": len(arrows),
        "dimension_count": len(dimension_diagnostics),
        "dimension_diagnostics": dimension_diagnostics,
        "tolerance_generation_enabled": bool(app_config.TOLERANCE_GENERATION_ENABLED),
        "warning_count": len(warnings),
        "warnings": warnings,
        "diagnostics": diagnostics,
        "geometry_diagnostics": geometry_diagnostics,
    }