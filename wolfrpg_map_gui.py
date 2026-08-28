# -*- coding: utf-8 -*-
"""WOLF RPG Editor offline map + event layer renderer GUI (mimics RPGMakerMapExporter).

Features:
  - Select Data folder -> map list
  - Preview map layer; optional event-layer overlay
  - Click an event in preview to toggle show/hide (hidden = semi-transparent)
  - Export: event layer only / map layer only / both (hidden events excluded from event export)
"""
import sys
import tempfile
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

sys.path.insert(0, r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png')
from PIL import Image, ImageTk
from offline_render_quadrant import render
import render_event_layer as rel

TILE = 32
THIS_PC = r'::{20D04FE0-3AEA-1069-A2D8-08002B30309D}'
CONFIG_PATH = Path.home() / '.wolfrpg_map_gui.json'

# ---- i18n strings (zh / ja / en) ----
STRINGS = {
    'app_title': {'zh': 'WOLF RPG 地图导出工具v1.0', 'ja': 'WOLF RPG マップ出力ツールv1.0', 'en': 'WOLF RPG Map Exporter v1.0'},
    'select_game': {'zh': '选择游戏(Data 文件夹)', 'ja': 'ゲーム選択(Data フォルダ)', 'en': 'Select Game (Data folder)'},
    'not_selected': {'zh': '未选择', 'ja': '未選択', 'en': 'Not selected'},
    'select_game_title': {'zh': '选择游戏 Data 文件夹', 'ja': 'ゲームのDataフォルダを選択', 'en': 'Select game Data folder'},
    'map_list': {'zh': '地图列表（勾选=导出）:', 'ja': 'マップ一覧（チェック=出力）:', 'en': 'Map list (check = export):'},
    'select_all': {'zh': '全选', 'ja': '全選択', 'en': 'Select all'},
    'invert': {'zh': '反选', 'ja': '反転', 'en': 'Invert'},
    'events_label': {'zh': '事件层（点事件切换显隐）', 'ja': 'イベント層（クリックで表示切替）', 'en': 'Event layer (click to toggle)'},
    'map_label': {'zh': '地图层', 'ja': 'マップ層', 'en': 'Map layer'},
    'both_label': {'zh': '两者', 'ja': '両方', 'en': 'Both'},
    'export_current': {'zh': '导出当前地图', 'ja': '現在のマップを出力', 'en': 'Export current map'},
    'export_selected': {'zh': '导出所选地图', 'ja': '選択したマップを出力', 'en': 'Export selected maps'},
    'copy_clipboard': {'zh': '复制到剪贴板', 'ja': 'クリップボードにコピー', 'en': 'Copy to clipboard'},
    'lang_menu': {'zh': '语言', 'ja': '言語', 'en': 'Language'},
    'lang_zh': {'zh': '中文', 'ja': '中文', 'en': 'Chinese'},
    'lang_ja': {'zh': '日本語', 'ja': '日本語', 'en': 'Japanese'},
    'lang_en': {'zh': 'English', 'ja': 'English', 'en': 'English'},
    'tip_need_game': {'zh': '请先选择游戏（Data 文件夹）', 'ja': '先にゲーム（Dataフォルダ）を選択してください', 'en': 'Please select a game (Data folder) first'},
    'tip_need_map': {'zh': '请先选择一张地图', 'ja': '先にマップを選択してください', 'en': 'Please select a map first'},
    'tip_need_check': {'zh': '请先勾选要导出的地图', 'ja': '出力するマップをチェックしてください', 'en': 'Please check the maps to export'},
    'tip_select_folder': {'zh': '选择导出文件夹', 'ja': '出力先フォルダを選択', 'en': 'Choose output folder'},
    'tip_save_png': {'zh': 'PNG 图片', 'ja': 'PNG画像', 'en': 'PNG image'},
    'done_exported': {'zh': '已导出', 'ja': '出力しました', 'en': 'Exported'},
    'done_exported_to': {'zh': '已导出 {} 张到 {}', 'ja': '{}枚を{}に出力しました', 'en': 'Exported {} file(s) to {}'},
    'fail_export': {'zh': '导出失败', 'ja': '出力に失敗', 'en': 'Export failed'},
    'err_render': {'zh': '渲染失败', 'ja': 'レンダリング失敗', 'en': 'Render failed'},
    'err_clipboard': {'zh': '剪贴板失败', 'ja': 'クリップボード失敗', 'en': 'Clipboard failed'},
    'err': {'zh': '错误', 'ja': 'エラー', 'en': 'Error'},
    'hint': {'zh': '提示', 'ja': 'ヒント', 'en': 'Hint'},
    'done': {'zh': '完成', 'ja': '完了', 'en': 'Done'},
    'copied': {'zh': '已复制到剪贴板（可粘贴到 Word 或文件夹）', 'ja': 'クリップボードにコピーしました（Wordやフォルダに貼り付け可能）', 'en': 'Copied to clipboard (paste into Word or a folder)'},
}


def _bind_wheel(widget, canvas):
    """Bind middle-mouse-wheel to canvas scroll for a widget."""
    widget.bind('<MouseWheel>', lambda e: canvas.yview_scroll(int(-e.delta / 120), 'units'))


def _copy_image_and_file_to_clipboard(pil_img, png_path):
    """Copy an image (CF_DIB) and a file path (CF_HDROP) to the Windows clipboard.

    - CF_DIB: pastes as an image into Word / Paint.
    - CF_HDROP: pastes as a file into a folder (copies the PNG).
    """
    import io
    import win32clipboard
    from PIL import Image as _Img
    # Build DIB bytes: BMP without the 14-byte BITMAPFILEHEADER.
    rgb = pil_img.convert('RGB')
    bio = io.BytesIO()
    rgb.save(bio, 'BMP')
    dib = bio.getvalue()[14:]

    # File list for CF_HDROP.
    files = [str(png_path)]

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        try:
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
        except Exception:
            pass
        try:
            win32clipboard.SetClipboardData(win32clipboard.CF_HDROP, files)
        except Exception:
            pass
    finally:
        win32clipboard.CloseClipboard()


def _load_last_dir():
    try:
        d = json.loads(CONFIG_PATH.read_text(encoding='utf-8')).get('last_dir')
        return d if d and Path(d).exists() else None
    except Exception:
        return None


def _save_last_dir(d):
    try:
        CONFIG_PATH.write_text(json.dumps({'last_dir': str(d)}), encoding='utf-8')
    except Exception:
        pass


class WolfMapGUI:
    def __init__(self, root):
        self.root = root
        self.lang = 'zh'
        root.title(STRINGS['app_title']['zh'])
        root.geometry("1000x680")
        self.map_dir = None
        self.data_root = None
        self.map_path = None
        self.map_vars = {}        # stem -> tk.BooleanVar (checked for export)
        self.map_stems = []       # ordered list of stems
        self.events = []          # list of (x,y,kind,frame,opacity)
        self.hidden = set()       # current map's hidden set (persisted per-map)
        self.hidden_map = {}      # stem -> set of (x,y) hidden events
        self.current_img = None
        self._press = None
        self._moved = False
        self._build_ui()

    def tr(self, key):
        d = STRINGS.get(key, {})
        return d.get(self.lang) or d.get('zh') or key

    # ---------- UI ----------
    def _build_ui(self):
        menubar = tk.Menu(self.root)
        langmenu = tk.Menu(menubar, tearoff=0)
        self.lang_var = tk.StringVar(value=self.lang)
        for code, name_key in [('zh', 'lang_zh'), ('ja', 'lang_ja'), ('en', 'lang_en')]:
            langmenu.add_radiobutton(label=self.tr(name_key), value=code,
                                     variable=self.lang_var,
                                     command=lambda c=code: self._set_lang(c))
        menubar.add_cascade(label=self.tr('lang_menu'), menu=langmenu)
        self.root.config(menu=menubar)
        self._lang_menu_label = menubar
        self._langmenu = langmenu
        top = tk.Frame(self.root)
        top.pack(fill=tk.X, padx=6, pady=6)
        self.btn_select = tk.Button(top, text=self.tr('select_game'), command=self.select_game)
        self.btn_select.pack(side=tk.LEFT)
        self.dir_lbl = tk.Label(top, text=self.tr('not_selected'), anchor='w', fg='#555')
        self.dir_lbl.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        body = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=6)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        left = tk.Frame(body)
        hdr = tk.Frame(left)
        hdr.pack(fill=tk.X)
        self.lbl_map_list = tk.Label(hdr, text=self.tr('map_list'))
        self.lbl_map_list.pack(side=tk.LEFT)
        self.btn_all = tk.Button(hdr, text=self.tr('select_all'), command=self.select_all)
        self.btn_all.pack(side=tk.LEFT, padx=2)
        self.btn_inv = tk.Button(hdr, text=self.tr('invert'), command=self.invert_selection)
        self.btn_inv.pack(side=tk.LEFT, padx=2)
        # Scrollable canvas holding per-map checkbuttons
        self.map_canvas = tk.Canvas(left, width=200, bg='white', highlightthickness=1, highlightbackground='#aaa')
        self.map_scroll = tk.Scrollbar(left, orient=tk.VERTICAL, command=self.map_canvas.yview)
        self.map_canvas.configure(yscrollcommand=self.map_scroll.set)
        self.map_list_frame = tk.Frame(self.map_canvas)
        self.map_list_frame.bind('<Configure>',
                                 lambda e: self.map_canvas.configure(scrollregion=self.map_canvas.bbox('all')))
        self.map_canvas.create_window((0, 0), window=self.map_list_frame, anchor='nw')
        self.map_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.map_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.map_canvas.bind('<MouseWheel>', lambda e: self.map_canvas.yview_scroll(int(-e.delta / 120), 'units'))
        self.map_list_frame.bind('<MouseWheel>',
                                 lambda e: self.map_canvas.yview_scroll(int(-e.delta / 120), 'units'))
        body.add(left, minsize=200)

        right = tk.Frame(body)
        # scrollable full-size preview canvas
        pv = tk.Frame(right)
        pv.pack(fill=tk.BOTH, expand=True)
        self.hbar = tk.Scrollbar(pv, orient=tk.HORIZONTAL)
        self.vbar = tk.Scrollbar(pv, orient=tk.VERTICAL)
        self.canvas = tk.Canvas(pv, bg='#ffffff', xscrollcommand=self.hbar.set,
                                yscrollcommand=self.vbar.set)
        self.hbar.config(command=self.canvas.xview)
        self.vbar.config(command=self.canvas.yview)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.hbar.grid(row=1, column=0, sticky='ew')
        self.vbar.grid(row=0, column=1, sticky='ns')
        pv.grid_rowconfigure(0, weight=1)
        pv.grid_columnconfigure(0, weight=1)
        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_click)
        self._press = None
        self._moved = False
        body.add(right, minsize=500)

        bottom = tk.Frame(self.root)
        bottom.pack(fill=tk.X, padx=6, pady=6)
        self.export_mode = tk.StringVar(value='both')
        self.rb_events = tk.Radiobutton(bottom, text=self.tr('events_label'), variable=self.export_mode,
                                        value='events', command=self.render_preview)
        self.rb_events.pack(side=tk.LEFT)
        self.rb_map = tk.Radiobutton(bottom, text=self.tr('map_label'), variable=self.export_mode,
                                     value='map', command=self.render_preview)
        self.rb_map.pack(side=tk.LEFT)
        self.rb_both = tk.Radiobutton(bottom, text=self.tr('both_label'), variable=self.export_mode,
                                      value='both', command=self.render_preview)
        self.rb_both.pack(side=tk.LEFT)
        self.btn_export_cur = tk.Button(bottom, text=self.tr('export_current'), command=self.export_current_map)
        self.btn_export_cur.pack(side=tk.LEFT)
        self.btn_export_sel = tk.Button(bottom, text=self.tr('export_selected'), command=self.export_map)
        self.btn_export_sel.pack(side=tk.LEFT, padx=8)
        self.btn_copy = tk.Button(bottom, text=self.tr('copy_clipboard'), command=self.copy_to_clipboard)
        self.btn_copy.pack(side=tk.LEFT)

    def _set_lang(self, code):
        self.lang = code
        # update menu cascade label + radios
        self._lang_menu_label.entryconfig(0, label=self.tr('lang_menu'))
        for i, (c, k) in enumerate([('zh', 'lang_zh'), ('ja', 'lang_ja'), ('en', 'lang_en')]):
            self._langmenu.entryconfig(i, label=self.tr(k))
        # update widgets
        self.root.title(self.tr('app_title'))
        self.btn_select.config(text=self.tr('select_game'))
        self.dir_lbl.config(text=self.tr('not_selected'))
        self.lbl_map_list.config(text=self.tr('map_list'))
        self.btn_all.config(text=self.tr('select_all'))
        self.btn_inv.config(text=self.tr('invert'))
        self.rb_events.config(text=self.tr('events_label'))
        self.rb_map.config(text=self.tr('map_label'))
        self.rb_both.config(text=self.tr('both_label'))
        self.btn_export_cur.config(text=self.tr('export_current'))
        self.btn_export_sel.config(text=self.tr('export_selected'))
        self.btn_copy.config(text=self.tr('copy_clipboard'))

    # ---------- data ----------
    def select_game(self):
        last = _load_last_dir()
        initial = last if last else THIS_PC
        try:
            d = filedialog.askdirectory(initialdir=initial, title=self.tr('select_game_title'))
        except Exception:
            d = filedialog.askdirectory(title=self.tr('select_game_title'))
        if not d:
            return
        _save_last_dir(d)
        cand = Path(d)
        if (cand / 'MapData').exists():
            self.data_root = cand
            cand = cand / 'MapData'
        elif (cand.parent / 'MapData').exists():
            self.data_root = cand.parent
            cand = cand.parent / 'MapData'
        self.map_dir = cand
        self.dir_lbl.config(text=str(cand))
        # rebuild checkbox list
        for w in self.map_list_frame.winfo_children():
            w.destroy()
        self.map_vars = {}
        self.map_stems = []
        for idx, m in enumerate(sorted(cand.glob('Map*.mps'))):
            stem = m.stem
            self.map_stems.append(stem)
            display = stem
            var = tk.BooleanVar(value=False)
            self.map_vars[stem] = var
            bg = '#f8f8f8' if idx % 2 == 0 else '#ffffff'
            row = tk.Frame(self.map_list_frame, bg=bg)
            row.pack(fill=tk.X, anchor='w')
            cb = tk.Checkbutton(row, text='', variable=var, command=lambda: None, bg=bg, activebackground=bg)
            cb.pack(side=tk.LEFT)
            lbl = tk.Label(row, text=display, anchor='w', cursor='hand2', bg=bg, fg='#222')
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            lbl.bind('<Button-1>', lambda e, s=stem: self.preview_map(s))
            _bind_wheel(row, self.map_canvas)
            _bind_wheel(cb, self.map_canvas)
            _bind_wheel(lbl, self.map_canvas)

    def _require_data_root(self):
        if not self.data_root or not Path(self.data_root).exists():
            messagebox.showinfo(self.tr('hint'), self.tr('tip_need_game'))
            return False
        return True

    def preview_map(self, stem):
        if not self._require_data_root():
            return
        p = self.map_dir / f'{stem}.mps'
        if not p.exists():
            return
        self.map_path = p
        self.hidden = self.hidden_map.setdefault(stem, set())
        self.events = []
        try:
            settings = rel.parse_game_settings(self.data_root)
            tilesets = rel.load_tilesets(self.data_root)
            items = rel.collect_event_items(str(p), self.data_root, settings, tilesets)
            self.events = [(it['x'], it['y'], it['kind'], it['frame'], it.get('opacity', 255))
                           for it in items]
        except Exception:
            self.events = []
        self.render_preview()

    def select_all(self):
        for v in self.map_vars.values():
            v.set(True)

    def invert_selection(self):
        for v in self.map_vars.values():
            v.set(not v.get())

    # ---------- rendering ----------
    def render_preview(self):
        if not self.map_path:
            return
        mode = self.export_mode.get()
        tmp = Path(tempfile.gettempdir()) / f'{self.map_path.stem}_prev.png'
        try:
            if mode == 'events':
                # Preview only the event layer on a white background so events are visible.
                m = rel.pe.parse_map(str(self.map_path))
                canvas = Image.new('RGBA', (m['width'] * TILE, m['height'] * TILE), (255, 255, 255, 255))
                self._composite_events(canvas, semi_hidden=True)
                base = canvas
            else:
                render(str(self.map_path), str(tmp), str(self.data_root))
                base = Image.open(tmp).convert('RGBA')
                if mode == 'both':
                    self._composite_events(base, semi_hidden=True)
        except Exception as e:
            messagebox.showerror(self.tr('err_render'), str(e))
            return
        self._display(base)

    def _composite_events(self, base, semi_hidden):
        for (x, y, kind, frame, opacity) in self.events:
            hidden = (x, y) in self.hidden
            f = frame
            if hidden:
                f = f.copy()
                # half transparent
                alpha = f.getchannel('A').point(lambda a: int(a * 0.35))
                f.putalpha(alpha)
            if kind == 'chara':
                pos = rel._anchor_char_frame(f, x, y, TILE)
            else:
                pos = rel._anchor_tile_frame(f, x, y, TILE)
            base.paste(f, pos, f)

    def _display(self, img):
        # Full-size display with scrollbars (no auto-scaling).
        self.current_img = ImageTk.PhotoImage(img)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=self.current_img)
        self.canvas.configure(scrollregion=(0, 0, img.width, img.height))

    def on_press(self, evt):
        self._press = (evt.x, evt.y)
        self._moved = False
        self.canvas.scan_mark(evt.x, evt.y)

    def on_drag(self, evt):
        if self._press is None:
            return
        if abs(evt.x - self._press[0]) > 2 or abs(evt.y - self._press[1]) > 2:
            self._moved = True
        self.canvas.scan_dragto(evt.x, evt.y, gain=1)

    def on_click(self, evt):
        if self._moved:
            self._moved = False
            return
        if not self.map_path or self.export_mode.get() == 'map' or not self.events:
            return
        cx = int(self.canvas.canvasx(evt.x))
        cy = int(self.canvas.canvasy(evt.y))
        tile_x = cx // TILE
        tile_y = cy // TILE
        hit = [e for e in self.events if e[0] == tile_x and e[1] == tile_y]
        if not hit:
            return
        key = (hit[0][0], hit[0][1])
        if key in self.hidden:
            self.hidden.discard(key)
        else:
            self.hidden.add(key)
        self.render_preview()

    # ---------- export ----------
    def export_current_map(self):
        """Export the currently previewed map (single file)."""
        if not self._require_data_root():
            return
        if not self.map_path or not self.map_path.exists():
            messagebox.showinfo(self.tr('hint'), self.tr('tip_need_map'))
            return
        mode = self.export_mode.get()
        out = filedialog.asksaveasfilename(defaultextension='.png',
                                           initialfile=f'{self.map_path.stem}.png',
                                           filetypes=[(self.tr('tip_save_png'), '*.png')])
        if not out:
            return
        try:
            self._export_single(self.map_path, Path(out), mode)
            messagebox.showinfo(self.tr('done'), self.tr('done_exported') + f' {out}')
        except Exception as e:
            messagebox.showerror(self.tr('fail_export'), str(e))

    def export_map(self):
        if not self._require_data_root():
            return
        checked = [s for s in self.map_stems if self.map_vars.get(s) and self.map_vars[s].get()]
        if not checked:
            messagebox.showinfo(self.tr('hint'), self.tr('tip_need_check'))
            return
        out_dir = filedialog.askdirectory(title=self.tr('tip_select_folder'))
        if not out_dir:
            return
        mode = self.export_mode.get()
        out_dir = Path(out_dir)
        ok = 0
        errs = []
        for stem in checked:
            mp = self.map_dir / f'{stem}.mps'
            try:
                self._export_single(mp, out_dir / f'{stem}.png', mode)
                ok += 1
            except Exception as e:
                errs.append(f'{stem}: {e}')
        msg = self.tr('done_exported_to').format(ok, out_dir)
        if errs:
            msg += "\n" + self.tr('fail_export') + ":\n" + "\n".join(errs[:10])
        messagebox.showinfo(self.tr('done'), msg)

    def _events_for(self, map_path):
        try:
            settings = rel.parse_game_settings(self.data_root)
            tilesets = rel.load_tilesets(self.data_root)
            items = rel.collect_event_items(str(map_path), self.data_root, settings, tilesets)
            return [(it['x'], it['y'], it['kind'], it['frame'], it.get('opacity', 255))
                    for it in items]
        except Exception:
            return []

    def _export_single(self, map_path, out_path, mode):
        if mode in ('map', 'both'):
            render(str(map_path), str(out_path), str(self.data_root))
        hidden = self.hidden_map.get(Path(map_path).stem, set())
        if mode == 'both':
            base = Image.open(out_path).convert('RGBA')
            events = self._events_for(map_path)
            self._composite_events_list(base, events, hidden, semi_hidden=False)
            base.convert('RGB').save(out_path)
        elif mode == 'events':
            self._export_events_only(map_path, out_path, hidden)

    def _export_events_only(self, map_path, out_path, hidden=None):
        m = rel.pe.parse_map(str(map_path))
        W = m['width'] * TILE
        H = m['height'] * TILE
        canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        events = self._events_for(map_path)
        if hidden is None:
            hidden = self.hidden_map.get(Path(map_path).stem, set())
        self._composite_events_list(canvas, events, hidden, semi_hidden=False)
        canvas.convert('RGB').save(out_path)

    def _composite_events_list(self, base, events, hidden, semi_hidden):
        for (x, y, kind, frame, opacity) in events:
            if (x, y) in hidden:
                if not semi_hidden:
                    continue
                f = frame.copy()
                f.putalpha(f.getchannel('A').point(lambda a: int(a * 0.35)))
            else:
                f = frame
            if kind == 'chara':
                pos = rel._anchor_char_frame(f, x, y, TILE)
            else:
                pos = rel._anchor_tile_frame(f, x, y, TILE)
            base.paste(f, pos, f)

    def copy_to_clipboard(self):
        if not self._require_data_root():
            return
        if not self.map_path:
            messagebox.showinfo(self.tr('hint'), self.tr('tip_need_map'))
            return
        tmp = Path(tempfile.gettempdir()) / f'{self.map_path.stem}_copy.png'
        try:
            mode = self.export_mode.get()
            hidden = self.hidden_map.get(self.map_path.stem, set())
            if mode == 'events':
                # Copy only the event layer (transparent), hidden events excluded.
                m = rel.pe.parse_map(str(self.map_path))
                base = Image.new('RGBA', (m['width'] * TILE, m['height'] * TILE), (0, 0, 0, 0))
                self._composite_events_list(base, self.events, hidden, semi_hidden=False)
            else:
                render(str(self.map_path), str(tmp), str(self.data_root))
                base = Image.open(tmp).convert('RGBA')
                if mode == 'both':
                    # Exclude hidden events from the copied image (not semi-transparent).
                    self._composite_events_list(base, self.events, hidden, semi_hidden=False)
            self._display(base)
            # save the final image to a temp file (also used for file-drop copy)
            final = Path(tempfile.gettempdir()) / f'{self.map_path.stem}_final.png'
            base.convert('RGB').save(final)
            # Put image + file path on the Windows clipboard so it can be
            # pasted into Word (image) or into a folder (file copy).
            try:
                _copy_image_and_file_to_clipboard(base, final)
                messagebox.showinfo(self.tr('hint'), self.tr('copied'))
            except Exception as ce:
                messagebox.showerror(self.tr('err_clipboard'), str(ce))
        except Exception as e:
            messagebox.showerror(self.tr('err'), str(e))


if __name__ == '__main__':
    root = tk.Tk()
    WolfMapGUI(root)
    root.mainloop()