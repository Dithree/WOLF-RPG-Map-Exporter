# -*- coding: utf-8 -*-
"""Batch render all maps with the corner-rule version into a fresh folder."""
import sys
from pathlib import Path

sys.path.insert(0, r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png')
from offline_render_quadrant import render

DATA = Path(r'D:\文档转移\Desktop\WOLF地图导出工具_1.4\WOLF_RPG_Editor3\Data\MapData')
OUT_DIR = Path(r'D:\文档转移\Desktop\地图离线渲染_墙角规则版')
OUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path(r'D:\文档转移\Desktop\WOLF地图导出工具_1.4\WOLF_RPG_Editor3\Backup_Before_Ver3')

names = sorted([p for p in DATA.glob('Map*.mps')])
print('maps to render', len(names), file=sys.stderr)
for i, p in enumerate(names):
    out = OUT_DIR / f'{p.stem}.png'
    try:
        render(str(p), str(out), str(DATA_DIR))
    except Exception as e:
        print(f'[{i+1}/{len(names)}] {p.stem} ERROR {e}', file=sys.stderr)
print('done', file=sys.stderr)