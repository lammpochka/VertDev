"""Prototype of the manual dimension entry window."""
import csv
import math
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog

try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    Image = ImageTk = ImageOps = None

from readers.dxf_reader import read_geometry


class DimensionEntryDialog:
    def __init__(self, parent, dxf_path: str, on_values_changed=None):
        self.dxf_path = Path(dxf_path)
        self.on_values_changed = on_values_changed
        self.window = tk.Toplevel(parent)
        self.window.title('VertDev — пилоны и размеры')
        # Карта занимает основную площадь, панель размеров остаётся достаточно
        # широкой. Размер стартового окна адаптируется к разрешению экрана.
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        width = min(1600, max(1150, screen_w - 60))
        height = min(1000, max(760, screen_h - 80))
        self.window.geometry(f'{width}x{height}')
        self.window.minsize(min(1120, screen_w), min(700, screen_h))
        self.window.resizable(True, True)
        self.window.after_idle(self._maximize_window)

        self.items = []
        self.pylons = []
        self.current = 0
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.drag_origin = None
        self.show_calibration_points = False
        self.calibration_points = []
        self.paper_image = None
        self._warped_cache_key = None
        self._warped_cache_image = None
        self.paper_path = None
        self.paper_points = []
        self.paper_pick_mode = False
        self.paper_tk_image = None
        self._warped_cache_key = None
        self._warped_cache_image = None
        self._load_geometry()
        self.values = {str(p['handle']): {'long': '', 'end': ''} for p in self.pylons}
        self._build_ui()
        self.window.after(100, self.fit_view)

    def _maximize_window(self):
        try:
            self.window.state("zoomed")
        except tk.TclError:
            self.window.geometry(f"{self.window.winfo_screenwidth()}x{self.window.winfo_screenheight()}+0+0")

    def _load_geometry(self):
        # Важно: карту строим не по исходным вершинам DXF, а по тем же
        # очищенным контурам, которые VertDev получает из dxf_reader.
        pylons, walls, diagnostics = read_geometry(str(self.dxf_path))
        pylon_handles = {
            d.get('entity_handle')
            for d in diagnostics
            if d.get('classification') == 'ПИЛОН'
        }

        pylon_index = 0
        for diagnostic in diagnostics:
            points = [tuple(map(float, point[:2])) for point in diagnostic.get('cleaned_points', [])]
            if len(points) < 3:
                continue

            handle = diagnostic.get('entity_handle', '')
            kind = diagnostic.get('classification', 'КОНТУР')
            xs, ys = zip(*points)
            item = {
                'points': points,
                'kind': kind,
                'handle': handle,
                'index': None,
            }

            if handle in pylon_handles:
                pylon_index += 1
                item['index'] = pylon_index
                item['label'] = f'Пилон {pylon_index}'
                item['center'] = (
                    float(diagnostic.get('center_x', (min(xs) + max(xs)) / 2)),
                    float(diagnostic.get('center_y', (min(ys) + max(ys)) / 2)),
                )
                # read_geometry уже вычислил длину и ширину после чистки
                # коллинеарных/дублирующихся вершин. Геометрия в метрах,
                # размеры в окне показываем в миллиметрах.
                item['target_long'] = float(diagnostic.get('length', 0)) * 1000.0
                item['target_end'] = float(diagnostic.get('width', 0)) * 1000.0
                self.pylons.append(item)

            if 'center' not in item:
                item['center'] = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
            self.items.append(item)

        self._sort_pylons_spatially()
        # После пространственной сортировки обновляем индексы на карте.
        for item in self.items:
            if item['kind'] == 'ПИЛОН':
                pylon = next((p for p in self.pylons if p['handle'] == item['handle']), None)
                if pylon:
                    item['index'] = pylon['index']
                    item['label'] = pylon['label']
                    item['center'] = pylon['center']
        self.bounds = self._get_bounds()
        self._calculate_calibration_points()

    def _calculate_calibration_points(self):
        """Choose four well-separated pylon vertices near the plan extremes."""
        self.calibration_points = []
        if len(self.pylons) < 4:
            return

        min_x, min_y, max_x, max_y = self.bounds
        span_x = max(max_x - min_x, 1e-9)
        span_y = max(max_y - min_y, 1e-9)
        # Coordinates are normalized so a long plan dimension does not dominate
        # the selection. Each point must belong to a different pylon.
        targets = [
            ('A', 'Верхний левый', min_x, max_y),
            ('B', 'Верхний правый', max_x, max_y),
            ('C', 'Нижний правый', max_x, min_y),
            ('D', 'Нижний левый', min_x, min_y),
        ]
        used_handles = set()
        for code, label, tx, ty in targets:
            candidates = []
            for pylon in self.pylons:
                if pylon['handle'] in used_handles:
                    continue
                for vertex in pylon['points']:
                    x, y = vertex
                    score = ((x - tx) / span_x) ** 2 + ((y - ty) / span_y) ** 2
                    candidates.append((score, pylon, vertex))
            if not candidates:
                self.calibration_points = []
                return
            _score, pylon, vertex = min(candidates, key=lambda row: row[0])
            used_handles.add(pylon['handle'])
            self.calibration_points.append({
                'code': code, 'label': label, 'point': tuple(vertex),
                'pylon_index': pylon['index'], 'handle': pylon['handle'],
            })

    def toggle_calibration_points(self):
        if len(self.calibration_points) != 4:
            messagebox.showwarning(
                'Недостаточно пилонов',
                'Для выбора четырёх опорных точек нужно минимум четыре распознанных пилона.',
                parent=self.window,
            )
            return
        self.show_calibration_points = not self.show_calibration_points
        if self.show_calibration_points:
            self.fit_view()
            self.status.config(text='Опорные точки совмещения: A–D. На следующем этапе укажем им соответствующие точки на фотографии листа.')
            self.calibration_button.config(text='Скрыть опорные точки')
        else:
            self.status.config(text='Опорные точки скрыты. Клик по пилону — выбор; колёсико — масштаб.')
            self.calibration_button.config(text='Показать точки совмещения')
        self.draw()

    def _sort_pylons_spatially(self):
        """Стабильный обход: сверху вниз, внутри ряда слева направо."""
        if len(self.pylons) < 2:
            for i, p in enumerate(self.pylons, 1):
                p['index'] = i
                p['label'] = f'Пилон {i}'
            return
        heights = sorted(max(max(y for _, y in p['points']) - min(y for _, y in p['points']), 1e-6) for p in self.pylons)
        row_tolerance = heights[len(heights)//2] * 2.5
        ordered = sorted(self.pylons, key=lambda p: (-p['center'][1], p['center'][0]))
        rows = []
        for p in ordered:
            cy = p['center'][1]
            row = next((r for r in rows if abs(r['y'] - cy) <= row_tolerance), None)
            if row is None:
                rows.append({'y': cy, 'items': [p]})
            else:
                row['items'].append(p)
                row['y'] = sum(item['center'][1] for item in row['items']) / len(row['items'])
        self.pylons = []
        for row in sorted(rows, key=lambda r: -r['y']):
            self.pylons.extend(sorted(row['items'], key=lambda p: p['center'][0]))
        for i, p in enumerate(self.pylons, 1):
            p['index'] = i
            p['label'] = f'Пилон {i}'

    def _get_bounds(self):
        pts = [p for item in self.items for p in item['points']]
        if not pts:
            return (0, 0, 100, 100)
        xs, ys = zip(*pts)
        return min(xs), min(ys), max(xs), max(ys)

    def _write_values_to_csv(self, path):
        """Явный экспорт введённых размеров; автоматически ничего не сохраняем."""
        with path.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['index', 'handle', 'label', 'center_x', 'center_y', 'long', 'end'])
            writer.writeheader()
            for p in self.pylons:
                vals = self.values.get(str(p['handle']), {})
                writer.writerow({'index': p['index'], 'handle': p['handle'], 'label': p['label'],
                    'center_x': f"{p['center'][0]:.6f}", 'center_y': f"{p['center'][1]:.6f}",
                    'long': vals.get('long', ''), 'end': vals.get('end', '')})

    def export_values(self):
        self._store_fields()
        path = filedialog.asksaveasfilename(
            parent=self.window, title='Экспорт размеров',
            defaultextension='.csv', initialfile=f'{self.dxf_path.stem}_размеры.csv',
            filetypes=[('Таблица CSV', '*.csv'), ('Все файлы', '*.*')])
        if not path:
            return
        try:
            self._write_values_to_csv(Path(path))
            messagebox.showinfo('Экспорт завершён', f'Размеры выгружены в файл:\n{path}', parent=self.window)
        except OSError as exc:
            messagebox.showerror('Ошибка экспорта', str(exc), parent=self.window)

    def reset_values(self):
        """Очистить все введённые размеры после подтверждения пользователя."""
        if not self.pylons:
            return
        if not messagebox.askyesno(
            'Сброс размеров',
            f'Очистить все введённые размеры для {len(self.pylons)} пилонов?\n'
            'Это действие нельзя отменить.',
            parent=self.window,
        ):
            return

        # Сначала фиксируем содержимое активных полей, затем очищаем весь набор.
        self._store_fields()
        for pylon in self.pylons:
            self.values[str(pylon['handle'])] = {'long': '', 'end': ''}
        self.long_var.set('')
        self.end_var.set('')
        self._refresh_list()
        self._publish_values()
        self.status.config(text=f'Все размеры сброшены. Пилонов: {len(self.pylons)}.')
        self.long_entry.focus_set()

    def import_values(self):
        path = filedialog.askopenfilename(
            parent=self.window, title='Импорт размеров',
            filetypes=[('Таблица CSV', '*.csv'), ('Все файлы', '*.*')])
        if not path:
            return
        try:
            with Path(path).open('r', encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            if not rows or not {'long', 'end'}.issubset(rows[0].keys()):
                raise ValueError('В файле нет столбцов long и end. Выбери CSV, ранее экспортированный из VertDev.')
            by_handle = {str(p['handle']): p for p in self.pylons}
            imported = 0
            for row in rows:
                p = by_handle.get((row.get('handle') or '').strip())
                # Если handle изменился при пересохранении DXF, ищем контур по центру.
                if p is None and row.get('center_x') and row.get('center_y'):
                    try:
                        cx, cy = float(row['center_x']), float(row['center_y'])
                        candidates = sorted(self.pylons, key=lambda item: math.hypot(item['center'][0]-cx, item['center'][1]-cy))
                        if candidates and math.hypot(candidates[0]['center'][0]-cx, candidates[0]['center'][1]-cy) <= 1.0:
                            p = candidates[0]
                    except (TypeError, ValueError):
                        p = None
                if p is None:
                    continue
                long_value = (row.get('long') or '').strip()
                end_value = (row.get('end') or '').strip()
                if (long_value and not long_value.isdigit()) or (end_value and not end_value.isdigit()):
                    raise ValueError(f"В строке {row.get('index', '?')} найдены значения не из цифр.")
                self.values[str(p['handle'])] = {'long': long_value, 'end': end_value}
                imported += 1
            if imported == 0:
                raise ValueError('Не удалось сопоставить строки файла с пилонами текущего DXF.')
            self.select_pylon(self.current)
            self._publish_values()
            messagebox.showinfo('Импорт завершён', f'Загружено записей: {imported}.\nЗначения находятся только в памяти. После изменений нажми «Экспорт размеров…», если хочешь сохранить их.', parent=self.window)
        except (OSError, csv.Error, ValueError) as exc:
            messagebox.showerror('Ошибка импорта', str(exc), parent=self.window)

    def _build_ui(self):
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main = ttk.Frame(self.window, padding=8)
        main.grid(row=0, column=0, sticky='nsew')
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        viewer = ttk.Frame(main)
        viewer.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        viewer.columnconfigure(0, weight=1)
        viewer.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(viewer, background='#20252b', highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.canvas.bind('<Configure>', lambda _e: self.draw())
        self.canvas.bind('<MouseWheel>', self._wheel_zoom)
        self.canvas.bind('<Button-4>', lambda e: self._zoom_at(e.x, e.y, 1.15))
        self.canvas.bind('<Button-5>', lambda e: self._zoom_at(e.x, e.y, 1 / 1.15))
        self.canvas.bind('<ButtonPress-2>', self._pan_start)
        self.canvas.bind('<B2-Motion>', self._pan_move)
        self.canvas.bind('<ButtonPress-3>', self._pan_start)
        self.canvas.bind('<B3-Motion>', self._pan_move)
        self.canvas.bind('<Double-Button-1>', lambda _e: self.fit_view())
        self.canvas.bind('<Button-1>', self._click_canvas)

        side = ttk.Frame(main, width=330)
        side.grid(row=0, column=1, sticky='ns')
        side.grid_propagate(False)
        ttk.Label(side, text='Пилоны', font=('', 12, 'bold')).pack(anchor='w')
        self.listbox = tk.Listbox(side, width=34, height=25, exportselection=False)
        self.listbox.pack(fill='both', expand=True, pady=(6, 8))
        self.listbox.bind('<<ListboxSelect>>', self._select_from_list)
        ttk.Label(side, text='Текущий пилон', font=('', 11, 'bold')).pack(anchor='w', pady=(2, 6))
        self.current_label = ttk.Label(side, text='—')
        self.current_label.pack(anchor='w')
        ttk.Label(side, text='Ввод фактических размеров', font=('', 10, 'bold')).pack(anchor='w', pady=(10, 2))
        ttk.Label(side, text='Поля ввода находятся рядом с активным пилоном.\nПроектный размер показан над каждым полем.', wraplength=300).pack(anchor='w', pady=(0, 6))
        self.long_var = tk.StringVar()
        self.end_var = tk.StringVar()
        self._digits_cmd = (self.window.register(self._digits_only), '%P')
        # Настоящие поля размещаются поверх Canvas рядом с выбранным пилоном.
        self.long_widget = ttk.Frame(self.canvas, padding=5, relief='solid')
        ttk.Label(self.long_widget, text='ДЛИННАЯ СТОРОНА', foreground='#2687ff', font=('', 8, 'bold')).pack(anchor='w')
        self.long_project_label = ttk.Label(self.long_widget, text='Проект: —', font=('', 8))
        self.long_project_label.pack(anchor='w')
        self.long_entry = ttk.Entry(self.long_widget, textvariable=self.long_var, font=('', 12), width=12, validate='key', validatecommand=self._digits_cmd)
        self.long_entry.pack(fill='x')
        self.end_widget = ttk.Frame(self.canvas, padding=5, relief='solid')
        ttk.Label(self.end_widget, text='ТОРЕЦ', foreground='#19b887', font=('', 8, 'bold')).pack(anchor='w')
        self.end_project_label = ttk.Label(self.end_widget, text='Проект: —', font=('', 8))
        self.end_project_label.pack(anchor='w')
        self.end_entry = ttk.Entry(self.end_widget, textvariable=self.end_var, font=('', 12), width=10, validate='key', validatecommand=self._digits_cmd)
        self.end_entry.pack(fill='x')
        self.long_entry.bind('<Return>', self._long_enter)
        self.end_entry.bind('<Return>', self._end_enter)
        ttk.Label(side, text='Enter: длинная сторона → торец → следующий пилон', wraplength=300).pack(anchor='w', pady=(4, 4))
        ttk.Separator(side).pack(fill='x', pady=8)
        row = ttk.Frame(side)
        row.pack(fill='x')
        ttk.Button(row, text='◀ Назад', command=self.previous).pack(side='left', expand=True, fill='x')
        ttk.Button(row, text='Дальше ▶', command=self.next).pack(side='left', expand=True, fill='x', padx=(6, 0))
        ttk.Button(side, text='Вписать весь план', command=self.fit_view).pack(fill='x', pady=(8, 3))
        self.calibration_button = ttk.Button(side, text='Показать точки совмещения', command=self.toggle_calibration_points)
        self.calibration_button.pack(fill='x', pady=(3, 3))
        self.paper_button = ttk.Button(side, text='Загрузить фото листа…', command=self.load_paper_photo)
        self.paper_button.pack(fill='x', pady=(3, 3))
        self.paper_clear_button = ttk.Button(side, text='Убрать фото листа', command=self.clear_paper_photo, state='disabled')
        self.paper_clear_button.pack(fill='x', pady=(0, 3))
        ttk.Button(side, text='Сбросить все размеры', command=self.reset_values).pack(fill='x', pady=(8, 3))
        ttk.Button(side, text='Импорт размеров…', command=self.import_values).pack(fill='x', pady=(3, 3))
        ttk.Button(side, text='Экспорт размеров…', command=self.export_values).pack(fill='x', pady=3)
        ttk.Button(side, text='Закрыть', command=self.close).pack(fill='x', pady=(3, 0))

        self.status = ttk.Label(main, text='', anchor='w')
        self.status.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        for p in self.pylons:
            self.listbox.insert('end', self._list_text(p))
        if not self.pylons:
            messagebox.showwarning('Нет пилонов', 'В DXF не найдено ни одного контура, распознанного как пилон.', parent=self.window)
        else:
            self.select_pylon(0)
        self.draw()

    def _select_from_list(self, _event=None):
        sel = self.listbox.curselection()
        if sel:
            self._store_fields()
            self.select_pylon(sel[0])

    def select_pylon(self, idx):
        if not self.pylons:
            return
        self.current = max(0, min(idx, len(self.pylons) - 1))
        p = self.pylons[self.current]
        self.listbox.selection_clear(0, 'end')
        self.listbox.selection_set(self.current)
        self.listbox.see(self.current)
        self.current_label.config(text=f"{p['label']}  ({self.current + 1} из {len(self.pylons)}) — {self._completion(p)}")
        vals = self.values[str(p['handle'])]
        self.long_project_label.config(text=self._project_size_text(p.get('target_long', 0)))
        self.end_project_label.config(text=self._project_size_text(p.get('target_end', 0)))
        self.long_var.set(vals.get('long', ''))
        self.end_var.set(vals.get('end', ''))
        self.status.config(text=f"DXF: {self.dxf_path.name} | Контуров: {len(self.items)} | Пилонов: {len(self.pylons)} | ✓ введён, ◐ частично, ○ не введён | клик по пилону — выбор")
        self._refresh_list()
        self.draw()

    def _project_size_text(self, value):
        if not value or value <= 0:
            return 'Проект: не определён'
        return f'Проект: {value:.1f} мм' if abs(value - round(value)) > 0.05 else f'Проект: {round(value)} мм'

    def _publish_values(self):
        """Передаёт введённые размеры в основное окно по центру контура."""
        if not self.on_values_changed:
            return
        result = {}
        for p in self.pylons:
            cx, cy = p['center']
            vals = self.values.get(str(p['handle']), {})
            result[(round(float(cx), 4), round(float(cy), 4))] = {
                'long': vals.get('long', '').strip(),
                'end': vals.get('end', '').strip(),
            }
        self.on_values_changed(str(self.dxf_path.resolve()), result)

    def close(self):
        self._store_fields()
        self._publish_values()
        self.window.destroy()

    def _digits_only(self, proposed):
        return proposed == '' or proposed.isdigit()

    def _completion(self, p):
        v = self.values.get(str(p['handle']), {})
        return 'введён' if v.get('long') and v.get('end') else ('частично' if v.get('long') or v.get('end') else 'не введён')

    def _list_text(self, p):
        mark = {'введён': '✓', 'частично': '◐', 'не введён': '○'}[self._completion(p)]
        return f"{mark} {p['index']:>3}. {p['label']}"

    def _refresh_list(self):
        if not hasattr(self, 'listbox'):
            return
        for i, p in enumerate(self.pylons):
            self.listbox.delete(i)
            self.listbox.insert(i, self._list_text(p))
        self.listbox.selection_clear(0, 'end')
        if self.pylons:
            self.listbox.selection_set(self.current)
            self.listbox.see(self.current)

    def load_paper_photo(self):
        if Image is None:
            messagebox.showerror('Нужен Pillow', 'Для работы с фотографией установи Pillow: pip install Pillow', parent=self.window)
            return
        path = filedialog.askopenfilename(parent=self.window, title='Выбери фотографию листа',
            filetypes=[('Изображения', '*.png *.jpg *.jpeg *.bmp *.tif *.tiff'), ('Все файлы', '*.*')])
        if not path:
            return
        try:
            # Reduce large phone photos once at load time. Keeping a bounded
            # working image avoids repeatedly resizing/warping 10-30 MP images
            # during zoom, pan, and redraw. 1800 px is enough for selecting
            # four anchors while substantially reducing CPU and memory use.
            with Image.open(path) as source_image:
                try:
                    source_image = ImageOps.exif_transpose(source_image)
                except Exception:
                    pass
                # Ч/б заметно сокращает память и объём данных для трансформации.
                # Ограничиваем рабочее разрешение: для опорных точек этого достаточно.
                source_image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
                self.paper_image = source_image.convert('L').convert('RGBA')
            self.paper_path = path
            self.paper_points = []
            self._warped_cache_key = None
            self._warped_cache_image = None
            self.paper_points = []
            self.paper_pick_mode = False
            self.show_calibration_points = True
            self.paper_clear_button.config(state='normal')
            self._open_paper_point_picker()
        except Exception as exc:
            messagebox.showerror('Ошибка фото', f'Не удалось открыть изображение: {exc}', parent=self.window)

    def _open_paper_point_picker(self):
        # Точки указываются в отдельном окне непосредственно на фотографии,
        # а не на DXF-плане. Порядок строго A, B, C, D.
        self.paper_picker = tk.Toplevel(self.window)
        self.paper_picker.title('Укажи 4 точки на фотографии листа')
        self.paper_picker.geometry('1000x750')
        self.paper_picker.transient(self.window)
        ttk.Label(self.paper_picker, text='Кликай по четырём соответствующим местам на бумаге: A → B → C → D.').pack(fill='x', padx=8, pady=6)
        self.paper_picker_canvas = tk.Canvas(self.paper_picker, bg='#20252b', highlightthickness=0)
        self.paper_picker_canvas.pack(fill='both', expand=True, padx=8, pady=8)
        self.paper_picker_canvas.bind('<Configure>', lambda _e: self._draw_paper_picker())
        self.paper_picker_zoom = 1.0
        self.paper_picker_pan = [0.0, 0.0]
        self.paper_picker_drag = None
        self.paper_picker_base_scale = 1.0
        self.paper_picker_canvas.bind('<Button-1>', self._pick_paper_point)
        self.paper_picker_canvas.bind('<MouseWheel>', self._paper_picker_wheel)
        self.paper_picker_canvas.bind('<Button-4>', lambda e: self._paper_picker_zoom_at(e.x, e.y, 1.2))
        self.paper_picker_canvas.bind('<Button-5>', lambda e: self._paper_picker_zoom_at(e.x, e.y, 1/1.2))
        self.paper_picker_canvas.bind('<ButtonPress-2>', self._paper_picker_pan_start)
        self.paper_picker_canvas.bind('<B2-Motion>', self._paper_picker_pan_move)
        self.paper_picker_canvas.bind('<ButtonPress-3>', self._paper_picker_pan_start)
        self.paper_picker_canvas.bind('<B3-Motion>', self._paper_picker_pan_move)
        self.paper_button.config(text='Выбор 4 точек на фото…')
        self._draw_paper_picker()

    def _draw_paper_picker(self):
        if not hasattr(self, 'paper_picker_canvas') or not self.paper_picker_canvas.winfo_exists():
            return
        c = self.paper_picker_canvas
        c.delete('all')
        w, h = max(1, c.winfo_width()), max(1, c.winfo_height())
        iw, ih = self.paper_image.size
        self.paper_picker_base_scale = min((w-20)/iw, (h-20)/ih)
        self.paper_picker_scale = self.paper_picker_base_scale * self.paper_picker_zoom
        rw, rh = max(1, int(iw*self.paper_picker_scale)), max(1, int(ih*self.paper_picker_scale))
        ox, oy = (w-rw)/2 + self.paper_picker_pan[0], (h-rh)/2 + self.paper_picker_pan[1]
        self.paper_picker_offset = (ox, oy)
        preview = self.paper_image.resize((rw, rh), Image.Resampling.LANCZOS)
        self.paper_picker_tk = ImageTk.PhotoImage(preview)
        c.create_image(ox, oy, image=self.paper_picker_tk, anchor='nw')
        colors = ['#ff5252', '#40c4ff', '#ffd740', '#69f0ae']
        for i, (px, py) in enumerate(self.paper_points):
            sx, sy = ox+px*self.paper_picker_scale, oy+py*self.paper_picker_scale
            c.create_oval(sx-7, sy-7, sx+7, sy+7, fill=colors[i], outline='white', width=2)
            c.create_text(sx+10, sy-12, text='ABCD'[i], fill=colors[i], anchor='w', font=('', 13, 'bold'))
        if len(self.paper_points) < 4:
            c.create_text(12, 12, text=f'Укажи точку {"ABCD"[len(self.paper_points)]}  ·  колесо — масштаб, правая/средняя кнопка — перемещение', anchor='nw', fill='white', font=('', 13, 'bold'))

    def _paper_picker_zoom_at(self, x, y, factor):
        old = self.paper_picker_scale
        new_zoom = max(0.2, min(20.0, self.paper_picker_zoom * factor))
        new_scale = self.paper_picker_base_scale * new_zoom
        if old <= 0:
            return
        ox, oy = self.paper_picker_offset
        # Keep the image point under the cursor fixed while zooming.
        image_x, image_y = (x-ox)/old, (y-oy)/old
        self.paper_picker_zoom = new_zoom
        self.paper_picker_pan[0] = x - image_x*new_scale - (self.paper_picker_canvas.winfo_width()-self.paper_image.width*new_scale)/2
        self.paper_picker_pan[1] = y - image_y*new_scale - (self.paper_picker_canvas.winfo_height()-self.paper_image.height*new_scale)/2
        self._draw_paper_picker()

    def _paper_picker_wheel(self, event):
        self._paper_picker_zoom_at(event.x, event.y, 1.2 if event.delta > 0 else 1/1.2)

    def _paper_picker_pan_start(self, event):
        self.paper_picker_drag = (event.x, event.y, self.paper_picker_pan[0], self.paper_picker_pan[1])

    def _paper_picker_pan_move(self, event):
        if self.paper_picker_drag is None:
            return
        sx, sy, px, py = self.paper_picker_drag
        self.paper_picker_pan = [px + event.x-sx, py + event.y-sy]
        self._draw_paper_picker()

    def _pick_paper_point(self, event):
        if len(self.paper_points) >= 4:
            return
        ox, oy = self.paper_picker_offset
        scale = self.paper_picker_scale
        x, y = (event.x-ox)/scale, (event.y-oy)/scale
        iw, ih = self.paper_image.size
        if not (0 <= x < iw and 0 <= y < ih):
            return
        self.paper_points.append((x, y))
        if len(self.paper_points) == 4:
            self.paper_picker.destroy()
            self.paper_button.config(text='Фото совмещено')
            self.status.config(text='Фото листа совмещено по четырём точкам и показано под линиями DXF.')
            self.fit_view()
        else:
            self._draw_paper_picker()

    def clear_paper_photo(self):
        self.paper_image = None
        self._warped_cache_key = None
        self._warped_cache_image = None
        self.paper_path = None
        self.paper_points = []
        self.paper_pick_mode = False
        self.paper_tk_image = None
        self.paper_button.config(text='Загрузить фото листа…')
        self.paper_clear_button.config(state='disabled')
        self.status.config(text='Фото листа убрано.')
        self.draw()

    @staticmethod
    def _solve_linear_system(matrix, vector):
        """Решение небольшой системы 8x8 методом Гаусса."""
        a = [list(map(float, row)) + [float(v)] for row, v in zip(matrix, vector)]
        n = len(a)
        for col in range(n):
            pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
            if abs(a[pivot][col]) < 1e-12:
                raise ValueError('Опорные точки расположены слишком близко или вырождены.')
            a[col], a[pivot] = a[pivot], a[col]
            div = a[col][col]
            a[col] = [v / div for v in a[col]]
            for r in range(n):
                if r == col:
                    continue
                factor = a[r][col]
                if factor:
                    a[r] = [a[r][k] - factor * a[col][k] for k in range(n + 1)]
        return [a[i][-1] for i in range(n)]

    def _warped_paper_for_canvas(self):
        if self.paper_image is None or len(self.paper_points) != 4 or Image is None:
            return None
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        cache_key = (w, h, round(self.scale, 9), round(self.offset_x, 3), round(self.offset_y, 3), tuple(self.paper_points))
        if cache_key == self._warped_cache_key and self._warped_cache_image is not None:
            return self._warped_cache_image
        # PIL needs output(screen) -> input(photo) mapping. Solve this inverse
        # projective transform from DXF anchor positions to picked photo points.
        matrix, vector = [], []
        for cp, photo_pt in zip(self.calibration_points, self.paper_points):
            tx, ty = self._screen(*cp['point'])
            px, py = photo_pt
            matrix.append([tx, ty, 1, 0, 0, 0, -px * tx, -px * ty]); vector.append(px)
            matrix.append([0, 0, 0, tx, ty, 1, -py * tx, -py * ty]); vector.append(py)
        coeff = self._solve_linear_system(matrix, vector)
        warped = self.paper_image.transform((w, h), Image.Transform.PERSPECTIVE, coeff,
                                             resample=Image.Resampling.BICUBIC)
        # The paper should sit below the DXF linework; soften it so contours remain readable.
        alpha = warped.getchannel('A').point(lambda a: int(a * 0.62))
        warped.putalpha(alpha)
        result = ImageTk.PhotoImage(warped)
        self._warped_cache_key = cache_key
        self._warped_cache_image = result
        return result

    def _click_canvas(self, event):
        best = None
        best_dist = float('inf')
        for i, p in enumerate(self.pylons):
            sx, sy = self._screen(*p['center'])
            dist = (sx-event.x)**2 + (sy-event.y)**2
            if dist < best_dist and dist <= max(18, self.scale * 150)**2:
                best, best_dist = i, dist
        if best is not None:
            self._store_fields()
            self.select_pylon(best)
            self.long_entry.focus_set()

    def _store_fields(self):
        if self.pylons:
            vals = self.values[str(self.pylons[self.current]['handle'])]
            p = self.pylons[self.current]
            long_value = self.long_var.get().strip()
            end_value = self.end_var.get().strip()
            for value, target, label, entry in (
                (long_value, p.get('target_long', 0), 'длинной стороны', self.long_entry),
                (end_value, p.get('target_end', 0), 'торца', self.end_entry),
            ):
                if value and target > 0:
                    numeric = float(value)
                    if numeric < target / 10 or numeric > target * 10:
                        messagebox.showwarning('Подозрительный размер', f'Размер {label} ({value}) отличается от геометрии пилона на порядок. Проверь значение.', parent=self.window)
                        entry.focus_set()
                        entry.selection_range(0, 'end')
                        return
            vals['long'] = long_value
            vals['end'] = end_value
            self._refresh_list()
            self._publish_values()

    def _long_enter(self, _event=None):
        self._store_fields()
        self.end_entry.focus_set()
        self.end_entry.selection_range(0, 'end')
        return 'break'

    def _end_enter(self, _event=None):
        self._store_fields()
        if self.current < len(self.pylons) - 1:
            self.select_pylon(self.current + 1)
            self.long_entry.focus_set()
            self.long_entry.selection_range(0, 'end')
        else:
            self.status.config(text='Последний пилон заполнен. Не забудь экспортировать размеры, если хочешь их сохранить.')
        return 'break'

    def previous(self):
        self._store_fields()
        self.select_pylon(self.current - 1)

    def next(self):
        self._store_fields()
        self.select_pylon(self.current + 1)

    def fit_view(self):
        self.window.update_idletasks()
        w, h = max(100, self.canvas.winfo_width()), max(100, self.canvas.winfo_height())
        min_x, min_y, max_x, max_y = self.bounds
        dx, dy = max(max_x - min_x, 1), max(max_y - min_y, 1)
        self.scale = min((w - 60) / dx, (h - 60) / dy)
        self.offset_x = (w - dx * self.scale) / 2 - min_x * self.scale
        self.offset_y = (h - dy * self.scale) / 2 + max_y * self.scale
        self.draw()

    def _screen(self, x, y):
        return self.offset_x + x * self.scale, self.offset_y - y * self.scale

    def draw(self):
        if not hasattr(self, 'canvas'):
            return
        self.canvas.delete('all')
        if self.paper_image is not None and len(self.paper_points) == 4:
            try:
                self.paper_tk_image = self._warped_paper_for_canvas()
                if self.paper_tk_image is not None:
                    self.canvas.create_image(0, 0, image=self.paper_tk_image, anchor='nw')
            except Exception as exc:
                self.status.config(text=f'Не удалось совместить фото: {exc}')
        for item in self.items:
            coords = []
            for x, y in item['points']:
                sx, sy = self._screen(x, y)
                coords.extend((sx, sy))
            if len(coords) < 6:
                continue
            if item['kind'] == 'ПИЛОН':
                selected = item['index'] == (self.current + 1 if self.pylons else -1)
                state = self._completion(item)
                color = '#ffb74d' if selected else ('#62d98b' if state == 'введён' else ('#e6c65c' if state == 'частично' else '#e6e9ed'))
                width = 3 if selected else 2
                fill = '#5a432b' if selected else ('#244d36' if state == 'введён' else ('#4b4726' if state == 'частично' else ''))
            else:
                color, width, fill = '#6c8799', 1, ''
            self.canvas.create_polygon(*coords, fill=fill, outline=color, width=width)
            if item['kind'] == 'ПИЛОН' and self.scale > 0.00001:
                cx, cy = self._screen(*item['center'])
                self.canvas.create_text(cx, cy, text=str(item['index']), fill='#ffcc80' if item['index'] == self.current + 1 else '#b8c2cc', font=('', 10, 'bold'))
        if self.show_calibration_points:
            marker_colors = {'A': '#ff5252', 'B': '#40c4ff', 'C': '#ffd740', 'D': '#69f0ae'}
            for cp in self.calibration_points:
                sx, sy = self._screen(*cp['point'])
                color = marker_colors[cp['code']]
                r = 8
                self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill=color, outline='#ffffff', width=2)
                self.canvas.create_text(sx, sy-19, text=cp['code'], fill=color,
                                        font=('', 12, 'bold'))
                self.canvas.create_text(sx+13, sy+12, text=f"{cp['label']} · пилон {cp['pylon_index']}",
                                        anchor='w', fill=color, font=('', 9, 'bold'))
        if self.paper_image is not None and self.paper_pick_mode:
            for i, (px, py) in enumerate(self.paper_points):
                code = 'ABCD'[i]
                color = {'A': '#ff5252', 'B': '#40c4ff', 'C': '#ffd740', 'D': '#69f0ae'}[code]
                self.canvas.create_oval(px-7, py-7, px+7, py+7, fill=color, outline='white', width=2)
                self.canvas.create_text(px+12, py-12, text=code, fill=color, anchor='w', font=('', 12, 'bold'))
            if len(self.paper_points) < 4:
                self.canvas.create_text(16, 16, text=f'Укажи на фото точку {"ABCD"[len(self.paper_points)]}',
                                        anchor='nw', fill='#ffffff', font=('', 13, 'bold'))
        if self.pylons and not self.show_calibration_points and not self.paper_pick_mode:
            p = self.pylons[self.current]
            x, y = self._screen(*p['center'])
            self.canvas.create_oval(x-5, y-5, x+5, y+5, fill='#ff5722', outline='white', width=1)
            # Поля фиксированного экранного размера привязаны к сторонам
            # активного пилона; остальные пилоны остаются полностью видимыми.
            xs = [self._screen(px, py)[0] for px, py in p['points']]
            ys = [self._screen(px, py)[1] for px, py in p['points']]
            left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
            cw, ch = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
            long_x = (left + right) / 2
            # Держим поля заметно дальше от контура пилона, чтобы не
            # закрывать фактические размеры и размерные подписи на плане.
            long_y = top - 175
            end_x = right + 235
            end_y = (top + bottom) / 2
            # Если у торца нет места справа, ставим поле слева.
            if end_x + 85 > cw:
                end_x = left - 235
            # Не позволяем полям уходить за границы холста.
            long_x = max(95, min(cw - 95, long_x))
            long_y = max(75, min(ch - 45, long_y))
            end_x = max(85, min(cw - 85, end_x))
            end_y = max(65, min(ch - 65, end_y))
            self.canvas.create_line((left + right) / 2, top, long_x, long_y + 34,
                                    fill='#2687ff', width=2)
            self.canvas.create_line(right, (top + bottom) / 2, end_x, end_y,
                                    fill='#19b887', width=2)
            self.canvas.create_window(long_x, long_y, window=self.long_widget, width=168, anchor='center')
            self.canvas.create_window(end_x, end_y, window=self.end_widget, width=145, anchor='center')

    def _zoom_at(self, x, y, factor):
        old = self.scale
        self.scale = max(1e-8, min(old * factor, 1e8))
        self.offset_x = x - (x - self.offset_x) * self.scale / old
        self.offset_y = y - (y - self.offset_y) * self.scale / old
        self._warped_cache_key = None
        self._warped_cache_image = None
        self.draw()

    def _wheel_zoom(self, event):
        self._zoom_at(event.x, event.y, 1.15 if event.delta > 0 else 1 / 1.15)

    def _pan_start(self, event):
        self.drag_origin = (event.x, event.y, self.offset_x, self.offset_y)

    def _pan_move(self, event):
        if self.drag_origin:
            x, y, ox, oy = self.drag_origin
            self.offset_x, self.offset_y = ox + event.x - x, oy + event.y - y
            self._warped_cache_key = None
            self._warped_cache_image = None
            self.draw()
