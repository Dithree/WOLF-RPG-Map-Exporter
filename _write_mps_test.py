# -*- coding: utf-8 -*-
"""Write a modified 0x67 .mps (remove layer0 separator cells), with round-trip test."""
import struct, sys
from pathlib import Path
import lz4.block

sys.path.insert(0, r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png')
from wolfrpg_067 import _logical_bytes, parse_067_header, decode_mps_0x67

SRC = r'D:\文档转移\Desktop\MapData备份_自动图块实验\Map143_before_cleanup.mps'
TMP = r'D:\应用\DeepSeek Harness\工作区1\wolfrpg-map-png\_Map143_clean_test.mps'


def write_067(path, logical: bytes, orig_header: bytes):
    dec_size = len(logical)
    enc = lz4.block.compress(logical, store_size=False)
    with open(path, 'wb') as f:
        f.write(orig_header[:25])
        f.write(struct.pack('<II', dec_size, len(enc)))
        f.write(enc)


def modify_payload(payload: bytearray):
    info = parse_067_header(SRC)
    W, H = info['width'], info['height']
    # mapdata_offset is logical offset; payload starts at logical 25
    off = info['mapdata_offset'] - 25
    n_cells = W * H * 3
    for i in range(W * H):
        pos = off + i * 4
        val = struct.unpack_from('<I', payload, pos)[0]
        if val == 1:
            struct.pack_into('<I', payload, pos, 0)
    return bytes(payload)


def main():
    b = Path(SRC).read_bytes()
    logical = _logical_bytes(SRC)
    payload = bytearray(logical[25:])
    new_payload = modify_payload(payload)
    write_067(TMP, new_payload, b)
    print('written temp', TMP)
    # Verify round-trip
    info = parse_067_header(SRC)
    w, h, layers = decode_mps_0x67(SRC, transpose=False)
    w2, h2, layers2 = decode_mps_0x67(TMP, transpose=False)
    print('dims orig', w, h, 'new', w2, h2)
    removed = 0
    changed = 0
    for y in range(h):
        for x in range(w):
            for li in range(3):
                a = layers[li][y][x]
                b2 = layers2[li][y][x]
                if a != b2:
                    changed += 1
                    if li == 0 and a == 1 and b2 == 0:
                        removed += 1
    print('changed cells', changed, 'separator removed', removed)


if __name__ == '__main__':
    main()