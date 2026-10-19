import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config.config import CONFIG_PATH
import config.config as app_config
from core.pylon import Pylon
from core.matcher import face_region_bounds
from gui.transform_dialog import TransformDialog
from gui.dimension_settings_dialog import DimensionSettingsDialog


class SettingsTab:

    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.entries = {}
        self.build()
        self.load_values()

    def build(self):
        # Две основные колонки позволяют не делать страницу настроек
        # слишком высокой. Правая колонка занята областью поиска и
        # большим предпросмотром.
        self.frame.columnconfigure(0, weight=0)
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(0, weight=1)

        left = ttk.Frame(self.frame, width=560)
        left.grid_propagate(False)
        left.grid(
            row=0,
            column=0,
            sticky="nsw",
            padx=(15, 10),
            pady=10,
        )

        right = ttk.Frame(self.frame)
        right.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(10, 15),
            pady=10,
        )
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # ----------------------------
        # Левая колонка: текст
        # ----------------------------
        row = 0
        ttk.Label(
            left,
            text="Текст",
            font=("", 11, "bold"),
        ).grid(row=row, column=0, sticky="w", pady=(0, 8))

        button_frame = ttk.Frame(left)
        button_frame.grid(row=row, column=1, sticky="e", pady=(0, 8))

        ttk.Button(
            button_frame,
            text="Сохранить",
            command=self.save_values,
        ).pack(side="left", padx=(0, 4))

        ttk.Button(
            button_frame,
            text="Перечитать",
            command=self.load_values,
        ).pack(side="left")

        self.status_label = ttk.Label(button_frame, text="")

        row += 1

        row = self.add_field(left, row, "Высота текста", "text.height")
        row = self.add_field(left, row, "Отступ от стрелки до текста", "text.offset")
        row = self.add_field(left, row, "Расстояние число / буква", "text.value_level_gap")
        row = self.add_field(left, row, "Текстовый стиль", "text.style")

        ttk.Separator(left, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6
        )
        row += 1

        # ----------------------------
        # Размеры
        # ----------------------------
        ttk.Label(
            left,
            text="Размеры",
            font=("", 11, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1

        self.dimensions_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            left,
            text="Рисовать размеры на чертеже",
            variable=self.dimensions_enabled_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
        row += 1

        ttk.Button(
            left,
            text="Параметры размеров…",
            command=self.open_dimension_settings,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 6))
        row += 1

        ttk.Separator(left, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6
        )
        row += 1

        # ----------------------------
        # Стрелки
        # ----------------------------
        ttk.Label(
            left,
            text="Стрелки",
            font=("", 11, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1

        row = self.add_field(left, row, "Длина стрелки", "arrow.length")
        row = self.add_field(left, row, "Размер головы стрелки", "arrow.size")
        row = self.add_field(left, row, "Ширина тела стрелки", "arrow.body_width")
        row = self.add_field(left, row, "Отступ от пилона", "arrow.wall_offset")
        row = self.add_field(left, row, "Расстояние В / Н", "arrow.pair_spacing")

        ttk.Separator(left, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6
        )
        row += 1

        # ----------------------------
        # Короткие пилоны
        # ----------------------------
        ttk.Label(
            left,
            text="Короткие пилоны",
            font=("", 11, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1

        self.short_pylons_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left,
            text="Считать короткие пилоны отдельно",
            variable=self.short_pylons_enabled_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        row = self.add_field(
            left,
            row,
            "Максимальная длина короткого пилона, мм",
            "short_pylons.max_length_mm",
        )

        ttk.Separator(left, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6
        )
        row += 1

        # ----------------------------
        # Генерация допуска
        # ----------------------------
        ttk.Label(
            left,
            text="Генерация допуска",
            font=("", 11, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1

        self.tolerance_generation_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left,
            text="Генерация допуска",
            variable=self.tolerance_generation_enabled_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        row = self.add_field(
            left,
            row,
            "Допуск X, мм",
            "tolerance_generation.limit_mm",
        )

        ttk.Separator(left, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6
        )
        row += 1

        # ----------------------------
        # Поиск точек
        # ----------------------------
        ttk.Label(
            left,
            text="Поиск точек",
            font=("", 11, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1

        row = self.add_field(left, row, "Допуск поиска", "search.margin")

        ttk.Separator(left, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=6
        )
        row += 1

        # ----------------------------
        # Трансформация координат
        # ----------------------------
        ttk.Label(
            left,
            text="Трансформация координат",
            font=("", 11, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1

        self.transform_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left,
            text="Включить трансформацию (МСК → ПСК)",
            variable=self.transform_enabled_var,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        ttk.Button(
            left,
            text="Настройки опорных точек...",
            command=self.open_transform_dialog,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        row += 1

        # ----------------------------
        # Правая колонка: область поиска
        # ----------------------------
        ttk.Label(
            right,
            text="Область поиска",
            font=("", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        search_content = ttk.Frame(right)
        search_content.grid(row=1, column=0, sticky="nsew")
        search_content.columnconfigure(0, weight=0)
        search_content.columnconfigure(1, weight=1)
        search_content.rowconfigure(1, weight=1)

        fields_frame = ttk.Frame(search_content)
        fields_frame.grid(row=0, column=0, sticky="nw")

        search_row = 0
        search_row = self.add_field(
            fields_frame, search_row,
            "Размер области внутрь от длинной грани",
            "matcher.margin_inside",
        )
        search_row = self.add_field(
            fields_frame, search_row,
            "Размер области наружу от длинной грани",
            "matcher.margin_outside",
        )
        search_row = self.add_field(
            fields_frame, search_row,
            "Размер области внутрь от торцевой грани",
            "matcher.end_face_normal_margin_inside",
        )
        search_row = self.add_field(
            fields_frame, search_row,
            "Размер области наружу от торцевой грани",
            "matcher.end_face_normal_margin_outside",
        )
        search_row = self.add_field(
            fields_frame, search_row,
            "Удлинение за пределы торца",
            "matcher.end_face_tangential_margin",
        )

        for key in (
            "matcher.margin_inside",
            "matcher.margin_outside",
            "matcher.end_face_normal_margin_inside",
            "matcher.end_face_normal_margin_outside",
            "matcher.end_face_tangential_margin",
        ):
            self.entries[key].trace_add(
                "write",
                lambda *_: self.update_search_preview(),
            )

        # Большой предпросмотр. Пилон специально повернут вертикально —
        # так зоны соответствия занимают заметную площадь и их проще читать.
        preview_frame = ttk.LabelFrame(
            search_content,
            text="Предпросмотр зон соответствия",
        )
        preview_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self.search_preview = tk.Canvas(
            preview_frame,
            width=500,
            height=380,
            highlightthickness=1,
        )
        self.search_preview.pack(
            fill="both",
            expand=True,
            padx=8,
            pady=8,
        )
        self.search_preview.bind(
            "<Configure>",
            lambda _event: self.update_search_preview(),
        )

    def add_field(self, parent, row, label_text, key):
        ttk.Label(parent, text=label_text).grid(
            row=row,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=2,
        )
        variable = tk.StringVar()
        entry = ttk.Entry(parent, textvariable=variable, width=20)
        entry.grid(
            row=row,
            column=1,
            sticky="w",
            padx=(0, 5),
            pady=2,
        )
        self.entries[key] = variable
        return row + 1

    def read_json(self) -> dict:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load_values(self):
        try:
            settings = self.read_json()
            for key, variable in self.entries.items():
                section, parameter = key.split(".")
                section_data = settings.get(section, {})

                defaults = {
                    "short_pylons.max_length_mm": 500,
                    "dimensions.search_step_m": 0.2,
                    "dimensions.search_max_distance_m": 1.5,
                    "dimensions.ray_count": 4,
                    "dimensions.ray_length_m": 5.0,
                }
                if key in defaults:
                    value = section_data.get(parameter, defaults[key])
                else:
                    value = section_data[parameter]

                variable.set(str(value))

            dimensions = settings.get("dimensions", {})
            self.dimensions_enabled_var.set(dimensions.get("enabled", True))

            short_pylons = settings.get("short_pylons", {})
            self.short_pylons_enabled_var.set(
                short_pylons.get("enabled", False)
            )

            tolerance_generation = settings.get("tolerance_generation", {})
            self.tolerance_generation_enabled_var.set(
                tolerance_generation.get("enabled", False)
            )

            transform = settings.get("transform", {})
            self.transform_enabled_var.set(
                transform.get("enabled", False)
            )

            self.status_label.config(text="Настройки загружены.")
            self.update_search_preview()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать настройки:\n{e}")

    def save_values(self):
        try:
            settings = self.read_json()
            numeric_fields = {
                "text.height", "text.offset", "text.value_level_gap",
                "arrow.length", "arrow.size", "arrow.body_width",
                "arrow.wall_offset", "arrow.pair_spacing",
                "search.margin",
                "matcher.margin_inside",
                "matcher.margin_outside",
                "matcher.end_face_normal_margin_inside",
                "matcher.end_face_normal_margin_outside",
                "matcher.end_face_tangential_margin",
                "short_pylons.max_length_mm",
                "tolerance_generation.limit_mm",
            }

            for key, variable in self.entries.items():
                section, parameter = key.split(".")
                raw = variable.get().strip()
                if not raw:
                    raise ValueError(f"Поле «{parameter}» не заполнено.")
                if key in numeric_fields:
                    val = float(raw.replace(",", "."))

                    # Для tangential_margin отрицательные значения допустимы:
                    # положительное значение расширяет зону за торец,
                    # отрицательное — укорачивает её вдоль торца.
                    if key in ("matcher.end_face_tangential_margin",):
                        # Для этих параметров отрицательные значения допустимы.
                        settings[section][parameter] = val
                    else:
                        if val <= 0:
                            raise ValueError(f"Значение «{parameter}» должно быть > 0.")
                        settings[section][parameter] = val
                else:
                    settings[section][parameter] = raw

            if "dimensions" not in settings:
                settings["dimensions"] = {}
            settings["dimensions"]["enabled"] = self.dimensions_enabled_var.get()

            if "short_pylons" not in settings:
                settings["short_pylons"] = {}
            settings["short_pylons"]["enabled"] = (
                self.short_pylons_enabled_var.get()
            )

            if "tolerance_generation" not in settings:
                settings["tolerance_generation"] = {}
            settings["tolerance_generation"]["enabled"] = (
                self.tolerance_generation_enabled_var.get()
            )

            if "transform" not in settings:
                settings["transform"] = {}
            settings["transform"]["enabled"] = self.transform_enabled_var.get()

            with CONFIG_PATH.open("w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)

            app_config.reload_settings()
            self.update_search_preview()

            self.status_label.config(text="Настройки сохранены и применены.")
            messagebox.showinfo("VertDev", "Настройки сохранены и применены.")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def update_search_preview(self):
        """Перерисовывает схему зон поиска по текущим значениям полей."""
        if not hasattr(self, "search_preview"):
            return

        try:
            values = {}
            for key in (
                "matcher.margin_inside",
                "matcher.margin_outside",
                "matcher.end_face_normal_margin_inside",
                "matcher.end_face_normal_margin_outside",
                "matcher.end_face_tangential_margin",
            ):
                values[key] = float(
                    self.entries[key].get().replace(",", ".")
                )

            # Условный пилон 1200 x 200 мм.
            pylon = Pylon(
                center_x=0.0,
                center_y=0.0,
                length=1.2,
                width=0.2,
                orientation="X",
                vertices=[],
            )

            import config.config as cfg
            old = (
                cfg.MARGIN_INSIDE,
                cfg.MARGIN_OUTSIDE,
                cfg.END_FACE_NORMAL_MARGIN_INSIDE,
                cfg.END_FACE_NORMAL_MARGIN_OUTSIDE,
                cfg.END_FACE_TANGENTIAL_MARGIN,
            )
            (
                cfg.MARGIN_INSIDE,
                cfg.MARGIN_OUTSIDE,
                cfg.END_FACE_NORMAL_MARGIN_INSIDE,
                cfg.END_FACE_NORMAL_MARGIN_OUTSIDE,
                cfg.END_FACE_TANGENTIAL_MARGIN,
            ) = (
                values["matcher.margin_inside"],
                values["matcher.margin_outside"],
                values["matcher.end_face_normal_margin_inside"],
                values["matcher.end_face_normal_margin_outside"],
                values["matcher.end_face_tangential_margin"],
            )

            bounds = [
                ("long", -1, face_region_bounds(pylon, "long", -1), "Длинная"),
                ("long", 1, face_region_bounds(pylon, "long", 1), "Длинная"),
                ("end", -1, face_region_bounds(pylon, "end", -1), "Торец"),
                ("end", 1, face_region_bounds(pylon, "end", 1), "Торец"),
            ]

            (
                cfg.MARGIN_INSIDE,
                cfg.MARGIN_OUTSIDE,
                cfg.END_FACE_NORMAL_MARGIN_INSIDE,
                cfg.END_FACE_NORMAL_MARGIN_OUTSIDE,
                cfg.END_FACE_TANGENTIAL_MARGIN,
            ) = old

            canvas = self.search_preview
            canvas.delete("all")

            width = max(canvas.winfo_width(), 500)
            height = max(canvas.winfo_height(), 380)

            # Поворачиваем схему на 90° для более удобного вертикального
            # отображения длинного пилона.
            rotated_boxes = []
            for face_type, face_key, box, label in bounds:
                x1, x2, y1, y2 = box
                rotated_boxes.append(
                    (
                        face_type,
                        face_key,
                        (y1, y2, x1, x2),
                        label,
                    )
                )

            min_x = min(b[2][0] for b in rotated_boxes)
            max_x = max(b[2][1] for b in rotated_boxes)
            min_y = min(b[2][2] for b in rotated_boxes)
            max_y = max(b[2][3] for b in rotated_boxes)

            world_width = max_x - min_x
            world_height = max_y - min_y
            scale = min(
                (width - 90) / world_width,
                (height - 105) / world_height,
            )

            def sx(x):
                return 45 + (x - min_x) * scale

            def sy(y):
                return height - 55 - (y - min_y) * scale

            # Пилон после поворота: исходный x становится экранным y,
            # исходный y становится экранным x.
            px1, py1 = sx(-0.1), sy(-0.6)
            px2, py2 = sx(0.1), sy(0.6)
            canvas.create_rectangle(
                px1, py1, px2, py2,
                outline="black",
                width=3,
            )

            for face_type, face_key, box, label in rotated_boxes:
                x1, x2, y1, y2 = box
                canvas.create_rectangle(
                    sx(x1), sy(y2),
                    sx(x2), sy(y1),
                    outline="royalblue",
                    width=3,
                    dash=(8, 5),
                )

            canvas.create_text(
                width / 2,
                14,
                text="Синие рамки — зоны соответствия",
                anchor="n",
                font=("", 10, "bold"),
            )

            canvas.create_text(
                width / 2,
                height - 28,
                text=(
                    f"Длинные грани: внутрь {values['matcher.margin_inside']*1000:.0f} мм / "
                    f"наружу {values['matcher.margin_outside']*1000:.0f} мм"
                ),
                anchor="s",
            )

        except (ValueError, ZeroDivisionError):
            self.search_preview.delete("all")
            canvas_width = max(self.search_preview.winfo_width(), 500)
            canvas_height = max(self.search_preview.winfo_height(), 380)
            self.search_preview.create_text(
                canvas_width / 2,
                canvas_height / 2,
                text="Введите корректные размеры",
                justify="center",
            )

    def open_dimension_settings(self):
        DimensionSettingsDialog(self.frame.winfo_toplevel(), on_saved=self.load_values)

    def open_transform_dialog(self):
        dialog = TransformDialog(self.frame, self.read_json())
        self.frame.master.wait_window(dialog.top)
        if dialog.result:
            self.load_values()
