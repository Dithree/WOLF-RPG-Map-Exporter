#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plan B: offline transparent event-layer renderer for WOLF RPG Editor.

Reads a .mps map file plus the game Data folder and produces a PNG containing
only the events, on a fully transparent background, using the actual game
graphics (CharaChip files or map-chip tiles from TileSetData.dat).

This does NOT use the editor.  It supports .mps 0x65/0x66 event sections.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path
from typing import Optional

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_mps_events as pe
from wolfrpg import parse_tileset_dat

# In the editor export pipeline the canvas is always 32 px per map tile.
# Game tile_size (16/32/40) is read from Game.dat; scale = 32 / game_tile_size.
DEFAULT_OUTPUT_TILE_PX = 32


def parse_game_settings(data_dir: Path) -> dict:
    """Return a few settings from BasicData/Game.dat needed for event graphics."""
    game_dat = Path(data_dir) / 'BasicData' / 'Game.dat'
    settings = {
        'tile_size': 16,
        'directions_image': 4,
        'animation_patterns': 3,
    }
    if not game_dat.exists():
        return settings
    b = game_dat.read_bytes()
    try:
        # magic [0,'W',0,0,'O','L',0,'F','M'] + version_header u1 + len u4
        off = 9
        if b[off] not in (0x55, 0):  # v3 / old
            return settings
        off += 1
        (n,) = struct.unpack_from('<I', b, off)
        off += 4
        if n >= 8 and off + n <= len(b):
            settings['tile_size'] = b[off + 0]
            settings['directions_image'] = b[off + 1]
            settings['animation_patterns'] = b[off + 7]
    except Exception:
        pass
    return settings


def load_tilesets(data_dir: Path):
    tileset_path = Path(data_dir) / 'BasicData' / 'TileSetData.dat'
    if tileset_path.exists():
        try:
            return parse_tileset_dat(tileset_path)
        except Exception:
            return []
    return []


def _actual_row(raw_row: int) -> int:
    # Stored row byte packs the actual row: actual = (raw >> 1) - 1.
    return (raw_row >> 1) - 1


def select_visible_page(event: dict) -> Optional[dict]:
    """Pick the first event page that has a visible graphic.

    The first page is normally the default page in WOLF RPG Editor.  If a page
    has no graphic (empty filename and chip_id == -1) it is invisible, so skip.
    """
    for page in event.get('pages', []):
        fn = page.get('filename') or ''
        chip = page.get('chip_id')
        if fn or (chip is not None and chip != 0xFFFFFFFF):
            return page
    return None


def _frame_grid_for_filename(filename: str, image: Image.Image, settings: dict,
                             max_raw_row: int) -> tuple[int, int]:
    """Return (columns, rows) for a CharaChip file.

    WOLF character walk graphics use `animation_patterns` columns.  The sample
    game's non-[Chara] sheets (animals/specials/monsters) use twice that many
    columns (each logical pattern is split into two cells).

    Rows: 4 for normal 4-direction sheets; use 8 only when the image actually
    stores 8-direction rows (observed raw row >= 8 means actual row >= 3 and
    the image height is divisible by 8).
    """
    w, h = image.size
    patterns = int(settings.get('animation_patterns', 3) or 3)
    dirs = int(settings.get('directions_image', 4) or 4)

    # Row count: trust an 8-direction sheet only when the stored row can only
    # fit in an 8-row sheet (actual row > 3) and the height divides by 8.
    rows = 4
    max_actual_row = (max_raw_row >> 1) - 1
    if dirs >= 8 and h % 8 == 0 and max_actual_row > 3:
        rows = 8
    if h % rows != 0:
        rows = 8 if h % 8 == 0 else 4

    # Column count: try both `patterns` and `patterns * 2` when the width allows.
    # Choose the grid whose cell aspect ratio is closest to square; this
    # distinguishes 3-column monster sheets (2x2 sprites) from 6-column sheets
    # used by some sample-game animals.
    candidates = []
    for c in (patterns, patterns * 2):
        if c > 0 and w % c == 0:
            fw = w // c
            fh = h // rows
            aspect = fw / fh if fh else 1.0
            score = abs(aspect - 1.0)
            candidates.append((score, c))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        columns = candidates[0][1]
    else:
        columns = patterns if w % patterns == 0 else 1
    return columns, rows


def _load_char_frame(page: dict, image: Image.Image, settings: dict,
                     max_raw_row: int) -> Image.Image:
    fn = page.get('filename') or ''
    cols, rows = _frame_grid_for_filename(fn, image, settings, max_raw_row)
    fw = image.width // cols
    fh = image.height // rows
    raw_row = int(page.get('row', 0))
    col = int(page.get('col', 0))
    row = _actual_row(raw_row)
    row = max(0, min(rows - 1, row))
    col = max(0, min(cols - 1, col))
    box = (col * fw, row * fh, (col + 1) * fw, (row + 1) * fh)
    frame = image.crop(box)
    return frame


def _load_mapchip_frame(page: dict, base_img: Image.Image) -> Image.Image:
    chip_id = int(page.get('chip_id', 0xFFFFFFFF))
    # Base tileset images are always 8 tiles per row.
    tile_px = base_img.width // 8
    row = chip_id // 8
    col = chip_id % 8
    box = (col * tile_px, row * tile_px, (col + 1) * tile_px, (row + 1) * tile_px)
    try:
        return base_img.crop(box)
    except Exception:
        return Image.new('RGBA', (tile_px, tile_px), (0, 0, 0, 0))


def _apply_opacity(frame: Image.Image, opacity: int) -> Image.Image:
    if opacity is None or opacity >= 255:
        return frame
    if opacity <= 0:
        return Image.new('RGBA', frame.size, (0, 0, 0, 0))
    if frame.mode != 'RGBA':
        frame = frame.convert('RGBA')
    r, g, b, a = frame.split()
    a = a.point(lambda v: v * opacity // 255)
    return Image.merge('RGBA', (r, g, b, a))


def _anchor_char_frame(frame: Image.Image, tile_x: int, tile_y: int,
                       tile_out: int) -> tuple[int, int]:
    """Bottom-center anchor for character-style sprites on a tile."""
    w, h = frame.size
    return tile_x * tile_out + (tile_out - w) // 2, tile_y * tile_out + tile_out - h


def _anchor_tile_frame(frame: Image.Image, tile_x: int, tile_y: int,
                       tile_out: int) -> tuple[int, int]:
    """Map-chip events fill the whole tile."""
    return tile_x * tile_out, tile_y * tile_out


def collect_event_items(map_path, data_dir: Path, settings: dict, tilesets: list) -> list:
    """Parse one .mps and return render items.

    Each item: dict(x, y, kind, frame, opacity, anchor).
    """
    m = pe.parse_map(map_path)
    items = []
    base_img_cache = {}

    for ev in m['events']:
        page = select_visible_page(ev)
        if page is None:
            continue
        x = int(ev.get('x', 0))
        y = int(ev.get('y', 0))
        fn = page.get('filename') or ''
        chip = page.get('chip_id')
        frame = None
        kind = 'tile'
        if fn:
            path = Path(data_dir) / fn
            if not path.exists():
                continue
            img = Image.open(path).convert('RGBA')
            # max raw row for this file: use current page row; a per-file max
            # would need a second pass, this is enough for the row decision.
            max_raw_row = int(page.get('row', 0))
            frame = _load_char_frame(page, img, settings, max_raw_row)
            kind = 'chara'
        else:
            # numeric chip_id -> base tileset tile
            ts_index = int(m.get('tileset', 0) or 0)
            if not tilesets:
                continue
            if ts_index < 0 or ts_index >= len(tilesets):
                ts_index = 0
            base_file = tilesets[ts_index].base_file
            if not base_file:
                continue
            if base_file not in base_img_cache:
                bp = Path(data_dir) / base_file
                if not bp.exists():
                    continue
                base_img_cache[base_file] = Image.open(bp).convert('RGBA')
            frame = _load_mapchip_frame(page, base_img_cache[base_file])
            kind = 'tile'
        if frame is None:
            continue
        frame = _apply_opacity(frame, int(page.get('opacity', 255)))
        items.append({
            'x': x,
            'y': y,
            'kind': kind,
            'frame': frame,
            'opacity': int(page.get('opacity', 255)),
        })
    return items


def render_event_layer(map_path, data_dir, out_png, scale: Optional[float] = None,
                       settings: Optional[dict] = None,
                       tilesets: Optional[list] = None) -> int:
    """Render events to a transparent PNG.  Returns number of events drawn.

    `scale` is the number of output pixels per source tile.  Defaults to
    32 / game_tile_size so it matches the editor exporter's 32px/tile canvas.
    """
    map_path = Path(map_path)
    data_dir = Path(data_dir)
    if settings is None:
        settings = parse_game_settings(data_dir)
    if tilesets is None:
        tilesets = load_tilesets(data_dir)

    m = pe.parse_map(map_path)
    if scale is None:
        tile_size = int(settings.get('tile_size', 16) or 16)
        scale = DEFAULT_OUTPUT_TILE_PX / tile_size

    items = collect_event_items(map_path, data_dir, settings, tilesets)

    W = int(m['width'] * DEFAULT_OUTPUT_TILE_PX)
    H = int(m['height'] * DEFAULT_OUTPUT_TILE_PX)
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))

    for it in items:
        frame = it['frame']
        if scale != 1.0:
            new_size = (max(1, round(frame.width * scale)),
                        max(1, round(frame.height * scale)))
            # NEAREST keeps pixel-art crisp.
            frame = frame.resize(new_size, Image.NEAREST)
        if it['kind'] == 'chara':
            pos = _anchor_char_frame(frame, it['x'], it['y'], DEFAULT_OUTPUT_TILE_PX)
        else:
            pos = _anchor_tile_frame(frame, it['x'], it['y'], DEFAULT_OUTPUT_TILE_PX)
        canvas.paste(frame, pos, frame)

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png)
    return len(items)


def main():
    if len(sys.argv) < 3:
        print('usage: python render_event_layer.py <map.mps> <out.png> [data_dir]')
        return 1
    map_path = Path(sys.argv[1])
    out_png = Path(sys.argv[2])
    data_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else map_path.parent.parent
    n = render_event_layer(map_path, data_dir, out_png)
    print(f'wrote {out_png} with {n} events')
    return 0


if __name__ == '__main__':
    sys.exit(main())
