# from core.warnings import generate_warning_marks
# from core.arrows import generate_arrows
# from core.calculator import calculate_deviations
# from core.matcher import (
#     classify_pylon_points,
#     match_points_to_pylons,
#     split_points_by_height,
# )
# from readers.dxf_reader import read_pylons
# from readers.survey_reader import read_survey
# from config.config import (
#     DXF_FILE,
#     OUTPUT_FILE,
#     SEARCH_MARGIN,
#     SURVEY_FILE,
# )
# from writers.dxf_writer import write_result_dxf

# def main() -> None:
#     print()
#     print("VerfDev")
#     print("=" * 50)

#     pylons = read_pylons(DXF_FILE)
#     survey_points = read_survey(SURVEY_FILE)

#     matches = match_points_to_pylons(
#         pylons=pylons,
#         survey_points=survey_points,
#         margin=SEARCH_MARGIN,
#     )
#     warnings = generate_warning_marks(matches)

#     levels = split_points_by_height(matches)
#     classified = classify_pylon_points(levels)
#     deviations = calculate_deviations(classified)
#     arrows = generate_arrows(deviations)

#     print(f"Предупреждений: {len(warnings)}")

#     for warning in warnings:
#         print(
#             f"{warning.message} "
#             f"в точке ({warning.x:.3f}, {warning.y:.3f})"
#         )

#     print()

#     result_path = write_result_dxf(
#         source_file=DXF_FILE,
#         output_file=OUTPUT_FILE,
#         arrows=arrows,
#     )

#     print(f"Пилонов найдено: {len(pylons)}")
#     print(f"Стрелок создано: {len(arrows)}")
#     print()
#     print("DXF успешно сохранён:")
#     print(result_path.resolve())

# if __name__ == "__main__":
#     main()
from gui.main_window import MainWindow

def main():
    app = MainWindow()
    app.run()

if __name__ == "__main__":
    main()