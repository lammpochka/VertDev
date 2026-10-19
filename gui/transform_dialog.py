import json
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from config.config import CONFIG_PATH


class TransformDialog:
    """Окно управления именованными ключами пересчёта координат."""

    def __init__(self, parent, settings):
        self.parent = parent
        self.settings = settings
        self.result = False
        self.current_key = None

        self.top = tk.Toplevel(parent)
        self.top.title("Ключи пересчёта координат")
        self.top.geometry("620x455")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()

        self.build_ui()
        self.prepare_keys()
        self.refresh_key_list()

    def build_ui(self):
        main_frame = ttk.Frame(self.top, padding=15)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(
            main_frame,
            text="Сохранённые ключи пересчёта (МСК → ПСК):",
            font=("", 10),
        ).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 8))

        # Выбор ключа
        ttk.Label(main_frame, text="Ключ:").grid(
            row=1, column=0, padx=(0, 5), pady=5, sticky="w"
        )

        self.key_var = tk.StringVar()
        self.key_combo = ttk.Combobox(
            main_frame,
            textvariable=self.key_var,
            state="readonly",
            width=28,
        )
        self.key_combo.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        self.key_combo.bind("<<ComboboxSelected>>", self.on_key_selected)

        ttk.Button(
            main_frame,
            text="Новый",
            command=self.new_key,
        ).grid(row=1, column=3, padx=5, pady=5)

        ttk.Button(
            main_frame,
            text="Удалить",
            command=self.delete_key,
        ).grid(row=1, column=4, padx=5, pady=5)

        ttk.Separator(main_frame, orient="horizontal").grid(
            row=2, column=0, columnspan=5, sticky="ew", pady=12
        )

        ttk.Label(
            main_frame,
            text="Введите координаты двух опорных точек в обеих системах:",
        ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(0, 8))

        # Заголовки столбцов
        headers = ["Точка", "МСК X", "МСК Y", "ПСК X", "ПСК Y"]
        for col, text in enumerate(headers):
            ttk.Label(
                main_frame,
                text=text,
                font=("", 9, "bold"),
            ).grid(row=4, column=col, padx=5, pady=5, sticky="w")

        # Переменные координат
        self.p1_msk_x = tk.StringVar()
        self.p1_msk_y = tk.StringVar()
        self.p1_psk_x = tk.StringVar()
        self.p1_psk_y = tk.StringVar()
        self.p2_msk_x = tk.StringVar()
        self.p2_msk_y = tk.StringVar()
        self.p2_psk_x = tk.StringVar()
        self.p2_psk_y = tk.StringVar()

        ttk.Label(main_frame, text="Точка 1").grid(
            row=5, column=0, padx=5, pady=5, sticky="w"
        )
        self._add_entry(main_frame, 5, 1, self.p1_msk_x)
        self._add_entry(main_frame, 5, 2, self.p1_msk_y)
        self._add_entry(main_frame, 5, 3, self.p1_psk_x)
        self._add_entry(main_frame, 5, 4, self.p1_psk_y)

        ttk.Label(main_frame, text="Точка 2").grid(
            row=6, column=0, padx=5, pady=5, sticky="w"
        )
        self._add_entry(main_frame, 6, 1, self.p2_msk_x)
        self._add_entry(main_frame, 6, 2, self.p2_msk_y)
        self._add_entry(main_frame, 6, 3, self.p2_psk_x)
        self._add_entry(main_frame, 6, 4, self.p2_psk_y)

        self.status_var = tk.StringVar(value="")
        ttk.Label(
            main_frame,
            textvariable=self.status_var,
        ).grid(row=7, column=0, columnspan=5, sticky="w", padx=5, pady=(15, 5))

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=5, pady=15)

        ttk.Button(
            button_frame,
            text="Сохранить",
            command=self.save_values,
        ).pack(side="left", padx=5)

        ttk.Button(
            button_frame,
            text="Отмена",
            command=self.cancel,
        ).pack(side="left", padx=5)

    def _add_entry(self, parent, row, col, variable):
        entry = ttk.Entry(parent, textvariable=variable, width=14)
        entry.grid(row=row, column=col, padx=5, pady=5, sticky="w")

    def prepare_keys(self):
        """Приводит старый формат одного ключа к новому формату."""
        transform = self.settings.setdefault("transform", {})
        keys = transform.get("keys")

        if not isinstance(keys, dict) or not keys:
            legacy_fields = (
                "point1_msk_x", "point1_msk_y",
                "point1_psk_x", "point1_psk_y",
                "point2_msk_x", "point2_msk_y",
                "point2_psk_x", "point2_psk_y",
            )

            if any(field in transform for field in legacy_fields):
                keys = {
                    "По умолчанию": {
                        field: transform.get(field, 0.0)
                        for field in legacy_fields
                    }
                }
            else:
                keys = {
                    "Новый ключ": {
                        field: 0.0
                        for field in legacy_fields
                    }
                }

            transform["keys"] = keys

        active_key = transform.get("active_key")
        if active_key not in keys:
            transform["active_key"] = next(iter(keys))

        self.current_key = transform["active_key"]

    def refresh_key_list(self):
        transform = self.settings["transform"]
        keys = transform["keys"]
        names = list(keys.keys())

        self.key_combo["values"] = names

        if self.current_key not in keys:
            self.current_key = names[0]

        self.key_var.set(self.current_key)
        self.load_current_key()

    def on_key_selected(self, event=None):
        name = self.key_var.get()
        if not name:
            return

        self.current_key = name
        self.settings["transform"]["active_key"] = name
        self.load_current_key()

    def load_current_key(self):
        key = self.settings["transform"]["keys"].get(self.current_key, {})

        self.p1_msk_x.set(str(key.get("point1_msk_x", "")))
        self.p1_msk_y.set(str(key.get("point1_msk_y", "")))
        self.p1_psk_x.set(str(key.get("point1_psk_x", "")))
        self.p1_psk_y.set(str(key.get("point1_psk_y", "")))
        self.p2_msk_x.set(str(key.get("point2_msk_x", "")))
        self.p2_msk_y.set(str(key.get("point2_msk_y", "")))
        self.p2_psk_x.set(str(key.get("point2_psk_x", "")))
        self.p2_psk_y.set(str(key.get("point2_psk_y", "")))

        self.status_var.set(f"Выбран ключ: {self.current_key}")

    def new_key(self):
        name = simpledialog.askstring(
            "Новый ключ",
            "Введите название ключа:",
            parent=self.top,
        )

        if name is None:
            return

        name = name.strip()
        if not name:
            messagebox.showerror("Ошибка", "Название ключа не может быть пустым.", parent=self.top)
            return

        keys = self.settings["transform"]["keys"]
        if name in keys:
            messagebox.showerror(
                "Ошибка",
                f'Ключ «{name}» уже существует.',
                parent=self.top,
            )
            return

        keys[name] = {
            "point1_msk_x": 0.0,
            "point1_msk_y": 0.0,
            "point1_psk_x": 0.0,
            "point1_psk_y": 0.0,
            "point2_msk_x": 0.0,
            "point2_msk_y": 0.0,
            "point2_psk_x": 0.0,
            "point2_psk_y": 0.0,
        }
        self.current_key = name
        self.settings["transform"]["active_key"] = name
        self.refresh_key_list()

    def delete_key(self):
        if not self.current_key:
            return

        keys = self.settings["transform"]["keys"]
        if len(keys) <= 1:
            messagebox.showwarning(
                "Удаление ключа",
                "Нельзя удалить последний ключ. Создайте новый ключ перед удалением этого.",
                parent=self.top,
            )
            return

        if not messagebox.askyesno(
            "Удаление ключа",
            f'Удалить ключ «{self.current_key}»?',
            parent=self.top,
        ):
            return

        del keys[self.current_key]
        self.current_key = next(iter(keys))
        self.settings["transform"]["active_key"] = self.current_key
        self.refresh_key_list()

    def save_values(self):
        try:
            if not self.current_key:
                raise ValueError("Не выбран ключ пересчёта.")

            values = {
                "point1_msk_x": float(self.p1_msk_x.get().replace(",", ".")),
                "point1_msk_y": float(self.p1_msk_y.get().replace(",", ".")),
                "point1_psk_x": float(self.p1_psk_x.get().replace(",", ".")),
                "point1_psk_y": float(self.p1_psk_y.get().replace(",", ".")),
                "point2_msk_x": float(self.p2_msk_x.get().replace(",", ".")),
                "point2_msk_y": float(self.p2_msk_y.get().replace(",", ".")),
                "point2_psk_x": float(self.p2_psk_x.get().replace(",", ".")),
                "point2_psk_y": float(self.p2_psk_y.get().replace(",", ".")),
            }

            self.settings["transform"]["keys"][self.current_key] = values
            self.settings["transform"]["active_key"] = self.current_key

            # Старые поля удаляем, чтобы settings.json не содержал два источника правды.
            for field in (
                "point1_msk_x", "point1_msk_y",
                "point1_psk_x", "point1_psk_y",
                "point2_msk_x", "point2_msk_y",
                "point2_psk_x", "point2_psk_y",
            ):
                self.settings["transform"].pop(field, None)

            with CONFIG_PATH.open("w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)

            self.result = True
            self.top.destroy()
            messagebox.showinfo(
                "VertDev",
                f'Ключ «{self.current_key}» сохранён.\n'
                "Настройки сохранены и будут применены сразу.",
            )

        except ValueError:
            messagebox.showerror(
                "Ошибка ввода",
                "Пожалуйста, введите корректные числовые значения.",
                parent=self.top,
            )

    def cancel(self):
        self.result = False
        self.top.destroy()
