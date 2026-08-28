# -*- coding: utf-8 -*-
"""Export both map layer (opaque) and event layer (transparent) for all maps."""
import sys
from pathlib import Path

sys.path.insert(0, r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png')
from offline_render_quadrant import render
import render_event_layer as rel

DATA = Path(r'D:\文档转移\Desktop\WOLF地图导出工具_1.4\WOLF_RPG_Editor3\Data\MapData')
OUT_MAP = Path(r'D:\文档转移\Desktop\导出_地图层')
OUT_EVT = Path(r'D:\文档转移\Desktop\导出_事件层')
OUT_MAP.mkdir(parents=True, exist_ok=True)
OUT_EVT.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path(r'D:\文档转移\Desktop\WOLF地图导出工具_1.4\WOLF_RPG_Editor3\Backup_Before_Ver3')
# Event layer needs the REAL Data folder to resolve CharaChip / MapChip / BasicData assets.
DATA_REAL = Path(r'D:\文档转移\Desktop\WOLF地图导出工具_1.4\WOLF_RPG_Editor3\Data')

names = sorted([p for p in DATA.glob('Map*.mps')])
print('maps', len(names), file=sys.stderr)
for p in names:
    stem = p.stem
    try:
        render(str(p), str(OUT_MAP / f'{stem}.png'), str(DATA_DIR))
    except Exception as e:
        print(f'[map] {stem} ERR {e}', file=sys.stderr)
    try:
        rel.render_event_layer(str(p), str(DATA_REAL), str(OUT_EVT / f'{stem}.png'))
    except Exception as e:
        print(f'[evt] {stem} ERR {e}', file=sys.stderr)
print('done', file=sys.stderr)