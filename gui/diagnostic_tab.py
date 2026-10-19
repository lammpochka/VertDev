import tkinter as tk
from tkinter import ttk

class DiagnosticTab:

    def __init__(self, parent):
        self.frame = ttk.Frame(parent)

        self.build()

    def build(self):
        self.frame.columnconfigure(
            0,
            weight=1,
        )
        self.frame.rowconfigure(
            1,
            weight=1,
        )

        self.summary_label = ttk.Label(
            self.frame,
            text="Диагностика ещё не выполнена.",
        )
        self.summary_label.grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=12,
        )

        text_frame = ttk.Frame(self.frame)
        text_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=12,
            pady=(0, 12),
        )

        text_frame.columnconfigure(
            0,
            weight=1,
        )
        text_frame.rowconfigure(
            0,
            weight=1,
        )

        self.text = tk.Text(
            text_frame,
            state="disabled",
            wrap="word",
        )
        self.text.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        scrollbar = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.text.yview,
        )
        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        self.text.configure(
            yscrollcommand=scrollbar.set
        )

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")

    def write(self, message: str):
        self.text.config(state="normal")
        self.text.insert("end", message + "\n")
        self.text.config(state="disabled")

    def show_report(
        self,
        diagnostics,
        geometry_diagnostics=None,
        dimension_diagnostics=None,
    ):
        self.clear()

        geometry_diagnostics = geometry_diagnostics or []
        dimension_diagnostics = dimension_diagnostics or []

        self.summary_label.config(
            text=(
                f"Контуров: {len(geometry_diagnostics)}   |   "
                f"пилонов: {sum(1 for item in geometry_diagnostics if item["classification"] == "ПИЛОН")}   |   "
                f"стен: {sum(1 for item in geometry_diagnostics if item["classification"] == "СТЕНА")}"
            )
        )

        if geometry_diagnostics:
            self.write("=" * 70)
            self.write("КЛАССИФИКАЦИЯ DXF-КОНТУРОВ")
            self.write("=" * 70)
            self.write(
                f"Порог ширины пилона: {geometry_diagnostics[0]["max_pylon_width"]:.6f} м"
            )
            self.write(
                "Формат: исходные вершины → вершины после очистки; "
                "размеры X/Y; результат проверки прямоугольника."
            )

            for item in geometry_diagnostics:
                marker = "ПИЛОН" if item["classification"] == "ПИЛОН" else "СТЕНА"
                self.write(
                    f"Контур #{item["number"]} — {marker}"
                )
                self.write(
                    f"  Вершины: {item["raw_vertices"]} → "
                    f"{item.get("normalized_vertices", item["raw_vertices"])} → "
                    f"{item["cleaned_vertices"]}"
                )

                if item.get("normalization_removed"):
                    self.write("  УДАЛЕНЫ ДУБЛИ ВЕРШИН ДО ПРОВЕРКИ КОЛЛИНЕАРНОСТИ:")
                    for removal in item["normalization_removed"]:
                        point = removal["point"]
                        self.write(
                            f"    Вершина #{removal['index']}: "
                            f"X={point[0]:.9f}, Y={point[1]:.9f} | "
                            f"причина: {removal['reason']}"
                        )
                        previous = removal.get("previous")
                        if previous is not None:
                            self.write(
                                f"      предыдущая оставшаяся: "
                                f"X={previous[0]:.9f}, Y={previous[1]:.9f}"
                            )
                        self.write(
                            f"      допуск совпадения: {removal['tolerance']:.9f}"
                        )

                if item.get("raw_points"):
                    self.write("  ИСХОДНЫЕ ВЕРШИНЫ:")
                    for index, point in enumerate(item["raw_points"], 1):
                        self.write(
                            f"    {index}: X={point[0]:.9f}, Y={point[1]:.9f}"
                        )

                if item.get("collinear_removals"):
                    self.write("  УДАЛЕНИЯ КАК КОЛЛИНЕАРНЫХ:")
                    for removal in item["collinear_removals"]:
                        point = removal["point"]
                        previous = removal["previous"]
                        next_point = removal["next"]
                        vin = removal["vector_in"]
                        vout = removal["vector_out"]
                        self.write(
                            f"    Вершина #{removal["index"]}: "
                            f"X={point[0]:.9f}, Y={point[1]:.9f}"
                        )
                        self.write(
                            f"      предыдущая: X={previous[0]:.9f}, Y={previous[1]:.9f}"
                        )
                        self.write(
                            f"      следующая:   X={next_point[0]:.9f}, Y={next_point[1]:.9f}"
                        )
                        self.write(
                            f"      вектор до:   ({vin[0]:.9f}, {vin[1]:.9f})"
                        )
                        self.write(
                            f"      вектор после:({vout[0]:.9f}, {vout[1]:.9f})"
                        )
                        self.write(
                            f"      cross product: {removal["cross_product"]:.12f} "
                            f"| допуск: {removal["tolerance"]:.12f}"
                        )

                if item.get("cleaned_points"):
                    self.write("  ВЕРШИНЫ ПОСЛЕ ОЧИСТКИ:")
                    for index, point in enumerate(item["cleaned_points"], 1):
                        self.write(
                            f"    {index}: X={point[0]:.9f}, Y={point[1]:.9f}"
                        )
                self.write(
                    f"  Размер X: {item["size_x"]:.6f} м | "
                    f"Y: {item["size_y"]:.6f} м | "
                    f"длина: {item["length"]:.6f} м | "
                    f"ширина: {item["width"]:.6f} м"
                )
                self.write(
                    f"  Ориентация: {item["orientation"]} | "
                    f"Прямоугольник X/Y: {"ДА" if item["rectangle"] else "НЕТ"}"
                )
                self.write(
                    f"  Причина: {item["reason"]}"
                )

                if item.get("cleaned_points"):
                    self.write("  ПРОВЕРКА КАЖДОЙ СТОРОНЫ:")
                    pts = item["cleaned_points"]
                    for index in range(len(pts)):
                        p1 = pts[index]
                        p2 = pts[(index + 1) % len(pts)]
                        dx = p2[0] - p1[0]
                        dy = p2[1] - p1[1]
                        horizontal = abs(dy) <= 0.001
                        vertical = abs(dx) <= 0.001
                        self.write(
                            f"    {index + 1}: dx={dx:.9f}, dy={dy:.9f} | "
                            f"горизонтальная={'ДА' if horizontal else 'НЕТ'} | "
                            f"вертикальная={'ДА' if vertical else 'НЕТ'} | "
                            f"длина={(dx * dx + dy * dy) ** 0.5:.9f}"
                        )
                if item.get("entity_handle"):
                    self.write(
                        f"  DXF handle: {item["entity_handle"]}"
                    )
                self.write("-")

            self.write("=" * 70)
            self.write("")

        processed_count = sum(
            1
            for item in diagnostics
            if item.processed
        )

        problem_count = sum(
            1
            for item in diagnostics
            if item.status != "OK"
        )

        self.summary_label.config(
            text=(
                f"Контуров: {len(geometry_diagnostics)} | "
                f"Пилонов: {sum(1 for item in geometry_diagnostics if item["classification"] == "ПИЛОН")} | "
                f"Стен: {sum(1 for item in geometry_diagnostics if item["classification"] == "СТЕНА")} || "
                f"Обработано пилонов: {processed_count} | "
                f"Проблемных пилонов: {problem_count}"
            )
        )

        if dimension_diagnostics:
            self.write("=" * 70)
            self.write("ДИАГНОСТИКА ГЕНЕРАЦИИ РАЗМЕРОВ")
            self.write("=" * 70)
            self.write(f"Сгенерировано размерных значений: {len(dimension_diagnostics)}")
            for item in dimension_diagnostics:
                kind_label = "ДЛИННЫЙ" if item["kind"] == "long" else "ТОРЕЦ"
                signed = item.get("signed_deviations", [])
                signed_text = ", ".join(f"{value:+.2f}" for value in signed) if signed else "нет данных"
                self.write(
                    f"{kind_label} | центр X={item['pylon_x']:.4f}, Y={item['pylon_y']:.4f}"
                )
                self.write(
                    f"  Проектный размер: {item['project_mm']} мм | "
                    f"режим допуска: {'ВКЛ' if item['generation_enabled'] else 'ВЫКЛ'}"
                )
                self.write(f"  Знаковые отклонения наружу/внутрь: [{signed_text}]")
                self.write(f"  Среднее: {item['mean_deviation']:+.3f} мм")
                self.write(f"  Диапазон поправки: {item['random_range']} мм")
                if item.get("manual_fallback"):
                    self.write("  Ручное значение пустое — взят проектный размер")
                elif not item['generation_enabled'] and item.get("manual_value", "").strip():
                    self.write(f"  Ручное значение: {item['manual_value']} мм")
                self.write(
                    f"  Поправка: {item['offset_mm']:+d} мм | "
                    f"ИТОГ: {item['actual_mm']} мм"
                )
                self.write("-")
            self.write("")

        for item in diagnostics:
            if item.status == "OK":
                marker = "OK"
            elif item.status == "EXTRA":
                marker = "ЛИШНИЕ ТОЧКИ"
            else:
                marker = "НЕ ХВАТАЕТ ТОЧЕК"

            self.write(
                f"ПИЛОН №{item.number} — {marker}"
            )

            self.write(
                f"Центр: "
                f"X={item.center_x:.3f}, "
                f"Y={item.center_y:.3f}"
            )

            self.write(
                f"Всего точек: "
                f"{item.total_points}"
            )

            self.write(
                f"Верх: "
                f"{item.upper_point_count}, "
                f"низ: "
                f"{item.lower_point_count}"
            )

            self.write(
                "Обработан: "
                + (
                    "да"
                    if item.processed
                    else "нет"
                )
            )

            if item.upper_selected:
                self.write(
                    "Выбрано В: "
                    + ", ".join(
                        item.upper_selected
                    )
                )

            if item.lower_selected:
                self.write(
                    "Выбрано Н: "
                    + ", ".join(
                        item.lower_selected
                    )
                )

            if item.upper_rejected:
                self.write(
                    "Отброшено В: "
                    + ", ".join(
                        item.upper_rejected
                    )
                )

            if item.lower_rejected:
                self.write(
                    "Отброшено Н: "
                    + ", ".join(
                        item.lower_rejected
                    )
                )

            if item.missing_positions:
                self.write("Не найдено:")

                for position in (
                    item.missing_positions
                ):
                    self.write(
                        f"  - {position}"
                    )

            self.write("-" * 55)

        self.text.see("1.0")