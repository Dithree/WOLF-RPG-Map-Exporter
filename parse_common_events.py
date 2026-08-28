#!/usr/bin/env python3
"""Parse CommonEvent.dat using the wolf-rpg-formats kaitai spec (manual port).

Prints a compact list of common events and their command type ids so we can
identify the encodings for Set Variable / Set String / Wait / Transfer etc.
"""
import struct, sys
from pathlib import Path

BASE = Path(r'D:\应用\DeepSeek Harness\WOLF_RPG_Editor3\Data\BasicData\CommonEvent.dat')


def read_tstr(b, off):
    (n,) = struct.unpack_from('<I', b, off)
    raw = b[off+4:off+4+n]
    s = raw.rstrip(b'\x00').decode('utf-8', 'replace')
    return s, off+4+n


def read_tstr_array(b, off):
    (n,) = struct.unpack_from('<I', b, off)
    off += 4
    arr = []
    for _ in range(n):
        s, off = read_tstr(b, off)
        arr.append(s)
    return arr, off


def read_u4_array(b, off):
    (n,) = struct.unpack_from('<I', b, off)
    off += 4
    return list(struct.unpack_from(f'<{n}I', b, off)), off + 4*n


def read_s4_array(b, off):
    (n,) = struct.unpack_from('<i', b, off)
    off += 4
    return list(struct.unpack_from(f'<{n}i', b, off)), off + 4*n


def parse_route(b, off):
    # route_info: animation_frequency u1, move_speed u1, move_frequency u1,
    # move_route_mode u1, behavior_options u1, route_options u1, route_length u4
    if off + 7 > len(b):
        return off
    off += 6  # 4 enums + behavior_options + route_options
    (route_length,) = struct.unpack_from('<I', b, off)
    off += 4
    for _ in range(route_length):
        off = parse_route_data(b, off)
    return off


def parse_route_data(b, off):
    if off >= len(b):
        return off
    rtype = b[off]
    off += 1
    # All route types in the spec have: u4_arg_len u1, args, u1_arg_len u1, args
    if off >= len(b):
        return off
    u4_len = b[off]
    off += 1 + u4_len*4
    if off >= len(b):
        return off
    u1_len = b[off]
    off += 1 + u1_len
    return off


def parse_event_command(b, off, depth=0):
    """Return (command_dict_or_None, new_off)."""
    if off >= len(b):
        return None, off
    start = off
    param_count = b[off]
    off += 1
    if param_count == 0:
        return {'param_count': 0, 'command_type': None, 'strings': [], 'route': False, 'param_bytes': b'', 'raw_len': off-start}, off
    if off + 4 > len(b):
        return None, off
    command_type = struct.unpack_from('<I', b, off)[0]
    off += 4
    param_size = param_count*4 - 4
    if off + param_size > len(b):
        return None, len(b)
    param_bytes = b[off:off+param_size]
    off += param_size
    if off >= len(b):
        return {'param_count': param_count, 'command_type': command_type, 'strings': [], 'route': False, 'raw_len': off-start}, off
    branch_depth = b[off]
    off += 1
    string_count = b[off]
    off += 1
    strings = []
    for _ in range(string_count):
        s, off = read_tstr(b, off)
        strings.append(s)
    have_route = 0
    route = False
    if off < len(b):
        have_route = b[off]
        off += 1
        if have_route != 0:
            route = True
            off = parse_route(b, off)
    return {'param_count': param_count, 'command_type': command_type,
            'branch_depth': branch_depth, 'string_count': string_count,
            'strings': strings, 'route': route, 'param_bytes': param_bytes,
            'raw_bytes': b[start:off], 'raw_len': off-start}, off


def parse_common_event(b, off):
    start = off
    header = b[off]
    off += 1
    common_event_id = struct.unpack_from('<I', b, off)[0]
    off += 4
    condition_operator_run = b[off]
    off += 1
    condition_operator = condition_operator_run >> 4
    run_condition = condition_operator_run & 0x0f
    condition_variable = struct.unpack_from('<I', b, off)[0]
    off += 4
    condition_value = struct.unpack_from('<I', b, off)[0]
    off += 4
    arg_num_count = b[off]
    off += 1
    arg_str_count = b[off]
    off += 1
    title, off = read_tstr(b, off)
    (lines_count,) = struct.unpack_from('<I', b, off)
    off += 4
    commands = []
    for _ in range(lines_count):
        cmd, off = parse_event_command(b, off)
        if cmd is None:
            break
        commands.append(cmd)
    # unknown4 5 bytes
    off += 5
    memo, off = read_tstr(b, off)
    sep1 = b[off]
    off += 1
    arg_names, off = read_tstr_array(b, off)
    spec_page_count = struct.unpack_from('<I', b, off)[0]
    off += 4
    off += spec_page_count  # u1 special spec each
    manual_str_pagecount = struct.unpack_from('<I', b, off)[0]
    off += 4
    for _ in range(manual_str_pagecount):
        arr, off = read_tstr_array(b, off)
    manual_val_pagecount = struct.unpack_from('<I', b, off)[0]
    off += 4
    for _ in range(manual_val_pagecount):
        arr, off = read_u4_array(b, off)
    arg_defaults, off = read_s4_array(b, off)
    sep2 = b[off]
    off += 1
    color = struct.unpack_from('<I', b, off)[0]
    off += 4
    for _ in range(100):
        s, off = read_tstr(b, off)
    sep3 = b[off]
    off += 1
    unknown5 = b[off:off+5]
    off += 5
    sep4 = b[off]
    off += 1
    return_name, off = read_tstr(b, off)
    return_value_id = struct.unpack_from('<I', b, off)[0]
    off += 4
    sep5 = b[off]
    off += 1
    return {'id': common_event_id, 'title': title, 'lines_count': lines_count,
            'commands': commands, 'memo': memo, 'arg_num_count': arg_num_count,
            'arg_str_count': arg_str_count, 'return_name': return_name,
            'return_value_id': return_value_id, 'raw_len': off-start}, off


def main():
    b = BASE.read_bytes()
    assert b[0:6] == b'\x00W\x00\x00OL'
    ver_header = b[6]
    assert b[7:10] == b'FC\x00'
    version = b[10]
    (count,) = struct.unpack_from('<I', b, 11)
    off = 15
    print(f'version_header={ver_header:#x} version={version} count={count} file_len={len(b)}')
    events = []
    for i in range(count):
        ev, off = parse_common_event(b, off)
        events.append(ev)
        types = [c['command_type'] for c in ev['commands'] if c['command_type'] is not None]
        print(f"[{ev['id']}] {ev['title']!r} lines={ev['lines_count']} cmds={len(ev['commands'])} types={types}")
        if i < 5:
            for c in ev['commands'][:10]:
                print('    ', c)
    print('footer', hex(b[off]) if off < len(b) else 'EOF', 'off', off, 'len', len(b))


if __name__ == '__main__':
    main()
