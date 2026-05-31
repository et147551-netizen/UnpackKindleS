"""Text-section decompressors. Ported from Decompress.cs.

PalmDOC (compression type 2) and HUFF/CDIC (type 0x4448).
"""

from __future__ import annotations

from . import util
from .errors import UnpackKindleSException

_MASK32 = 0xFFFFFFFF
_MASK64 = 0xFFFFFFFFFFFFFFFF


class PalmdocDecoder:
    """PalmDOC LZ77 variant decoder."""

    def decode(self, data: bytes) -> bytes:
        r = bytearray()
        pos = 0
        n_len = len(data)
        while pos < n_len:
            c = data[pos]
            pos += 1
            if 1 <= c <= 8:
                r.extend(data[pos:pos + c])
                pos += c
            elif c < 128:
                r.append(c)
            elif c >= 192:
                r.append(0x20)
                r.append(c ^ 128)
            else:
                if pos < n_len:
                    cx = (c << 8) | data[pos]
                    pos += 1
                    m = (cx >> 3) & 0x07FF
                    n = (cx & 7) + 3
                    if m > n:
                        # Non-overlapping copy from a snapshot of the output.
                        start = len(r) - m
                        r.extend(r[start:start + n])
                    else:
                        # Byte-by-byte (regions may overlap with the output tail).
                        for _ in range(n):
                            r.append(r[len(r) - m])
        return bytes(r)


class _HuffmanCDIC:
    """Accumulates dictionary slices from CDIC sections."""

    def __init__(self):
        self.slice = []        # list[bytes]
        self.slice_flag = []   # list[bool]  (True once decoded)

    def add(self, raw: bytes) -> None:
        ident = util.ascii_str(raw[0:4])
        if ident != "CDIC":
            raise UnpackKindleSException("Unexpect Section Header at CDIC")
        phases = util.get_uint32(raw, 8)
        bits = util.get_uint32(raw, 12)
        n = min(1 << bits, phases - len(self.slice))
        for i in range(n):
            off = util.get_uint16(raw, 16 + i * 2)
            length = util.get_uint16(raw, 16 + off)
            self.slice_flag.append((length & 0x8000) > 0)
            self.slice.append(raw[18 + off:18 + off + (length & 0x7FFF)])


class HuffmanDecoder:
    """HUFF/CDIC decoder."""

    def __init__(self, seed_section: bytes):
        ident = util.ascii_str(seed_section[0:4])
        if ident != "HUFF":
            raise UnpackKindleSException("Unexpect Section Header at Huff Decoder")
        off1 = util.get_uint32(seed_section, 8)
        off2 = util.get_uint32(seed_section, 12)

        self.mincode = [0] * 33
        self.maxcode = [0] * 33
        self.codelen = [0] * 256
        self.term = [False] * 256
        self.maxcode1 = [0] * 256

        for i in range(256):
            v = util.get_uint32(seed_section, off1 + i * 4)
            self.codelen[i] = v & 0x1F
            self.term[i] = (v & 0x80) > 0
            self.maxcode1[i] = v >> 8
            if self.codelen[i] == 0 or (self.codelen[i] <= 8 and not self.term[i]):
                raise UnpackKindleSException("Huff decode error.")
            self.maxcode1[i] = (((self.maxcode1[i] + 1) << (32 - self.codelen[i])) - 1) & _MASK64

        self.mincode[0] = 0
        self.maxcode[0] = ((1 << 32) - 1)
        for i in range(1, 33):
            mn = util.get_uint32(seed_section, off2 + (i - 1) * 4 * 2)
            mx = util.get_uint32(seed_section, off2 + (i - 1) * 4 * 2 + 4)
            self.mincode[i] = (mn << (32 - i)) & _MASK64
            self.maxcode[i] = (((mx + 1) << (32 - i)) - 1) & _MASK64

        self.cdic = _HuffmanCDIC()

    def add_cdic(self, cdic_section: bytes) -> None:
        self.cdic.add(cdic_section)

    def decode(self, _data: bytes) -> bytes:
        data = bytes(_data) + b"\x00" * 8
        bitsleft = len(_data) * 8
        pos = 0
        x = util.get_uint64(data, pos)
        n = 32
        s = bytearray()
        while True:
            if n <= 0:
                pos += 4
                x = util.get_uint64(data, pos)
                n += 32
            code = (x >> n) & _MASK32
            dict1_i = code >> 24
            _codelen = self.codelen[dict1_i]
            _maxcode = self.maxcode1[dict1_i]
            if not self.term[dict1_i]:
                while code < self.mincode[_codelen]:
                    _codelen += 1
                _maxcode = self.maxcode[_codelen]
            n -= _codelen
            bitsleft -= _codelen
            if bitsleft < 0:
                break
            r = (_maxcode - code) >> (32 - _codelen)
            sl = self.cdic.slice[r]
            flag = self.cdic.slice_flag[r]
            if not flag:
                sl = self.decode(sl)
                self.cdic.slice[r] = sl
                self.cdic.slice_flag[r] = True
            s.extend(sl)
        return bytes(s)
