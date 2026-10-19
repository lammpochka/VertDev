from dataclasses import dataclass
from pathlib import Path

@dataclass
class SurveyPoint:
    name: str
    x: float
    y: float
    z: float

def read_survey(filename: str) -> list[SurveyPoint]:
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(f"Файл съёмки не найден: {path}")

    points = []

    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            parts = [
                part.strip()
                for part in line.split(",")
            ]

            # Удаляем пустые элементы
            parts = [part for part in parts if part]

            if len(parts) != 4:
                raise ValueError(
                    f"Строка {line_number}: ожидалось 4 значения, "
                    f"получено {len(parts)}"
                )

            name, survey_x, survey_y, z = parts

            try:
                survey_x = float(survey_x)
                survey_y = float(survey_y)
                z = float(z)
            except ValueError as error:
                raise ValueError(
                    f"Строка {line_number}: неверное числовое значение"
                ) from error

            # Перестановка координат тахеометра в систему AutoCAD
            autocad_x = survey_y
            autocad_y = survey_x

            points.append(
                SurveyPoint(
                    name=name,
                    x=autocad_x,
                    y=autocad_y,
                    z=z,
                )
            )

    return points