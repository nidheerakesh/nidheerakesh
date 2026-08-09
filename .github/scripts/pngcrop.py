#!/usr/bin/env python3
"""Crop a PNG to its non-transparent content. No third-party dependencies.

Only handles what Chromium's --screenshot emits: 8-bit RGBA, non-interlaced.
Anything else raises rather than silently producing a wrong image.
"""

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunks(data):
    offset = len(SIGNATURE)
    while offset < len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        yield kind, payload
        offset += 12 + length


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode(data):
    """Return (width, height, rows) where each row is a bytearray of RGBA."""
    if not data.startswith(SIGNATURE):
        raise ValueError("not a PNG")

    width = height = None
    idat = bytearray()
    for kind, payload in _chunks(data):
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (depth, color, interlace) != (8, 6, 0):
                raise ValueError(
                    f"unsupported PNG: depth={depth} color={color} interlace={interlace}"
                )
        elif kind == b"IDAT":
            idat += payload
        elif kind == b"IEND":
            break

    if width is None:
        raise ValueError("no IHDR")

    raw = zlib.decompress(bytes(idat))
    stride = width * 4
    rows = []
    previous = bytearray(stride)
    position = 0
    for _ in range(height):
        filter_type = raw[position]
        position += 1
        line = bytearray(raw[position : position + stride])
        position += stride

        if filter_type == 1:
            for i in range(4, stride):
                line[i] = (line[i] + line[i - 4]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - 4] if i >= 4 else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - 4] if i >= 4 else 0
                upper_left = previous[i - 4] if i >= 4 else 0
                line[i] = (line[i] + _paeth(left, previous[i], upper_left)) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"bad filter type {filter_type}")

        rows.append(line)
        previous = line

    return width, height, rows


def encode(width, height, rows):
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter: None
        raw += row

    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return (
        SIGNATURE
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def crop_to_content(data, padding=4):
    """Trim fully transparent margins, keeping `padding` px of breathing room."""
    width, height, rows = decode(data)

    top, bottom, left, right = None, None, width, -1
    for y, row in enumerate(rows):
        row_left, row_right = None, None
        for x in range(width):
            if row[x * 4 + 3]:  # alpha
                if row_left is None:
                    row_left = x
                row_right = x
        if row_left is None:
            continue
        if top is None:
            top = y
        bottom = y
        left = min(left, row_left)
        right = max(right, row_right)

    if top is None:
        raise ValueError("image is fully transparent — nothing was rendered")

    left = max(0, left - padding)
    right = min(width - 1, right + padding)
    top = max(0, top - padding)
    bottom = min(height - 1, bottom + padding)

    cropped = [
        rows[y][left * 4 : (right + 1) * 4] for y in range(top, bottom + 1)
    ]
    return encode(right - left + 1, bottom - top + 1, cropped)
