import os
import tkinter as tk

from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from processor import process_project
from gui.dimension_entry_dialog import DimensionEntryDialog

class MainTab:

    def __init__(
        self,
        parent,
        diagnostic_callback=None,
    ):
        self.frame = ttk.Frame(parent)

        self.dxf_path = tk.StringVar()
        self.txt_path = tk.StringVar()

        self.diagnostic_callback = diagnostic_callback
        self.result_path = None
        self.dimension_values_by_dxf = {}

        self.build()

    def build(self):
        self.frame.columnconfigure(
            0,
            weight=1,
        )

        # Журнал растягивается вместе с окном.
        self.frame.rowconfigure(
            6,
            weight=1,
        )

        # ==========================================
        # DXF
        # ==========================================

        ttk.Label(
            self.frame,
            text="Проект DXF",
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=10,
            pady=(8, 3),
        )

        dxf_frame = ttk.Frame(
            self.frame
        )

        dxf_frame.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=12,
        )

        dxf_frame.columnconfigure(
            0,
            weight=1,
        )

        self.dxf_entry = ttk.Entry(
            dxf_frame,
            textvariable=self.dxf_path,
        )

        self.dxf_entry.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        ttk.Button(
            dxf_frame,
            text="Выбрать",
            command=self.select_dxf,
        ).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )

        # ==========================================
        # TXT
        # ==========================================

        ttk.Label(
            self.frame,
            text="Съёмка TXT",
        ).grid(
            row=2,
            column=0,
            sticky="w",
            padx=10,
            pady=(8, 3),
        )

        txt_frame = ttk.Frame(
            self.frame
        )

        txt_frame.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=12,
        )

        txt_frame.columnconfigure(
            0,
            weight=1,
        )

        self.txt_entry = ttk.Entry(
            txt_frame,
            textvariable=self.txt_path,
        )

        self.txt_entry.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        ttk.Button(
            txt_frame,
            text="Выбрать",
            command=self.select_txt,
        ).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )

        # ==========================================
        # Памятка и кнопки
        # ==========================================

        action_frame = ttk.Frame(
            self.frame
        )

        action_frame.grid(
            row=4,
            column=0,
            sticky="ew",
            padx=12,
            pady=(8, 8),
        )

        action_frame.columnconfigure(
            0,
            weight=1,
        )

        action_frame.columnconfigure(
            1,
            weight=0,
        )

        # Памятка
        warning_frame = ttk.LabelFrame(
            action_frame,
            text="Важно",
        )

        warning_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 12),
        )

        ttk.Label(
            warning_frame,
            text=(
                "Экспортируйте проект в DXF через ПБЛОК, "
                "выбирая только стены и пилоны.\n\n"
                "Все стены и пилоны должны быть "
                "замкнутыми полилиниями.\n\n"
                "Чтобы включить преобразование координат, "
                "включите галочку «Преобразование координат» "
                "на вкладке «Настройки», задайте параметры пересчёта,"
                "нажмите «Сохранить настройки» — настройки применятся сразу."
            ),
            justify="left",
            wraplength=520,
        ).pack(
            anchor="w",
            padx=12,
            pady=10,
        )

        # Кнопки
        button_frame = ttk.Frame(
            action_frame
        )

        button_frame.grid(
            row=0,
            column=1,
            sticky="n",
        )

        button_frame.columnconfigure(
            0,
            weight=1,
        )

        button_frame.columnconfigure(
            1,
            weight=1,
        )

        self.build_button = ttk.Button(
            button_frame,
            text="ПОСТРОИТЬ",
            command=self.on_build,
            state="disabled",
            width=26,
        )

        self.build_button.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(3, 8),
        )

        self.open_result_button = ttk.Button(
            button_frame,
            text="Открыть результат",
            command=self.open_result,
            state="disabled",
        )

        self.open_result_button.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=(0, 4),
        )

        self.open_folder_button = ttk.Button(
            button_frame,
            text="Открыть папку",
            command=self.open_result_folder,
            state="disabled",
        )

        self.open_folder_button.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(4, 0),
        )

        ttk.Button(
            button_frame,
            text="Обзор плана / ручной ввод размеров",
            command=self.open_dimension_entry,
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )

        # ==========================================
        # Журнал
        # ==========================================

        ttk.Label(
            self.frame,
            text="Журнал",
        ).grid(
            row=5,
            column=0,
            sticky="w",
            padx=12,
        )

        self.log = tk.Text(
            self.frame,
            height=8,
            state="disabled",
        )

        self.log.grid(
            row=6,
            column=0,
            sticky="nsew",
            padx=10,
            pady=(4, 8),
        )

    def _save_dimension_values(self, dxf_path, values):
        self.dimension_values_by_dxf[dxf_path] = values

    def open_dimension_entry(self):
        filename = self.dxf_path.get().strip()
        if not filename:
            messagebox.showwarning(
                "Не выбран DXF",
                "Сначала выберите файл проекта DXF.",
                parent=self.frame,
            )
            return
        if not os.path.isfile(filename):
            messagebox.showerror(
                "Файл не найден",
                "Указанный DXF-файл не существует.",
                parent=self.frame,
            )
            return
        try:
            DimensionEntryDialog(self.frame.winfo_toplevel(), filename, on_values_changed=self._save_dimension_values)
        except Exception as exc:
            messagebox.showerror(
                "Не удалось открыть обзор",
                f"Ошибка чтения DXF или подготовки окна:\n{exc}",
                parent=self.frame,
            )

    def select_dxf(self):
        filename = filedialog.askopenfilename(
            title="Выберите проект DXF",
            filetypes=[
                ("DXF files", "*.dxf"),
                ("Все файлы", "*.*"),
            ],
        )

        if filename:
            self.dxf_path.set(filename)
            self.result_path = None

            self.open_result_button.config(
                state="disabled"
            )

            self.open_folder_button.config(
                state="disabled"
            )

            self.write_log(
                f"Выбран DXF: {Path(filename).name}"
            )

            self.update_build_button()

    def select_txt(self):
        filename = filedialog.askopenfilename(
            title="Выберите файл съёмки",
            filetypes=[
                ("TXT files", "*.txt"),
                ("Все файлы", "*.*"),
            ],
        )

        if filename:
            self.txt_path.set(filename)

            self.write_log(
                f"Выбран TXT: {Path(filename).name}"
            )

            self.update_build_button()

    def update_build_button(self):
        files_selected = (
            bool(self.dxf_path.get())
            and bool(self.txt_path.get())
        )

        self.build_button.config(
            state=(
                "normal"
                if files_selected
                else "disabled"
            )
        )

    def on_build(self):
        self.build_button.config(
            state="disabled"
        )

        self.open_result_button.config(
            state="disabled"
        )

        self.open_folder_button.config(
            state="disabled"
        )

        self.write_log("")
        self.write_log("Начало обработки...")
        self.write_log("Чтение DXF и TXT...")


        self.frame.update_idletasks()

        try:
            result = process_project(
                dxf_file=self.dxf_path.get(),
                survey_file=self.txt_path.get(),
                dimension_values=self.dimension_values_by_dxf.get(str(Path(self.dxf_path.get()).resolve()), {}),
            )

            if self.diagnostic_callback:
                self.diagnostic_callback(
                    result["diagnostics"],
                    result.get("geometry_diagnostics", []),
                    result.get("dimension_diagnostics", []),
                )

            self.result_path = Path(
                result["output_path"]
            )

            self.write_log(
                f"Найдено пилонов: "
                f"{result['pylon_count']}"
            )

            self.write_log(
                f"Точек в файле съёмки: "
                f"{result['survey_point_count']}"
            )

            self.write_log(
                f"Обработано пилонов: "
                f"{result['processed_count']}"
            )

            self.write_log(
                f"Создано стрелок: "
                f"{result['arrow_count']}"
            )

            self.write_log(
                f"Сгенерировано размеров: {result.get('dimension_count', 0)}"
            )
            mode = "DOPUSK (генерация допуска включена)" if result.get("tolerance_generation_enabled") else "FACT (генерация допуска выключена)"
            self.write_log(f"Режим размеров: {mode}")

            self.write_log(
                f"Предупреждений: "
                f"{result['warning_count']}"
            )

            self.write_log("")
            self.write_log(
                "DXF успешно создан."
            )

            self.write_log(
                f"Результат: {self.result_path}"
            )

            self.open_result_button.config(
                state="normal"
            )

            self.open_folder_button.config(
                state="normal"
            )

        except Exception as error:
            self.write_log("")
            self.write_log(
                f"ОШИБКА: {error}"
            )

            messagebox.showerror(
                "VertDev — ошибка",
                str(error),
            )

        finally:
            self.update_build_button()

    def open_result(self):
        if not self.result_path:
            return

        if not self.result_path.exists():
            messagebox.showerror(
                "VertDev",
                "Файл результата не найден.",
            )
            return

        try:
            os.startfile(
                self.result_path
            )

        except OSError as error:
            messagebox.showerror(
                "VertDev",
                f"Не удалось открыть DXF:\n{error}",
            )

    def open_result_folder(self):
        if not self.result_path:
            return

        folder = self.result_path.parent

        try:
            os.startfile(folder)

        except OSError as error:
            messagebox.showerror(
                "VertDev",
                f"Не удалось открыть папку:\n{error}",
            )

    def write_log(
        self,
        message,
    ):
        self.log.config(
            state="normal"
        )

        self.log.insert(
            "end",
            message + "\n",
        )

        self.log.see("end")

        self.log.config(
            state="disabled"
        )