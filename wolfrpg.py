"""Minimal Wolf RPG Editor (WOLF RPG Editor v3) data readers.

Implements enough of the community-documented format (djytw/wolf-rpg-formats,
MIT) to read:
  * TileSetData.dat  -> list of tilesets (base chip file + autotile files)
  * *.mps map files  -> header (tileset id, size) + 3 layers of tile cells

Cell encoding (mappixel, from the kaitai spec):
  raw == 0                 -> empty
  raw < 100000             -> base tile index
  raw >= 100000            -> autotile:
        autotile_id  = raw // 100000            (1-based id into autotile files)
        mode_tl      = raw % 10000 // 1000      (top-left quadrant)
        mode_tr      = raw % 1000  // 100       (top-right)
        mode_bl      = raw % 100   // 10        (bottom-left)
        mode_br      = raw % 10                (bottom-right)
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path


def read_tstr(buf: bytes, off: int, enc: str = 'utf-8'):
    """t_str: u4 len + strz bytes (len includes trailing NUL)."""
    (n,) = struct.unpack_from('<I', buf, off)
    raw = buf[off + 4: off + 4 + n]
    # strip trailing NUL(s)
    s = raw.rstrip(b'\x00').decode(enc, errors='replace')
    return s, off + 4 + n


def read_tstr_raw(buf: bytes, off: int, enc: str = 'utf-8'):
    """t_str returning (decoded_str, raw_bytes, new_off).

    raw_bytes retains the original bytes so non-UTF-8 filenames can be
    resolved against the filesystem with another encoding.
    """
    (n,) = struct.unpack_from('<I', buf, off)
    raw = buf[off + 4: off + 4 + n]
    body = raw.rstrip(b'\x00')
    s = body.decode(enc, errors='replace')
    return s, body, off + 4 + n


@dataclass
class Tileset:
    index: int
    title: str
    base_file: str
    auto_files: list = field(default_factory=list)
    base_file_b: bytes = b''
    auto_files_b: list = field(default_factory=list)

    def auto_file(self, i: int) -> str:
        """Autotile file for 1-based autotile id `i`."""
        if 1 <= i <= len(self.auto_files):
            return self.auto_files[i - 1]
        return ''


def parse_tileset_dat(path) -> list:
    """Parse TileSetData.dat, return list[Tileset]."""
    b = Path(path).read_bytes()
    assert b[0:6] == b'\x00W\x00\x00OL', f'bad magic {b[0:6]!r}'
    ver_header = b[6]
    assert b[7:10] == b'FM\x00', 'bad magic2'
    version = b[10]
    (count,) = struct.unpack_from('<I', b, 11)
    off = 15
    tilesets = []
    if version in (210, 211):
        enc = 'utf-8'
        n_auto = 31
    elif version == 209:
        enc = 'shift-jis'
        n_auto = 15
    else:
        raise ValueError(f'unsupported tileset version {version}')
    for i in range(count):
        title, off = read_tstr(b, off, enc)
        base, base_b, off = read_tstr_raw(b, off, enc)
        autos = []
        autos_b = []
        for _ in range(n_auto):
            f, f_b, off = read_tstr_raw(b, off, enc)
            if f:
                autos.append(f)
                autos_b.append(f_b)
        # separator1 (0xff)
        assert b[off] == 0xff, f'tileset {i}: sep1 {b[off]:#x}'
        off += 1
        # tag numbers
        (ntag,) = struct.unpack_from('<I', b, off)
        off += 4 + ntag
        # separator2 (0xff)
        assert b[off] == 0xff, f'tileset {i}: sep2 {b[off]:#x}'
        off += 1
        # passability records (bit-packed), we do not need them
        (npass,) = struct.unpack_from('<I', b, off)
        off += 4 + npass * 4
        tilesets.append(Tileset(index=i, title=title, base_file=base, auto_files=autos,
                                base_file_b=base_b, auto_files_b=autos_b))
    assert b[off] == 0xcf, f'footer {b[off]:#x}'
    return tilesets


@dataclass
class WolfMap:
    path: Path
    version_header: int
    version: int
    title: str
    tileset: int
    width: int
    height: int
    event_count: int
    layers: list      # layers[0..2] -> list[list[int]] height rows of width raw cells


def parse_mps(path, transpose=True) -> WolfMap:
    b = Path(path).read_bytes()
    assert b[10:16] == b'WOLFM\x00', f'bad magic {b[10:16]!r}'
    ver_header = b[16]
    assert b[17:20] == b'\x00\x00\x00'
    assert struct.unpack_from('<I', b, 20)[0] == 0x64
    version = b[24]
    assert version in (0x65, 0x66), f'version {version:#x}'
    title, off = read_tstr(b, 25)
    tileset, width, height, event_count = struct.unpack_from('<IIII', b, off)
    off += 16
    # Guard against truncated/incomplete files.
    if off + 4 > len(b):
        zero = [[0] * width for _ in range(height)]
        return WolfMap(path=Path(path), version_header=ver_header, version=version,
                       title=title, tileset=tileset, width=width, height=height,
                       event_count=event_count, layers=[zero, zero, zero])
    (first_pixel,) = struct.unpack_from('<I', b, off)
    n_px = width * height * 3
    # first_pixel == 0xFFFFFFFF means no tile-data block (zero layers).
    if first_pixel == 0xFFFFFFFF:
        zero = [[0] * width for _ in range(height)]
        return WolfMap(path=Path(path), version_header=ver_header, version=version,
                       title=title, tileset=tileset, width=width, height=height,
                       event_count=event_count, layers=[zero, zero, zero])
    # mapdata block: first_pixel + (width*height*12 - 4) skipped, then n_px u4 cells
    off += width * height * 12  # includes first_pixel
    cells = struct.unpack_from(f'<{n_px}I', b, off - (n_px * 4))
    storage_w, storage_h = width, height
    if transpose:
        # The file stores map data TRANSPOSED relative to the editor/game display:
        #   display[row][col] = storage[col * storage_width + row]
        disp_w, disp_h = storage_h, storage_w
        layer_bytes = storage_w * storage_h
        layers = []
        for li in range(3):
            seg = cells[li * layer_bytes:(li + 1) * layer_bytes]
            rows = [[seg[col * storage_w + row] for col in range(disp_w)] for row in range(disp_h)]
            layers.append(rows)
    else:
        # Original (non-transposed) interpretation.
        disp_w, disp_h = storage_w, storage_h
        layer_bytes = storage_w * storage_h
        layers = []
        for li in range(3):
            seg = cells[li * layer_bytes:(li + 1) * layer_bytes]
            if storage_w == storage_h:
                rows = [seg[y * disp_w:(y + 1) * disp_w] for y in range(disp_h)]
            else:
                # Non-square maps use a shifted/transposed storage layout:
                #   display[y][x] = storage[x*storage_h + y]
                rows = []
                for y in range(storage_h):
                    row = []
                    for x in range(storage_w):
                        idx = x * storage_h + y
                        row.append(seg[idx] if idx < len(seg) else 0)
                    rows.append(row)
            layers.append(rows)
    return WolfMap(path=Path(path), version_header=ver_header, version=version,
                   title=title, tileset=tileset, width=disp_w, height=disp_h,
                   event_count=event_count, layers=layers)


# ---- cell decode helpers -------------------------------------------------

def decode_cell(raw: int):
    """Return ('empty',) | ('base', index) | ('auto', autoid, (tl,tr,bl,br))."""
    if raw == 0:
        return ('empty',)
    if raw < 100000:
        return ('base', raw)
    aid = raw // 100000
    tl = raw % 10000 // 1000
    tr = raw % 1000 // 100
    bl = raw % 100 // 10
    br = raw % 10
    return ('auto', aid, (tl, tr, bl, br))
