# -*- coding: utf-8 -*-
"""Regenerate unique-color materials for tilesets 1/3/9 with a non-overflow scheme."""
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

ORIG = Path(r'D:\文档转移\Desktop\WOLF地图导出工具_1.4\WOLF_RPG_Editor3\Data\MapChip')
TILE = 32

T1 = {
    'out': Path(r'D:\文档转移\Desktop\Tileset1_数字素材'),
    'base': '[M]00.png',
    'autos': ['at_dang01.png', 'at_mori201.png', 't_fairy02.png', 't_mori201.png'],
    'bak': Path(r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png\_ORIGINAL_MATERIALS_BACKUP_T1'),
}
T3 = {
    'out': Path(r'D:\文档转移\Desktop\Tileset3_数字素材'),
    'base': '[M]02.png',
    'autos': ['[A]Wall-Up1_pipo.png', '[A]Wall-Up2_pipo.png', 't_fairy02.png',
              '[A]Water1_Cave4_pipo.png', 't_town03.png', '[A]Grass1-Dirt2_pipo.png',
              't_longglass.png'],
    'bak': Path(r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png\_ORIGINAL_MATERIALS_BACKUP_T3'),
}
T9 = {
    'out': Path(r'D:\文档转移\Desktop\Tileset9_数字素材'),
    'base': '[M]08.png',
    'autos': ['[A]Wall-Up1_pipo.png', '[A]Wall-Up2_pipo.png', 'at_dang01.png', 'at_dang03.png',
              'glass2.png', 't_dang01.png', 't_mura01.png', 't_longglass.png', 'glass4.png',
              'skl.png', 't_fairy01.png'],
    'bak': Path(r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png\_ORIGINAL_MATERIALS_BACKUP_T9'),
}


def base_color_for_id(n):
    r = (n % 8) * 28 + 14       # 0..210
    g = ((n // 8) % 16) * 14 + 7  # 0..217
    b = ((n // 128) % 8) * 28 + 14  # 0..210
    return (r, g, b)


def auto_color(file_id, col, row, quad):
    r = file_id * 16 + 8          # fid 1..11 -> 24..184
    g = col * 32 + 16             # col 0..4 -> 16..144
    b = row * 32 + quad * 8 + 10  # row 0..4 -> 10..138? (4*32+3*8+10=162)
    # clamp safety
    return (min(r, 255), min(g, 255), min(b, 255))


def make_base(path, cols, rows):
    img = Image.new('RGBA', (cols * TILE, rows * TILE), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    n = 1
    for r in range(rows):
        for c in range(cols):
            d.rectangle([c * TILE, r * TILE, c * TILE + TILE - 1, r * TILE + TILE - 1],
                        fill=base_color_for_id(n))
            n += 1
    img.save(path)
    print('saved', path, img.size)


def make_auto(path, file_id, cols, rows):
    img = Image.new('RGBA', (cols * TILE, rows * TILE), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for c in range(cols):
        for r in range(rows):
            ox, oy = c * TILE, r * TILE
            for qi, (qx, qy) in enumerate([(0, 0), (16, 0), (0, 16), (16, 16)]):
                color = auto_color(file_id, c, r, qi)
                d.rectangle([ox + qx, oy + qy, ox + qx + 15, oy + qy + 15], fill=color)
    img.save(path)
    print('saved', path, img.size)


def main():
    for spec in (T1, T3, T9):
        spec['out'].mkdir(parents=True, exist_ok=True)
        spec['bak'].mkdir(parents=True, exist_ok=True)
        # Base
        im = Image.open(ORIG / spec['base'])
        make_base(spec['out'] / spec['base'], im.width // TILE, im.height // TILE)
        # Autos
        for fid, f in enumerate(spec['autos'], 1):
            p = ORIG / f
            if not p.exists():
                print('missing', f)
                continue
            im = Image.open(p)
            make_auto(spec['out'] / f, fid, im.width // TILE, im.height // TILE)
            # backup original
            if not (spec['bak'] / f).exists():
                shutil.copy2(p, spec['bak'] / f)
        # Backup base
        if not (spec['bak'] / spec['base']).exists():
            shutil.copy2(ORIG / spec['base'], spec['bak'] / spec['base'])
        # Replace in MapChip
        for f in [spec['base']] + spec['autos']:
            src = spec['out'] / f
            if src.exists():
                shutil.copy2(src, ORIG / f)
                print('replaced', f)


if __name__ == '__main__':
    main()