import tkinter as tk
from tkinter import ttk

from gui.main_tab import MainTab
from gui.settings_tab import SettingsTab
from gui.diagnostic_tab import DiagnosticTab

class MainWindow:

    def __init__(self):

        self.root = tk.Tk()

        self.root.title("VertDev")
        # Компактное стартовое окно: пользователь сам разворачивает его при необходимости.
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1080, max(820, screen_w - 120))
        height = min(760, max(620, screen_h - 140))
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(820, screen_w), min(620, screen_h))
        self.root.resizable(True, True)

        self.build()

    def _maximize_window(self):
        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")

    def build(self):

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True)

        self.diagnostic_tab = DiagnosticTab(
        notebook
        )

        self.main_tab = MainTab(
        notebook,
        diagnostic_callback=(
        self.diagnostic_tab.show_report
            ),
        )       

        self.settings_tab = SettingsTab(
        notebook
        )

        notebook.add(self.main_tab.frame, text="Главная")
        notebook.add(self.settings_tab.frame, text="Настройки")
        notebook.add(self.diagnostic_tab.frame, text="Диагностика")

        self.status = ttk.Label(
            self.root,
            text="Готов к работе",
            relief="sunken",
            anchor="w"
        )

        self.status.pack(
            side="bottom",
            fill="x"
        )

    def run(self):

        self.root.mainloop()