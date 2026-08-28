#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline full-map base-tile renderer for WOLF RPG Editor .mps files.

This renders the ordinary (non-autotile) map chips directly from the game's
MapChip atlas.  Autotile cells are currently skipped (they need the autotile
compositor), so the output shows the base layers underneath them.

Usage:
    python offline_render_base.py <map.mps> <out.png> [data_dir]

`data_dir` must contain BasicData/TileSetData.dat and MapChip/*.png.
If the current Data uses TileSetData v211 (unsupported), point `data_dir` at
the `Backup_Before_Ver3` folder that contains the pre-conversion v209 data.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wolfrpg import parse_mps, decode_cell, parse_tileset_dat
from wolfrpg_067 import decode_mps_0x67

TILE = 32

# ID -> atlas mapping.  The Map140 reference suggested row = id//8 - 4 for
# some tilesets, but Map006 matches direct row = id//8 better.  Keep this
# configurable; for the first integrated demo we use direct mapping.
ID_ROW_SHIFT = 0
CALIB_ATLAS = Path(__file__).resolve().parent / '_calib_correct' / 'bmp_0.png'


def tile_rc(cid: int):
    """Return (row, col) in the base atlas for a tile ID."""
    return cid // 8 - ID_ROW_SHIFT, cid % 8


def find_tileset_dat(data_dir: Path):
    """Return the first readable TileSetData.dat under data_dir."""
    candidates = [
        data_dir / 'BasicData' / 'TileSetData.dat',
        data_dir / 'TileSetData.dat',
    ]
    for p in candidates:
        if p.exists():
            try:
                return parse_tileset_dat(p)
            except Exception:
                continue
    return []


def resolve_asset_file(data_dir: Path, rel, raw_b: bytes = b''):
    """Find an asset file, tolerating non-UTF-8 (Shift-JIS/GBK/...) filenames.

    Tries the decoded `rel` first, then re-decodes the raw bytes with several
    encodings and checks the filesystem so maps can run on non-English paths
    and read Japanese/Chinese filenames.
    """
    rel_p = Path(rel)
    candidates = [
        data_dir / rel,
        data_dir / 'MapChip' / rel_p.name,
        data_dir.parent / 'Data' / rel,
        data_dir.parent / 'Data' / 'MapChip' / rel_p.name,
    ]
    for c in candidates:
        if c.exists():
            return c
    if raw_b:
        body = raw_b.rstrip(b'\x00')
        for enc in ('cp932', 'shift_jis', 'utf-8', 'gbk', 'big5'):
            try:
                name = body.decode(enc)
            except Exception:
                continue
            for c in (data_dir / name,
                      data_dir / 'MapChip' / Path(name).name,
                      data_dir.parent / 'Data' / name,
                      data_dir.parent / 'Data' / 'MapChip' / Path(name).name):
                if c.exists():
                    return c
    return None


def load_base_tiles(tilesets, ts_index, data_dir: Path):
    """Return {chip_id: RGBA tile image} for the tileset's base atlas."""
    if not (0 <= ts_index < len(tilesets)):
        ts_index = 0
    ts = tilesets[ts_index]
    base_file = ts.base_file
    base_path = resolve_asset_file(data_dir, base_file, getattr(ts, 'base_file_b', b''))
    if base_path is None:
        print(f'[warn] base image not found: {base_file}', file=sys.stderr)
        return {}

    img = Image.open(base_path).convert('RGBA')
    cols = img.width // TILE
    rows = img.height // TILE
    tiles = {}
    for r in range(rows):
        for c in range(cols):
            # Store by (row, col) key; rendering uses tile_rc() to look up.
            tiles[(r, c)] = img.crop((c * TILE, r * TILE,
                                      (c + 1) * TILE, (r + 1) * TILE))
    return tiles


def render_base(map_path, data_dir, out_png):
    map_path = Path(map_path)
    data_dir = Path(data_dir)

    # Detect 0x67 (new) vs 0x65/0x66 (old).
    b = map_path.read_bytes()
    version = b[24] if len(b) > 24 else 0
    # The editor display orientation is the transposed storage order.
    TRANSPOSE = True
    if version == 0x67:
        width, height, layers = decode_mps_0x67(map_path, transpose=TRANSPOSE)
        tileset = 0
        # Need the tileset from the logical header for atlas selection.
        try:
            from wolfrpg_067 import parse_067_header
            tileset = parse_067_header(map_path)['tileset']
        except Exception:
            tileset = 0
    else:
        m = parse_mps(map_path, transpose=TRANSPOSE)
        width, height, layers = m.width, m.height, m.layers
        tileset = m.tileset

    tilesets = find_tileset_dat(data_dir)
    if not tilesets:
        print('[error] no readable TileSetData.dat', file=sys.stderr)
        return 2
    tiles = load_base_tiles(tilesets, tileset, data_dir)
    if not tiles:
        print('[error] no base tiles loaded', file=sys.stderr)
        return 3

    print(f'map {map_path.name}: {width}x{height}, '
          f'tileset {tileset}, base tiles {len(tiles)}', file=sys.stderr)

    # Black background; autotile cells are left as whatever base layers show.
    canvas = Image.new('RGBA', (width * TILE, height * TILE), (0, 0, 0, 255))
    stats = {'base': 0, 'auto': 0, 'empty': 0, 'missing': 0}

    # Precompute wall cells (autotile id == 1) in layer 2 only.
    wall_cells = set()
    for y in range(height):
        for x in range(width):
            raw = layers[2][y][x]
            if raw >= 100000 and raw // 100000 == 1:
                wall_cells.add((x, y))

    # Precompute layer1 object cells (autotile id == 1, excluding pure fill 100000).
    wall_cells_l1 = set()
    for y in range(height):
        for x in range(width):
            raw = layers[1][y][x]
            if raw >= 100000 and raw // 100000 == 1 and raw != 100000:
                wall_cells_l1.add((x, y))

    # Load autotile neighbor lookup table (4-neighbor version, known to work best so far)
    _LOOKUP_DIR = Path(__file__).resolve().parent / '_autotile_lookup'
    _autotile_lookup = {}
    _autotile_lookup_normal = None
    if _LOOKUP_DIR.is_dir():
        for p in _LOOKUP_DIR.glob('*.png'):
            try:
                if p.stem == '1_1_1_1_normal':
                    _autotile_lookup_normal = Image.open(p).convert('RGBA')
                    continue
                key = tuple(int(v) for v in p.stem.split('_'))
                if len(key) == 4:
                    _autotile_lookup[key] = Image.open(p).convert('RGBA')
            except Exception:
                pass

    # Layer1 wall-part mapping discovered from Map024's correct layer1 example.
    # When layer0 has autotile id 7 (window/object overlay), the layer1 cells
    # are wall-cap parts that composite from t_castle03 via the lookup tiles.
    WALL_MAP = {
        104120: _autotile_lookup.get((0, 1, 0, 1)),
        104141: _autotile_lookup.get((0, 1, 0, 1)),
        150: _autotile_lookup.get((0, 1, 0, 1)),
        158: _autotile_lookup.get((0, 0, 0, 1)),
        148: _autotile_lookup.get((0, 0, 0, 1)),
        101414: _autotile_lookup.get((1, 1, 1, 0)),
        101402: _autotile_lookup.get((1, 1, 1, 0)),
        566: _autotile_lookup.get((1, 0, 0, 1)),
        147: _autotile_lookup.get((1, 0, 0, 1)),
        586: _autotile_lookup.get((0, 1, 1, 1)),
        585: _autotile_lookup.get((0, 1, 1, 1)),
        407: _autotile_lookup.get((0, 1, 1, 1)),
        594: _autotile_lookup.get((0, 1, 1, 1)),
        593: _autotile_lookup.get((0, 1, 1, 1)),
        415: _autotile_lookup.get((0, 1, 1, 1)),
        602: _autotile_lookup.get((1, 1, 1, 1)),
        601: _autotile_lookup.get((1, 1, 1, 1)),
        100011: _autotile_lookup.get((1, 1, 1, 1)),
    }

    # File layer 0 is the top layer; draw bottom first.
    for li in (2, 1, 0):
        for y in range(height):
            for x in range(width):
                raw = layers[li][y][x]
                if raw == 0:
                    stats['empty'] += 1
                    continue
                if li == 1:
                    l0_raw = layers[0][y][x] if len(layers) > 0 else 0
                    l0_is_auto7 = l0_raw >= 100000 and l0_raw // 100000 == 7
                    if l0_is_auto7:
                        tile = WALL_MAP.get(raw)
                        if tile is not None:
                            canvas.paste(tile, (x * TILE, y * TILE), tile)
                            continue
                if raw < 100000:
                    # base tile
                    r, c = tile_rc(raw)
                    tile = tiles.get((r, c))
                    if tile is None:
                        stats['missing'] += 1
                        continue
                    canvas.paste(tile, (x * TILE, y * TILE), tile)
                    stats['base'] += 1
                else:
                    # autotile
                    stats['auto'] += 1
                    aid = raw // 100000
                    if aid == 1 and _autotile_lookup:
                        if li == 2:
                            cells = wall_cells
                            key = (1 if (x, y - 1) in cells else 0,
                                   1 if (x, y + 1) in cells else 0,
                                   1 if (x - 1, y) in cells else 0,
                                   1 if (x + 1, y) in cells else 0)
                            tile = _autotile_lookup.get(key)
                            # Special case: all-connected wall has two variants.
                            if key == (1, 1, 1, 1) and _autotile_lookup_normal is not None:
                                above_raw = layers[2][y - 1][x] if y > 0 else 0
                                l1_raw = layers[1][y][x] if len(layers) > 1 else 0
                                if not (above_raw == 100000 and l1_raw >= 100000):
                                    tile = _autotile_lookup_normal
                        elif li == 1 and raw != 100000:
                            # Rolled back: do not draw layer1 autotile in the
                            # composite; keep layer1 wall cells empty for now.
                            tile = None
                        else:
                            tile = None
                        if tile is not None:
                            canvas.paste(tile, (x * TILE, y * TILE), tile)
                    # else: skip other autotile types for now

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert('RGB').save(out_png)
    print('stats', stats, file=sys.stderr)
    print(f'saved {out_png}', file=sys.stderr)
    return 0


def main():
    if len(sys.argv) < 3:
        print('usage: python offline_render_base.py <map.mps> <out.png> [data_dir]')
        return 1
    map_path = sys.argv[1]
    out_png = sys.argv[2]
    data_dir = sys.argv[3] if len(sys.argv) > 3 else str(Path(map_path).parent.parent.parent)
    return render_base(map_path, data_dir, out_png)


if __name__ == '__main__':
    sys.exit(main())
