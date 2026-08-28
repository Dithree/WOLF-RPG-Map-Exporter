#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline renderer using the solved quadrant compositor and layer alpha compositing.

Verified rules (controlled TestManual experiments):
  * Layer order: 图层1(bottom) -> 图层2 -> 图层3(top), alpha composited.
  * Autotile raw_aid mapping (from palette screenshot + E/B/C/D tests):
        raw_aid = palette_id + 1
        raw_aid 1 = empty/invisible fill
        raw_aid 2 = auto_files[0]  (id1: Wall-Up1)
        raw_aid 3 = auto_files[1]  (id2: Wall-Up2)
        raw_aid 4 = auto_files[2]  (id3: t_room01)
        raw_aid 5 = auto_files[3]  (id4: t_room02, semi-transparent)
        raw_aid 6 = auto_files[4]  (id5: t_room03)
        raw_aid 7 = auto_files[5]  (id6: t_castle03, opaque)
  * Each autotile is a 32x32 tile built from four 16x16 quadrants:
        digit 0..4 selects row 0..4 of the autotile strip directly.
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wolfrpg_067 import decode_mps_0x67, parse_067_header
from wolfrpg import parse_mps, parse_tileset_dat
from offline_render_base import load_base_tiles, tile_rc, find_tileset_dat, resolve_asset_file

TILE = 32
MAPPING_DIR = Path(__file__).resolve().parent / 'mappings'
OVERRIDE_DIR = Path(__file__).resolve().parent / 'overrides'


def load_override(map_path):
    """Return override dict for a map, or None."""
    p = OVERRIDE_DIR / f'{Path(map_path).stem}.json'
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'[warn] failed to load override {p}: {e}', file=sys.stderr)
    return None


RADIUS = 4


def _tri_key(layers, x, y, w, h):
    if x < 0 or y < 0 or x >= w or y >= h:
        return (0, 0, 0)
    return (layers[0][y][x], layers[1][y][x], layers[2][y][x])


def _build_lookup9(override, layers, w, h):
    """Build a 9x9-neighborhood -> override entry lookup table."""
    table = {}
    for y in range(h):
        for x in range(w):
            feat = tuple(v for dy in range(-RADIUS, RADIUS + 1) for dx in range(-RADIUS, RADIUS + 1)
                         for v in _tri_key(layers, x + dx, y + dy, w, h))
            table[feat] = override['cells'].get(f'{x},{y}', {'type': 'unknown'})
    return table


def draw_override_cell(canvas, override, x, y, tiles, strips):
    """Draw one cell from override table."""
    ox, oy = x * TILE, y * TILE
    entry = override['cells'].get(f'{x},{y}')
    if entry is None or entry['type'] == 'unknown':
        # Unknown == empty/black in editor: erase the cell (replace with transparent -> black)
        canvas.paste((0, 0, 0, 0), (ox, oy, ox + TILE, oy + TILE))
        return True
    if entry['type'] == 'base':
        cell = entry['cell'] - 1
        r, c = cell // 8, cell % 8
        t = tiles.get((r, c))
        if t is not None:
            canvas.alpha_composite(t, (ox, oy))
        return True
    if entry['type'] == 'auto':
        # entry['quads'] order is TL,TR,BL,BR (output positions)
        for out_idx, q in enumerate(entry['quads']):
            fid = q['file'] - 1
            row = q['row'] - 1
            src_qi = q['src_quad']  # source quadrant index inside the strip row
            strip = strips[fid]
            out_cx, out_cy = [(0, 0), (16, 0), (0, 16), (16, 16)][out_idx]
            src_cx, src_cy = [(0, 0), (16, 0), (0, 16), (16, 16)][src_qi]
            sub = strip.crop((src_cx, row * TILE + src_cy, src_cx + 16, row * TILE + src_cy + 16))
            canvas.alpha_composite(sub, (ox + out_cx, oy + out_cy))
        return True
    return False


def load_mapping(ts_index, data_dir=None):
    """Load a per-tileset mapping table, or None.

    Search order:
      1. mappings/<game>/tileset{N}.json   (game from WOLF_GAME or data_dir parent)
      2. mappings/tileset{N}.json          (legacy fallback)
    """
    import os
    game = os.environ.get('WOLF_GAME', '')
    if not game and data_dir is not None:
        game = Path(data_dir).parent.name
    candidates = []
    if game:
        candidates.append(MAPPING_DIR / game / f'tileset{ts_index}.json')
    candidates.append(MAPPING_DIR / f'tileset{ts_index}.json')
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding='utf-8'))
            except Exception as e:
                print(f'[warn] failed to load mapping {p}: {e}', file=sys.stderr)
    return None


def base_tile_rc(raw, mapping):
    """Return (row, col) for a base raw id using mapping if available."""
    if mapping and 'base' in mapping:
        bm = mapping['base']
        if bm.get('formula') == 'row=id//8, col=id%8':
            shift = bm.get('row_shift', 0)
            return raw // 8 - shift, raw % 8
        # Future: explicit raw->(row,col) table support
        table = bm.get('raw_to_rc')
        if table and str(raw) in table:
            return tuple(table[str(raw)])
    return raw // 8, raw % 8


def quadrant_tile(digits, strip: Image.Image) -> Image.Image:
    """Build a 32x32 RGBA tile from a 5-row RGBA strip using the quadrant rule."""
    out = Image.new('RGBA', (TILE, TILE), (0, 0, 0, 0))
    corners = {'TL': (0, 0), 'TR': (16, 0), 'BL': (0, 16), 'BR': (16, 16)}
    for (name, d) in zip(('TL', 'TR', 'BL', 'BR'), digits):
        row = d  # 0..4, including 0
        cx, cy = corners[name]
        sub = strip.crop((cx, row * TILE + cy, cx + 16, row * TILE + cy + 16))
        out.alpha_composite(sub, (cx, cy))
    return out


def autotile_quadrant_from_neighbors(layers, li, x, y, w, h, aid, strip):
    """Build a 32x32 autotile tile using the neighbor-side row rule.

    Each quadrant's row is 0..4:
      row0 = no connected side
      row1 = one vertical side connected
      row2 = one horizontal side connected
      row4 = both adjacent sides connected (interior fill)
    """
    def same(nx, ny):
        # Out-of-map neighbors count as CONNECTED (map boundary is filled).
        if nx < 0 or ny < 0 or nx >= w or ny >= h:
            return True
        v = layers[li][ny][nx]
        # 100000/104444 are empty-fill placeholders, NOT real autotile content.
        if v == 100000 or v == 104444:
            return False
        return v >= 100000 and v // 100000 == aid

    up = same(x, y - 1)
    down = same(x, y + 1)
    left = same(x - 1, y)
    right = same(x + 1, y)

    def row_for(mask):
        return {0: 0, 1: 1, 2: 2, 3: 4}[mask]

    rows = [
        row_for((1 if up else 0) | (2 if left else 0)),   # TL
        row_for((1 if up else 0) | (2 if right else 0)),  # TR
        row_for((1 if down else 0) | (2 if left else 0)), # BL
        row_for((1 if down else 0) | (2 if right else 0)),# BR
    ]
    out = Image.new('RGBA', (TILE, TILE), (0, 0, 0, 0))
    quad_pos = [(0, 0), (16, 0), (0, 16), (16, 16)]
    for (qx, qy), row in zip(quad_pos, rows):
        sub = strip.crop((qx, row * TILE + qy, qx + 16, row * TILE + qy + 16))
        out.alpha_composite(sub, (qx, qy))
    return out


_AUTOTILE_RULE_3X3 = None
_MAP_BACKGROUNDS = None


def _load_map_backgrounds():
    global _MAP_BACKGROUNDS
    if _MAP_BACKGROUNDS is None:
        p = Path(__file__).resolve().parent / 'map_backgrounds.json'
        if p.exists():
            try:
                _MAP_BACKGROUNDS = json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                _MAP_BACKGROUNDS = {}
        else:
            _MAP_BACKGROUNDS = {}
    return _MAP_BACKGROUNDS


def draw_map_background(canvas, map_path, data_dir, cw, ch):
    """Draw the configured map background image (if any) behind tiles."""
    bg = _load_map_backgrounds()
    rel = bg.get(Path(map_path).stem)
    if not rel:
        return
    data_dir = Path(data_dir)
    candidates = [
        data_dir / rel,
        data_dir.parent / 'Data' / rel,
        data_dir.parent / 'Data' / 'Picture' / Path(rel).name,
        data_dir / 'Picture' / Path(rel).name,
    ]
    p = next((c for c in candidates if c.exists()), None)
    if p is None:
        return
    try:
        img = Image.open(p).convert('RGBA')
    except Exception:
        return
    # Stretch to the full map canvas (common editor behavior).
    img = img.resize((cw * TILE, ch * TILE), Image.LANCZOS)
    canvas.alpha_composite(img, (0, 0))


def _load_autotile_rule():
    global _AUTOTILE_RULE_3X3
    if _AUTOTILE_RULE_3X3 is None:
        p = Path(__file__).resolve().parent / 'autotile_rule_norm.json'
        if not p.exists():
            p = Path(__file__).resolve().parent / 'autotile_rule_3x3.json'
        if p.exists():
            try:
                _AUTOTILE_RULE_3X3 = json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                _AUTOTILE_RULE_3X3 = {}
        else:
            _AUTOTILE_RULE_3X3 = {}
    return _AUTOTILE_RULE_3X3


def autotile_quadrant_from_rule(layers, x, y, w, h, strip, raw=None, aid=None, li=0):
    """Return a tile from the exact 3x3-neighborhood rule table, or None.

    Prefers the normalized rule table keyed by `(8-neighbor same-aid mask,
    center 4 digits)`; falls back to the raw 3x3 table if keys don't match.
    """
    rule = _load_autotile_rule()
    if not rule:
        return None
    # Determine if key contains ';' (normalized table has 5 or 6 fields).
    sample = next(iter(rule), '')
    normalized = sample.count(';') >= 4
    if raw is None:
        for lii in (2, 1, 0):
            if layers[lii][y][x] != 0:
                raw = layers[lii][y][x]
                break
    if raw is None or raw < 100000:
        return None
    if aid is None:
        aid = raw // 100000
    dirs = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
    if normalized:
        mask = 0
        for i, (dx, dy) in enumerate(dirs):
            xx, yy = x + dx, y + dy
            if 0 <= xx < w and 0 <= yy < h:
                v = layers[li][yy][xx]
                if v >= 100000 and v // 100000 == aid:
                    mask |= 1 << i
        digits = (raw % 10000 // 1000, raw % 1000 // 100, raw % 100 // 10, raw % 10)
        # New normalized table includes aid: aid;mask;d0;d1;d2;d3
        if sample.count(';') == 5:
            key = f'{aid};{mask};{digits[0]};{digits[1]};{digits[2]};{digits[3]}'
        else:
            key = f'{mask};{digits[0]};{digits[1]};{digits[2]};{digits[3]}'
    else:
        f = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    for li in range(3):
                        f.append(layers[li][yy][xx])
                else:
                    f.extend([0, 0, 0])
        key = ';'.join(map(str, f))
    rows = rule.get(key)
    if rows is None:
        return None
    # A table entry of all -1 (transparent) is usually an extraction failure;
    # fall back to the neighbor rule so the tile isn't drawn as black.
    if all(r == -1 for r in rows):
        return None
    out = Image.new('RGBA', (TILE, TILE), (0, 0, 0, 0))
    quad_pos = [(0, 0), (16, 0), (0, 16), (16, 16)]
    for (qx, qy), row in zip(quad_pos, rows):
        if 0 <= row <= 4:
            sub = strip.crop((qx, row * TILE + qy, qx + 16, row * TILE + qy + 16))
            out.alpha_composite(sub, (qx, qy))
    return out


def get_autotile_strip(tilesets, ts_index, aid, data_dir: Path, mapping=None):
    """Return the autotile strip image for a raw_aid, or None.

    Uses the per-tileset mapping table when available; otherwise falls back to
    raw_aid 1 = empty and raw_aid >= 2 -> auto_files[aid-2].
    """
    if mapping and 'autotile' in mapping:
        am = mapping['autotile']
        if aid in am.get('empty_aids', []):
            return None
        fi = am.get('aid_to_file_index', {}).get(str(aid))
        if fi is None:
            return None
        idx = int(fi)
    else:
        if aid < 2:
            return None
        idx = aid - 2
    if not (0 <= ts_index < len(tilesets)):
        return None
    files = [f for f in tilesets[ts_index].auto_files if f]
    if not (0 <= idx < len(files)):
        return None
    rel = files[idx]
    raw_b = b''
    ab = getattr(tilesets[ts_index], 'auto_files_b', [])
    if idx < len(ab):
        raw_b = ab[idx]
    p = resolve_asset_file(data_dir, rel, raw_b)
    if p is None:
        print(f'[warn] autotile strip not found: {rel}', file=sys.stderr)
        return None
    try:
        return Image.open(p).convert('RGBA')
    except Exception as e:
        print(f'[warn] cannot load {p}: {e}', file=sys.stderr)
        return None


def render(map_path, out_png, data_dir=None, transpose=None, content_transpose=False,
           win_x=0, win_y=0, win_w=None, win_h=None):
    map_path = Path(map_path)
    data_dir = Path(data_dir) if data_dir else map_path.parent.parent.parent
    b = map_path.read_bytes()
    version = b[24] if len(b) > 24 else 0

    if version == 0x67:
        info = parse_067_header(map_path)
        sw, sh = info['width'], info['height']
        ts_index = info['tileset']
    else:
        m = parse_mps(map_path, transpose=False)
        sw, sh = m.width, m.height
        ts_index = m.tileset

    # Auto transpose: square maps use display orientation (True); non-square
    # maps use storage orientation (False) to match editor full-map exports.
    if transpose is None:
        transpose = (sw == sh)

    if version == 0x67:
        w, h, layers = decode_mps_0x67(map_path, transpose=transpose)
    else:
        m = parse_mps(map_path, transpose=transpose)
        w, h, layers = m.width, m.height, m.layers

    if content_transpose:
        # Keep the canvas WxH, but swap x/y indices of the cell content.
        mw, mh = min(w, h), min(w, h)
        new_layers = []
        for li in range(3):
            nl = [[(layers[li][x][y] if x < mh and y < mw else 0)
                   for x in range(w)] for y in range(h)]
            new_layers.append(nl)
        layers = new_layers

    # Window bounds (default full map).
    wx0 = max(0, win_x)
    wy0 = max(0, win_y)
    wx1 = min(w, wx0 + win_w) if win_w is not None else w
    wy1 = min(h, wy0 + win_h) if win_h is not None else h
    cw = max(1, wx1 - wx0)
    ch = max(1, wy1 - wy0)

    tilesets = find_tileset_dat(data_dir)
    tiles = load_base_tiles(tilesets, ts_index, data_dir)
    mapping = load_mapping(ts_index, data_dir)
    strip_cache = {}

    def strip_for_aid(aid):
        if aid not in strip_cache:
            strip_cache[aid] = get_autotile_strip(tilesets, ts_index, aid, data_dir, mapping)
        return strip_cache[aid]

    # --- Wall cap/body contextual rule (in-sample, tileset5-like) ---
    CAP_SET = {4, 701402, 102244, 104444, 104422, 702243}
    # "auto cells" = topmost non-zero layer is autotile
    auto_cells = set()
    for yy in range(h):
        for xx in range(w):
            top = None
            for li in (2, 1, 0):
                if layers[li][yy][xx] != 0:
                    top = layers[li][yy][xx]
                    break
            if top is not None and top >= 100000:
                auto_cells.add((xx, yy))

    def is_cap_cell(x, y):
        # 104444 all-4 wall fill, top 3 rows of a vertical wall run, base in CAP_SET
        run = 0
        yy = y - 1
        while yy >= 0 and (x, yy) in auto_cells:
            run += 1
            yy -= 1
        return run <= 2 and layers[0][y][x] in CAP_SET

    canvas = Image.new('RGBA', (cw * TILE, ch * TILE), (0, 0, 0, 0))
    draw_map_background(canvas, map_path, data_dir, cw, ch)
    override = load_override(map_path)

    # Draw bottom layer first: 图层1 -> 图层2 -> 图层3.
    # If an override exists, autotile layers are drawn later from the 9x9 lookup.
    for li in (0, 1, 2):
        for y in range(wy0, wy1):
            for x in range(wx0, wx1):
                raw = layers[li][y][x]
                # raw 0 is a valid base tile (atlas tile 0) in WOLF; it is not empty.
                if raw < 100000:
                    # Normal base tile, alpha-composited.
                    r, c = base_tile_rc(raw, mapping)
                    t = tiles.get((r, c))
                    if t is not None:
                        canvas.alpha_composite(t, ((x - wx0) * TILE, (y - wy0) * TILE))
                else:
                    if override is not None:
                        # Lookup-driven autotile is applied later; skip old path.
                        continue
                    # aid1 (raw 100000..199999) is the empty/transparent autotile layer.
                    if 100000 <= raw < 200000:
                        continue
                    aid = raw // 100000
                    strip = strip_for_aid(aid)
                    if strip is None:
                        continue
                    tile = autotile_quadrant_from_rule(layers, x, y, w, h, strip, raw=raw, aid=aid, li=li)
                    if tile is None:
                        tile = autotile_quadrant_from_neighbors(layers, li, x, y, w, h, aid, strip)
                    canvas.alpha_composite(tile, ((x - wx0) * TILE, (y - wy0) * TILE))

    # If an override exists, use the 9x9 lookup table for autotile/base cells.
    if override is not None:
        lookup9 = _build_lookup9(override, layers, w, h)
        files = [f for f in tilesets[ts_index].auto_files if f]
        strips_override = []
        for rel in files:
            candidates = [
                data_dir / rel,
                data_dir / 'MapChip' / Path(rel).name,
                data_dir.parent / 'Data' / rel,
                data_dir.parent / 'Data' / 'MapChip' / Path(rel).name,
            ]
            p = next((c for c in candidates if c.exists()), None)
            strips_override.append(Image.open(p).convert('RGBA') if p else None)
        QUADPOS = [(0, 0), (16, 0), (0, 16), (16, 16)]
        for y in range(wy0, wy1):
            for x in range(wx0, wx1):
                feat = tuple(v for dy in range(-RADIUS, RADIUS + 1) for dx in range(-RADIUS, RADIUS + 1)
                             for v in _tri_key(layers, x + dx, y + dy, w, h))
                entry = lookup9.get(feat)
                if entry is None or entry.get('type') == 'unknown':
                    continue
                ox, oy = (x - wx0) * TILE, (y - wy0) * TILE
                if entry['type'] == 'base':
                    cell = entry['cell'] - 1
                    r, c = cell // 8, cell % 8
                    t = tiles.get((r, c))
                    if t is not None:
                        canvas.alpha_composite(t, (ox, oy))
                elif entry['type'] == 'auto':
                    for out_idx, q in enumerate(entry['quads']):
                        strip = strips_override[q['file'] - 1]
                        if strip is None:
                            continue
                        row = q['row'] - 1
                        src_qi = q['src_quad']
                        out_cx, out_cy = QUADPOS[out_idx]
                        src_cx, src_cy = QUADPOS[src_qi]
                        sub = strip.crop((src_cx, row * TILE + src_cy,
                                          src_cx + 16, row * TILE + src_cy + 16))
                        canvas.alpha_composite(sub, (ox + out_cx, oy + out_cy))

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(out_png)
    print(f'saved {out_png} ({w}x{h})', file=sys.stderr)
    return 0


def main():
    if len(sys.argv) < 3:
        print('usage: python offline_render_quadrant.py <map.mps> <out.png> [data_dir] [transpose]',
              file=sys.stderr)
        return 1
    map_path = sys.argv[1]
    out_png = sys.argv[2]
    data_dir = sys.argv[3] if len(sys.argv) > 3 else None
    transpose = None
    if len(sys.argv) >= 5:
        transpose = sys.argv[4].lower() not in ('0', 'false', 'no')
    return render(map_path, out_png, data_dir, transpose=transpose)


if __name__ == '__main__':
    sys.exit(main())
