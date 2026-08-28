"""Reverse-engineering helpers for WOLF RPG Editor 0x67 `.mps` maps.

Format discovered:

* The first 25 bytes are the normal WOLF header:
  `10 zero bytes + "WOLFM\\0" + 0x55 + 3 zero bytes + 0x64 + 0x67`.
* Starting at offset 25 the file stores an LZ4 block:

      u32 decompressed_payload_size
      u32 compressed_payload_size
      LZ4 block payload

  The decompressed payload is the *remainder of the logical file* that would
  start right after the 25-byte header.  Reconstructing the logical file is:

      logical = original[0:25] + lz4_decompress(original[33:33+compressed_size])

* The logical file then has the familiar WOLF format:

      t_str title      (u32 byte length incl. NUL + UTF-8 bytes)
      u32 tileset
      u32 width
      u32 height
      u32 event_count
      u32 cells[width * height * 3]   (3 layers, row-major storage)
      events / footer ...

The mapdata command/run-length layer that earlier looked like compact varints
was actually just LZ4-compressed bytes; after LZ4 decompression the tile cells
are plain little-endian u32 values.
"""
from __future__ import annotations

import struct
from pathlib import Path

try:
    import lz4.block
except ImportError as exc:  # pragma: no cover - helpful error
    raise ImportError(
        'decode_mps_0x67 requires the "lz4" package. Install it with: '
        'python -m pip install lz4'
    ) from exc

MAGIC = b'WOLFM\x00'
HEADER_SIZE = 25
LZ4_SIZE_FIELD = 8  # two u32 fields


def _read_tstr(b: bytes, off: int, enc: str = 'utf-8'):
    """WOLF t_str: u32 length + bytes (length includes trailing NUL)."""
    (n,) = struct.unpack_from('<I', b, off)
    raw = b[off + 4:off + 4 + n]
    s = raw.rstrip(b'\x00').decode(enc, errors='replace')
    return s, off + 4 + n


def _logical_bytes(path) -> bytes:
    """Read a 0x67 file and return the logical (decompressed) file bytes."""
    b = Path(path).read_bytes()
    if len(b) < HEADER_SIZE + LZ4_SIZE_FIELD or b[10:16] != MAGIC:
        raise ValueError('bad WOLF magic')
    if b[24] != 0x67:
        raise ValueError(f'not a 0x67 map (version=0x{b[24]:02x})')

    dec_size, enc_size = struct.unpack_from('<II', b, HEADER_SIZE)
    payload = b[HEADER_SIZE + LZ4_SIZE_FIELD:HEADER_SIZE + LZ4_SIZE_FIELD + enc_size]
    if len(payload) != enc_size:
        raise ValueError('truncated LZ4 payload')
    try:
        dec = lz4.block.decompress(payload, uncompressed_size=dec_size)
    except Exception as exc:
        raise ValueError(f'LZ4 decompression failed: {exc}') from exc
    if len(dec) != dec_size:
        raise ValueError(
            f'LZ4 decompressed size mismatch: expected {dec_size}, got {len(dec)}'
        )
    return b[:HEADER_SIZE] + dec


def parse_067_header(path) -> dict:
    """Parse the logical 0x67 header; return metadata and mapdata start offset.

    Two variants exist:
    * Converted maps: offset 25 = u32 title length, then UTF-8 title, then
      tileset/width/height/event_count.
    * New maps created in the editor: offset 25 = a single flag byte (usually
      0x01), no title, then tileset/width/height/event_count at offset 26.
    """
    logical = _logical_bytes(path)
    if len(logical) < HEADER_SIZE + 4:
        raise ValueError('header truncated')

    # Try converted-map layout first.
    title_len = struct.unpack_from('<I', logical, HEADER_SIZE)[0]
    if 0 < title_len <= 256 and HEADER_SIZE + 4 + title_len + 16 <= len(logical):
        title_off = HEADER_SIZE + 4
        title_raw = logical[title_off:title_off + title_len]
        # Converted maps have a readable UTF-8 title (or at least a NUL terminator).
        if title_raw.endswith(b'\x00'):
            title = title_raw.rstrip(b'\x00').decode('utf-8', errors='replace')
            off = title_off + title_len
            tileset, width, height, event_count = struct.unpack_from('<IIII', logical, off)
            return {
                'title': title,
                'tileset': tileset,
                'width': width,
                'height': height,
                'event_count': event_count,
                'mapdata_offset': off + 16,
                'logical_size': len(logical),
                'file_size': len(Path(path).read_bytes()),
            }

    # New-map layout: flag byte at offset 25, then four u32 fields at offset 26.
    off = HEADER_SIZE + 1
    if off + 16 > len(logical):
        raise ValueError('header truncated')
    tileset, width, height, event_count = struct.unpack_from('<IIII', logical, off)
    return {
        'title': '',
        'tileset': tileset,
        'width': width,
        'height': height,
        'event_count': event_count,
        'mapdata_offset': off + 16,
        'logical_size': len(logical),
        'file_size': len(Path(path).read_bytes()),
    }


def extract_mapdata(path) -> bytes:
    """Return the logical mapdata cell bytes (u32 cells for 3 layers)."""
    info = parse_067_header(path)
    logical = _logical_bytes(path)
    start = info['mapdata_offset']
    n = info['width'] * info['height'] * 3 * 4
    return logical[start:start + n]


def read_wolf_varint(buf: bytes, off: int):
    """Read the compact little-endian varint found inside WOLF data streams.

    Kept for compatibility with earlier partial research.  For 0x67 maps the
    tile cells are plain u32 values after LZ4 decompression, so this is not
    needed by `decode_mps_0x67`.
    """
    start = off
    while off < len(buf) and (buf[off] & 0x80):
        off += 1
    if off >= len(buf):
        raise ValueError('truncated varint')
    off += 1
    raw = buf[start:off]
    value = 0
    for i, x in enumerate(raw):
        value |= x << (8 * i)
    return value, off


def decode_mps_0x67(path, transpose=False) -> tuple:
    """Decode a 0x67 map into `(width, height, layers)`.

    `layers` is a list of three `height` x `width` lists of raw tile-cell u32
    values.  The default (`transpose=False`) keeps the file's row-major storage
    order and the header width/height.  Pass `transpose=True` to get the
    editor/display orientation used by `wolfrpg.parse_mps(transpose=True)`
    (display width/height are the swapped storage dimensions).
    """
    logical = _logical_bytes(path)
    title, off = _read_tstr(logical, HEADER_SIZE)
    tileset, width, height, event_count = struct.unpack_from('<IIII', logical, off)
    off += 16

    n_px = width * height * 3

    # Some maps are marked as having no tile data at all (0xFFFFFFFF).
    # WolfTL handles this by skipping tile loading; return zero-filled layers.
    if off + 4 <= len(logical) and struct.unpack_from('<I', logical, off)[0] == 0xFFFFFFFF:
        zero_layer = [[0] * width for _ in range(height)]
        return width, height, [zero_layer, zero_layer, zero_layer]

    if off + n_px * 4 > len(logical):
        raise ValueError(
            f'mapdata truncated: need {n_px * 4} bytes, only '
            f'{len(logical) - off} available'
        )
    cells = struct.unpack_from(f'<{n_px}I', logical, off)

    storage_w, storage_h = width, height
    layer_bytes = storage_w * storage_h
    layers = []
    for li in range(3):
        seg = cells[li * layer_bytes:(li + 1) * layer_bytes]
        if transpose:
            # File stores transposed: display[row][col] =
            # storage[col * storage_width + row].
            disp_w, disp_h = storage_h, storage_w
            rows = [
                [seg[col * storage_w + row] for col in range(disp_w)]
                for row in range(disp_h)
            ]
            layers.append(rows)
        else:
            if storage_w == storage_h:
                rows = [
                    seg[y * storage_w:(y + 1) * storage_w]
                    for y in range(storage_h)
                ]
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

    if transpose:
        return disp_w, disp_h, layers
    return storage_w, storage_h, layers
