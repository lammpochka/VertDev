from dataclasses import dataclass

from core.matcher import MatchStatus, PylonMatch

@dataclass
class WarningMark:
    x: float
    y: float

    message: str

    width: float
    height: float

def warning_position(match: PylonMatch) -> tuple[float, float]:
    """
    Ставит предупреждение немного выше и правее пилона.
    Позже вынесем этот отступ в настройки.
    """
    pylon = match.pylon

    if pylon.orientation == "X":
        half_x = pylon.length / 2
        half_y = pylon.width / 2
    else:
        half_x = pylon.width / 2
        half_y = pylon.length / 2

    x = pylon.center_x + half_x + 0.20
    y = pylon.center_y + half_y + 0.20

    return x, y

def warning_message(match: PylonMatch) -> str:
    """
    Формирует короткий текст внутри облачка.
    """
    point_count = len(match.points)

    if match.status == MatchStatus.MISSING:
        return f"{point_count}/6"

    if match.status == MatchStatus.EXTRA:
        return f"{point_count}->6"

    return ""

def generate_warning_marks(
    matches: list[PylonMatch],
) -> list[WarningMark]:
    """
    Создаёт предупреждения только для проблемных пилонов.
    """
    warnings = []

    for match in matches:
        if match.status == MatchStatus.OK:
            continue

        x, y = warning_position(match)
        message = warning_message(match)

        warnings.append(
            WarningMark(
                x=x,
                y=y,
                message=message,
                width=0.45,
                height=0.25,
            )
        )

    return warnings