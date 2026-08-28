# -*- coding: utf-8 -*-
"""Rebuild aid-aware normalized autotile rule table from all completed maps."""
import json, sys
from pathlib import Path
from PIL import Image
import numpy as np

sys.path.insert(0, r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png')
from wolfrpg_067 import decode_mps_0x67

T1 = Path(r'D:\文档转移\Desktop\Tileset1_数字素材')
T9 = Path(r'D:\文档转移\Desktop\Tileset9_数字素材')
T1_AUTOS = ['at_dang01.png', 'at_mori201.png', 't_fairy02.png', 't_mori201.png']
T9_AUTOS = ['[A]Wall-Up1_pipo.png', '[A]Wall-Up2_pipo.png', 'at_dang01.png', 'at_dang03.png',
            'glass2.png', 't_dang01.png', 't_mura01.png', 't_longglass.png', 'glass4.png',
            'skl.png', 't_fairy01.png']

SP = [(4, 4), (12, 4), (4, 12), (12, 12), (8, 8), (8, 4), (4, 8), (12, 8), (8, 12)]
DIRS = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]


def build_lookup(base_dir, autos):
    lookup = {}
    for fid, f in enumerate(autos, 1):
        im = Image.open(base_dir / f)
        for c in range(im.width // 32):
            for r in range(im.height // 32):
                for qi in range(4):
                    color = (fid * 16 + 8, c * 32 + 16, r * 32 + qi * 8 + 10)
                    lookup[color] = ('auto', fid, c, r, qi)
    return lookup


def rows_at(ae, x, y, lookup):
    out = []
    for (qx, qy) in [(0, 0), (16, 0), (0, 16), (16, 16)]:
        r = -1
        for (px, py) in SP:
            lab = lookup.get(tuple(ae[y * 32 + qy + py, x * 32 + qx + px]))
            if lab and lab[0] == 'auto':
                r = lab[3]
                break
        out.append(r)
    return out


def collect(map_path, export_path, lookup, transpose, table):
    w, h, layers = decode_mps_0x67(map_path, transpose=transpose)
    ae = np.array(Image.open(export_path).convert('RGB'))
    for li in range(3):
        for y in range(h):
            for x in range(w):
                raw = layers[li][y][x]
                if not (raw >= 200000):
                    continue
                aid = raw // 100000
                mask = 0
                for i, (dx, dy) in enumerate(DIRS):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < w and 0 <= yy < h:
                        v = layers[li][yy][xx]
                        if v >= 100000 and v // 100000 == aid:
                            mask |= 1 << i
                digits = (raw % 10000 // 1000, raw % 1000 // 100, raw % 100 // 10, raw % 10)
                rows = rows_at(ae, x, y, lookup)
                key = f'{aid};{mask};{digits[0]};{digits[1]};{digits[2]};{digits[3]}'
                if key in table:
                    old = table[key]
                    if rows.count(-1) < old.count(-1):
                        table[key] = rows
                else:
                    table[key] = rows


def main():
    table = {}
    base = r'D:\文档转移\Desktop\WOLF地图导出工具_1.4\WOLF_RPG_Editor3\Data\MapData'
    t1_lookup = build_lookup(T1, T1_AUTOS)
    t9_lookup = build_lookup(T9, T9_AUTOS)
    EXP = r'D:\文档转移\Desktop\唯一色待补全'
    # Map142 (tileset1, square -> transpose=True)
    collect(f'{base}/Map142.mps', f'{EXP}/Map142_id2_唯一色.png', t1_lookup, True, table)
    # Map143 (tileset1, non-square -> transpose=False)
    collect(f'{base}/Map143.mps', f'{EXP}/Map143_clean2_唯一色.png', t1_lookup, False, table)
    # Map004 (tileset1, non-square -> transpose=False)
    collect(f'{base}/Map004.mps', f'{EXP}/Map004_唯一色.png', t1_lookup, False, table)
    # Map002 (tileset1, non-square -> transpose=False)
    collect(f'{base}/Map002.mps', f'{EXP}/Map002_墙角_唯一色.png', t1_lookup, False, table)
    # Map101 (tileset9, non-square -> transpose=False)
    collect(f'{base}/Map101.mps', f'{EXP}/Map101_唯一色.png', t9_lookup, False, table)
    # Map102 (tileset9, non-square -> transpose=False)
    collect(f'{base}/Map102.mps', f'{EXP}/Map102_唯一色.png', t9_lookup, False, table)
    out = Path(r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png\autotile_rule_norm.json')
    out.write_text(json.dumps(table, indent=0), encoding='utf-8')
    neg = sum(1 for v in table.values() if all(r == -1 for r in v))
    print('aid-aware table size', len(table), 'all -1', neg)


if __name__ == '__main__':
    main()