#!/usr/bin/env python3
"""Parse .mps events fully using mps.ksy + event_command.ksy (manual port)."""
import struct, sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
import parse_common_events as ce

BASE = Path(r'D:\应用\DeepSeek Harness\WOLF_RPG_Editor3\Data')


def parse_route(b, off):
    return ce.parse_route(b, off)


def parse_page(b, off):
    start = off
    header = b[off]; off += 1
    assert header == 0x79, f'page header {header:#x} at {off-1}'
    chip_id = struct.unpack_from('<I', b, off)[0]; off += 4
    fname, off = ce.read_tstr(b, off)
    row, col, opacity, disp = b[off:off+4]
    off += 4
    trigger_condition = b[off]; off += 1
    switches = []
    for _ in range(4):
        sw = b[off]; off += 1
        switches.append((sw >> 4, sw & 0xf))
    variables = list(struct.unpack_from('<4I', b, off)); off += 16
    values = list(struct.unpack_from('<4i', b, off)); off += 16
    off = parse_route(b, off)
    (cmd_count,) = struct.unpack_from('<I', b, off); off += 4
    cmd_start = off
    commands = []
    for _ in range(cmd_count):
        cmd, off = ce.parse_event_command(b, off)
        if cmd is None:
            break
        commands.append(cmd)
    cmd_end = off
    unknown3 = struct.unpack_from('<I', b, off)[0]; off += 4
    shadow = b[off]; off += 1
    range_x = b[off]; off += 1
    range_y = b[off]; off += 1
    footer = b[off]; off += 1
    assert footer == 0x7a, f'page footer {footer:#x} at {off-1}'
    return {'chip_id': chip_id, 'filename': fname, 'row': row, 'col': col,
            'opacity': opacity, 'display_type': disp,
            'trigger_condition': trigger_condition, 'switches': switches,
            'variables': variables, 'values': values,
            'cmd_count': cmd_count, 'commands': commands,
            'unknown3': unknown3, 'shadow': shadow, 'range': (range_x, range_y),
            'cmd_start': cmd_start, 'cmd_end': cmd_end,
            'cmd_start_rel': cmd_start - (off - (off-start)),
            'cmd_end_rel': cmd_end - (off - (off-start)),
            'raw_bytes': b[start:off], 'raw_len': off-start}, off


def parse_map(path):
    raw = Path(path).read_bytes()
    assert raw[10:16] == b'WOLFM\x00'
    if raw[24] == 0x67:
        # 0x67 files are LZ4-compressed; decompress to the logical file first.
        from wolfrpg_067 import _logical_bytes
        b = _logical_bytes(path)
    else:
        b = raw
    # header as in wolfrpg.py
    ver_header = b[16]
    version = b[24]
    title, off = ce.read_tstr(b, 25)
    tileset, width, height, event_count = struct.unpack_from('<IIII', b, off)
    off += 16
    (first_pixel,) = struct.unpack_from('<I', b, off)
    if first_pixel != 0xFFFFFFFF:
        off += width * height * 12
    # events start after mapdata block; need skip exactly as wolfrpg does
    # easier: use wolfrpg.parse_mps to get layers? But we need event offset.
    # Recompute: after header off points to first_pixel; mapdata block length:
    if first_pixel != 0xFFFFFFFF:
        # block = width*height*12 bytes (includes first_pixel)
        pass
    else:
        off += 4
    events = []
    for i in range(event_count):
        ev_start = off
        header = b[off]; off += 1
        assert header == 0x6f, f'event header {header:#x} at {off-1}'
        header2, event_id = struct.unpack_from('<II', b, off); off += 8
        title, off = ce.read_tstr(b, off)
        map_x, map_y, page_count, sep = struct.unpack_from('<IIII', b, off); off += 16
        pages = []
        for _ in range(page_count):
            page, off = parse_page(b, off)
            pages.append(page)
        footer = b[off]; off += 1
        assert footer == 0x70, f'event footer {footer:#x} at {off-1}'
        events.append({'id': event_id, 'title': title, 'x': map_x, 'y': map_y,
                       'page_count': page_count, 'pages': pages, 'raw_len': off-ev_start})
    return {'path': path, 'title': title, 'tileset': tileset, 'width': width,
            'height': height, 'event_count': event_count, 'events': events,
            'event_start': 0, 'footer_off': off}


def main():
    for name in ['SampleMapA.mps', 'SampleMapB.mps', 'Dungeon.mps', 'TitleMap.mps']:
        path = BASE / 'MapData' / name
        m = parse_map(path)
        print(f'=== {name}: {m["title"]} {m["width"]}x{m["height"]} events={m["event_count"]} footer_off={m["footer_off"]} file_len={path.stat().st_size}')
        for ev in m['events']:
            print(f'  ev id={ev["id"]} title={ev["title"]!r} pos=({ev["x"]},{ev["y"]}) pages={ev["page_count"]} raw_len={ev["raw_len"]}')
            for pi, page in enumerate(ev['pages']):
                types = [c['command_type'] for c in page['commands']]
                print(f'    page{pi} trig={page["trigger_condition"]} sw={page["switches"]} vars={page["variables"]} vals={page["values"]} cmds={page["cmd_count"]} types={types[:30]}')


if __name__ == '__main__':
    main()
