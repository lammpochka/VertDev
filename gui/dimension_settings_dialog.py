import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config.config import CONFIG_PATH
import config.config as app_config


class DimensionSettingsDialog:
    """Компактное отдельное окно параметров размерных надписей."""
    FIELDS = [
        ("style_name", "Размерный стиль в эталоне", "text", "ОСНОВА"),
        ("long_random_min_mm", "Длинный размер: минимум рандома, мм", "int", -6),
        ("long_random_max_mm", "Длинный размер: максимум рандома, мм", "int", 6),
        ("end_random_min_mm", "Торцевой размер: минимум рандома, мм", "int", -3),
        ("end_random_max_mm", "Торцевой размер: максимум рандома, мм", "int", 3),
        ("search_initial_offset_m", "Базовый отступ размера, м", "positive", 0.4),
        ("search_step_m", "Шаг поиска места, м", "positive", 0.2),
        ("search_max_distance_m", "Максимальный отступ, м", "positive", 1.5),
        ("ray_count", "Количество лучей проверки", "positive_int", 4),
        ("ray_length_m", "Длина лучей проверки, м", "positive", 5.0),
    ]

    def __init__(self, parent, on_saved=None):
        self.on_saved = on_saved
        self.window = tk.Toplevel(parent)
        self.window.title("VertDev — параметры размеров")
        self.window.transient(parent)
        self.window.resizable(False, False)
        self.vars = {}
        frame = ttk.Frame(self.window, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        for row, (key, label, _kind, _default) in enumerate(self.FIELDS):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=4)
            var = tk.StringVar()
            ttk.Entry(frame, textvariable=var, width=18).grid(row=row, column=1, sticky="ew", pady=4)
            self.vars[key] = var
        etalon_row = len(self.FIELDS)
        ttk.Label(frame, text="Эталонный DXF с размером").grid(row=etalon_row, column=0, sticky="w", padx=(0, 14), pady=4)
        self.etalon_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.etalon_var, width=30).grid(row=etalon_row, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Обзор…", command=self.select_etalon).grid(row=etalon_row + 1, column=0, columnspan=2, sticky="w", pady=(3, 8))
        buttons = ttk.Frame(frame)
        buttons.grid(row=etalon_row + 2, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Отмена", command=self.window.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Сохранить", command=self.save).pack(side="right")
        self.load()
        self.window.update_idletasks()
        w, h = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        sw, sh = self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        self.window.geometry(f"{w}x{h}+{max(0, (sw-w)//2)}+{max(0, (sh-h)//2)}")
        self.window.grab_set()

    def _read(self):
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)

    def load(self):
        try:
            dimensions = self._read().get("dimensions", {})
            for key, _label, _kind, default in self.FIELDS:
                self.vars[key].set(str(dimensions.get(key, default)))
            self.etalon_var.set(str(dimensions.get("etalon_dxf", "")))
        except Exception as exc:
            messagebox.showerror("Ошибка", f"Не удалось загрузить параметры размеров:\n{exc}", parent=self.window)

    def select_etalon(self):
        path = filedialog.askopenfilename(parent=self.window, title="Выберите эталонный DXF", filetypes=[("DXF", "*.dxf"), ("Все файлы", "*.*")])
        if path:
            self.etalon_var.set(path)

    def save(self):
        try:
            settings = self._read()
            dimensions = settings.setdefault("dimensions", {})
            for key, label, kind, _default in self.FIELDS:
                raw = self.vars[key].get().strip().replace(",", ".")
                if not raw:
                    raise ValueError(f"Заполни поле «{label}».")
                if kind == "text":
                    dimensions[key] = raw
                elif kind == "int":
                    dimensions[key] = int(float(raw))
                elif kind == "positive_int":
                    value = int(float(raw))
                    if value < 1:
                        raise ValueError(f"«{label}» должно быть не меньше 1.")
                    dimensions[key] = value
                else:
                    value = float(raw)
                    if value <= 0:
                        raise ValueError(f"«{label}» должно быть больше нуля.")
                    dimensions[key] = value
            for prefix, label in (("long", "длинного размера"), ("end", "торцевого размера")):
                low, high = dimensions[f"{prefix}_random_min_mm"], dimensions[f"{prefix}_random_max_mm"]
                if low > high:
                    raise ValueError(f"Минимум рандома для {label} не может быть больше максимума.")
            dimensions["etalon_dxf"] = self.etalon_var.get().strip()
            with CONFIG_PATH.open("w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
            app_config.reload_settings()
            if self.on_saved:
                self.on_saved()
            messagebox.showinfo("VertDev", "Параметры размеров сохранены и применены.", parent=self.window)
            self.window.destroy()
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc), parent=self.window)
