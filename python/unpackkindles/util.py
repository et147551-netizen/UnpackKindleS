"""Utility helpers. Ported from utils.cs.

Binary readers are big-endian (the C# code reverses bytes before BitConverter).
Image handling uses Pillow instead of System.Drawing.
"""

from __future__ import annotations

import io
from typing import List, Tuple


def ascii_str(b: bytes) -> str:
    """Mimic .NET Encoding.ASCII.GetString: bytes >= 128 become '?'."""
    return "".join(chr(c) if c < 128 else "?" for c in b)


def get_uint64(src: bytes, start: int) -> int:
    return int.from_bytes(src[start:start + 8], "big")


def get_uint32(src: bytes, start: int) -> int:
    return int.from_bytes(src[start:start + 4], "big")


def get_uint16(src: bytes, start: int) -> int:
    return int.from_bytes(src[start:start + 2], "big")


def get_uint8(src: bytes, start: int) -> int:
    return src[start]


def to_hex_string(src: bytes, start: int, length: int) -> str:
    """Uppercase hex string of length bytes starting at start."""
    return src[start:start + length].hex().upper()


def guess_image_type(data: bytes):
    """Return the image extension by magic bytes, or None. Ported from GuessImageType."""
    if len(data) < 4:
        return None
    if data[0] == 0xFF and data[1] == 0xD8:
        return ".jpg"
    if data[0:4] == b"GIF8":
        return ".gif"
    if data[0:4] == b"\x89\x50\x4e\x47":
        return ".png"
    return None


def get_outer_xml(data: str, tagname: str):
    """Extract the outer XML of <tagname>...</tagname> from a string. Ported from GetOuterXML."""
    start = data.find("<" + tagname)
    if start < 0:
        return None
    end = data.find("</" + tagname + ">") + 3 + len(tagname)
    return data[start:end]


def get_struct_be(data: bytes, offset: int, fields: List[Tuple[str, int, bool]]) -> dict:
    """Replicate Util.GetStructBE<T>.

    The C# code copies `size` bytes, reverses the *entire* block, then marshals
    it sequentially on a little-endian machine. Reversing the whole block and
    reading little-endian sequentially in declared field order reproduces that
    exactly (so integer fields end up read in reverse byte order).

    `fields` is a list of (name, width_in_bytes, is_byte_array) in C# declaration
    order.
    """
    size = sum(w for _, w, _ in fields)
    block = data[offset:offset + size][::-1]
    result = {}
    pos = 0
    for name, width, is_bytes in fields:
        chunk = block[pos:pos + width]
        if is_bytes:
            result[name] = bytes(chunk)
        else:
            result[name] = int.from_bytes(chunk, "little")
        pos += width
    return result


def decode_base32(s: str) -> int:
    """Decode a kindle base32 token (0-9, A-V). Ported from DecodeBase32."""
    r = 0
    for c in s:
        if c.isdigit():
            v = ord(c) - ord("0")
        else:
            v = ord(c) - ord("A") + 10
        r = r * 32 + v
    return r


def number(n: int, length: int = 4) -> str:
    """Zero-pad n to at least `length` digits. Ported from Number."""
    r = str(n)
    while len(r) < length:
        r = "0" + r
    return r


def filename_check(s: str) -> str:
    """Replace characters illegal in filenames with full-width equivalents."""
    table = {
        "?": "？",
        "\\": "＼",
        "/": "／",
        ":": "：",
        "*": "＊",
        '"': "＂",
        "|": "｜",
        "<": "＜",
        ">": "＞",
    }
    return "".join(table.get(ch, ch) for ch in s)


def get_image_size(data: bytes) -> Tuple[int, int]:
    """Return (width, height) of an image. Ported from GetImageSize (System.Drawing -> Pillow)."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        return (img.width, img.height)
