"""Section parsing. Ported from ProcessSection.cs.

Section base class plus the specialised section types: FDST, RESC, INDX
(main/extra), CTOC and FONT.
"""

from __future__ import annotations

import zlib
from typing import Dict, List, Optional

from . import util
from .errors import UnpackKindleSException
from .palmdb import get_struct_be_indx_header


class Section:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.type = ""
        self.comment = ""
        if raw is None or len(raw) < 4:
            self.type = "Empty Section"
            return
        self.type = util.ascii_str(raw[0:4])
        if self.type == "??\r\n":
            self.type = "End Of File"
        elif self.type == "?6?\t":
            self.type = "Place Holder"
        elif self.type == "\0\0\0\0":
            self.type = "Empty Section0"

    def get_size(self) -> int:
        return len(self.raw)

    @classmethod
    def from_section(cls, s: "Section") -> "Section":
        """Equivalent of the C# `Section(Section s)` copy constructor for subclasses."""
        obj = cls.__new__(cls)
        Section._copy_init(obj, s)
        return obj

    @staticmethod
    def _copy_init(obj: "Section", s: "Section") -> None:
        obj.type = s.type
        obj.raw = s.raw
        obj.comment = ""


def _make_typed(type_str: str, raw: bytes) -> Section:
    """Equivalent of the C# `Section(string type, byte[] raw)` constructor."""
    s = Section.__new__(Section)
    s.type = type_str
    s.raw = raw
    s.comment = ""
    return s


class Text_Section(Section):
    def __init__(self, raw: bytes):
        s = _make_typed("Text", None)
        Section._copy_init(self, s)
        self._size = len(raw)

    def get_size(self) -> int:
        return self._size


class Huffman_Section(Section):
    def __init__(self, raw: bytes):
        s = _make_typed("Huffman", None)
        Section._copy_init(self, s)
        self._size = len(raw)

    def get_size(self) -> int:
        return self._size


class HuffmanCDIC_Section(Section):
    def __init__(self, raw: bytes):
        s = _make_typed("Huffman CDIC", None)
        Section._copy_init(self, s)
        self._size = len(raw)

    def get_size(self) -> int:
        return self._size


class Image_Section(Section):
    def __init__(self, s: Section, ext: str):
        Section._copy_init(self, s)
        self.type = "Image"
        self.raw = s.raw
        self.ext = ext


class FDST_Section(Section):
    def __init__(self, section: Section):
        Section._copy_init(self, section)
        if self.type != "FDST":
            raise UnpackKindleSException("Error on SectionFDST Process")
        n = util.get_uint32(self.raw, 8)
        self.table: List[int] = []
        for i in range(n):
            self.table.append(util.get_uint32(self.raw, 12 + 8 * i))


class RESC_Section(Section):
    def __init__(self, section: Section):
        from lxml import etree

        Section._copy_init(self, section)
        if self.type != "RESC":
            raise UnpackKindleSException("Error on SectionRESC Process")
        zero = len(self.raw) - 1
        while self.raw[zero] == 0:
            zero -= 1
        data = self.raw[16:16 + (zero - 15)].decode("utf-8")
        data = data[data.index("<"):]
        self.metadata = None
        self.spine = None
        meta = util.get_outer_xml(data, "metadata")
        if meta is not None:
            self.metadata = etree.fromstring(meta.encode("utf-8"))
        spi = util.get_outer_xml(data, "spine")
        if spi is not None:
            self.spine = etree.fromstring(spi.encode("utf-8"))
        else:
            raise UnpackKindleSException("RESC Section has none spine")


class INDX_Section(Section):
    def __init__(self, data: bytes):
        super().__init__(data)
        if self.type != "INDX":
            raise UnpackKindleSException("INDX Section Header Error")
        self.header = get_struct_be_indx_header(data, 4)


class _Tag:
    __slots__ = ("tag", "count", "value", "tag_value")

    def __init__(self, tag, count, value, tag_value):
        self.tag = tag
        self.count = count
        self.value = value
        self.tag_value = tag_value


class INDX_Section_Main(INDX_Section):
    def __init__(self, data: bytes, type_str: str):
        super().__init__(data)
        self.type = type_str
        self.tag_table_start = 0
        self.tag_table_end = 0
        self.ctrl_byte_count = 0
        self.or_dict: Optional[List[int]] = None
        self.read_tag()

    @property
    def tag_table_length(self) -> int:
        return (self.tag_table_end - self.tag_table_start) // 4

    def tag(self, i: int) -> int:
        return self.raw[self.tag_table_start + i * 4]

    def tag_value(self, i: int) -> int:
        return self.raw[self.tag_table_start + i * 4 + 1]

    def mask(self, i: int) -> int:
        return self.raw[self.tag_table_start + i * 4 + 2]

    def endflag(self, i: int) -> int:
        return self.raw[self.tag_table_start + i * 4 + 3]

    @property
    def is_sample(self) -> bool:
        return self.or_dict is not None

    def read_tag(self) -> None:
        off = self.header["tag_part_start"]
        tagx = util.ascii_str(self.raw[off:off + 4])
        if tagx != "TAGX":
            return
        self.tag_table_start = off + 12
        self.tag_table_end = off + util.get_uint32(self.raw, off + 4)
        self.ctrl_byte_count = util.get_uint32(self.raw, off + 8)

        # Sample book detection (KindleUnpack mobi_index.py:99).
        o_count = util.get_uint32(self.raw, 0xA4)
        o_entries = util.get_uint32(self.raw, 0xA8)
        op1 = util.get_uint32(self.raw, 0xAC)
        op2 = util.get_uint32(self.raw, 0xB0)
        if self.header["codepage"] == 65002 or o_count != 0 or o_entries > 0:
            if (o_count != 1
                    or util.ascii_str(self.raw[op1:op1 + 4]) != "ORDT"
                    or util.ascii_str(self.raw[op2:op2 + 4]) != "ORDT"):
                raise UnpackKindleSException("Sample Book Assumption Failure.")
            from . import log
            log.log("Book Sample Assumption.")
            self.or_dict = []
            for i in range(o_entries):
                self.or_dict.append(util.get_uint16(self.raw, op2 + 4 + i * 2))


class INDX_Section_Extra(INDX_Section):
    def __init__(self, data: bytes, main: INDX_Section_Main):
        super().__init__(data)
        self.type = "INDX Section (Extra)"
        self.main_sec = main
        self.index_pos: List[int] = []
        self.tags: List[Optional[_Tag]] = []
        self.tagmaps: List[Dict[int, List[int]]] = []
        self.texts: List[str] = []
        self._value = 0
        self._consumed = 0

    def read_tag_map(self) -> None:
        any_count = self.header["any_count"]
        index_offset = self.header["index_offset"]
        self.index_pos = [0] * (any_count + 1)
        for i in range(any_count):
            self.index_pos[i] = util.get_uint16(self.raw, index_offset + i * 2 + 4)
        self.index_pos[any_count] = index_offset
        self.tagmaps = [None] * any_count
        self.texts = [None] * any_count
        for i in range(any_count):
            length = self.raw[self.index_pos[i]]
            text = bytearray(self.raw[self.index_pos[i] + 1:self.index_pos[i] + 1 + length])
            if self.main_sec.is_sample:
                for j in range(len(text)):
                    text[j] = self.main_sec.or_dict[text[j]] & 0xFF
            self.texts[i] = bytes(text).decode("utf-8")
            self.tagmaps[i] = self._get_tag_map(
                self.index_pos[i] + 1 + length, self.index_pos[i + 1])

    def _get_tag_map(self, start_pos: int, end_pos: int) -> Dict[int, List[int]]:
        ctrl_byte_index = 0
        data_start = start_pos + self.main_sec.ctrl_byte_count
        tag_table_length = self.main_sec.tag_table_length
        self.tags = [None] * tag_table_length
        for i in range(tag_table_length):
            if self.main_sec.endflag(i) == 0x01:
                ctrl_byte_index += 1
                continue
            c = self.raw[start_pos + ctrl_byte_index]
            mask_i = self.main_sec.mask(i)
            v = c & mask_i
            if v != 0:
                if v == mask_i:
                    if self._count_bit(v) > 1:
                        self._get_variable_width_value(data_start)
                        data_start += self._consumed
                        self.tags[i] = _Tag(self.main_sec.tag(i), 0, self._value,
                                            self.main_sec.tag_value(i))
                    else:
                        self.tags[i] = _Tag(self.main_sec.tag(i), 1, 0,
                                            self.main_sec.tag_value(i))
                else:
                    mask = mask_i
                    while (mask & 1) == 0:
                        mask = mask >> 1
                        v = v >> 1
                    self.tags[i] = _Tag(self.main_sec.tag(i), v, 0,
                                        self.main_sec.tag_value(i))
        # NOTE: the C# code shares a single `values` list across every tag and
        # assigns the same reference to each hashtable key. Replicate exactly:
        # every key ends up pointing at the full accumulated list.
        hashtable: Dict[int, List[int]] = {}
        values: List[int] = []
        for tag in self.tags:
            if tag is None:
                continue
            if tag.count != 0:
                for _j in range(tag.count):
                    for _i in range(tag.tag_value):
                        self._get_variable_width_value(data_start)
                        data_start += self._consumed
                        values.append(self._value)
            else:
                consum = 0
                while consum < tag.value:
                    self._get_variable_width_value(data_start)
                    data_start += self._consumed
                    consum += self._consumed
                    values.append(self._value)
                if consum != tag.value:
                    raise UnpackKindleSException("tag decode error")
            hashtable[tag.tag] = values
        return hashtable

    def _get_variable_width_value(self, offset: int) -> None:
        self._consumed = 0
        self._value = 0
        finish = False
        while not finish:
            x = self.raw[offset + self._consumed]
            self._consumed += 1
            if (x & 0x80) > 0:
                finish = True
            self._value = (self._value << 7) | (x & 0x7F)

    @staticmethod
    def _count_bit(a: int) -> int:
        count = 0
        for _ in range(8):
            if (a & 1) > 0:
                count += 1
            a = a >> 1
        return count


class CTOC_Section(Section):
    def __init__(self, data: bytes):
        super().__init__(data)
        self.type = "CTOC"
        self.ctoc_data: Dict[int, str] = {}
        self._value = 0
        self._consumed = 0
        offset = 0
        while offset < len(data):
            if data[offset] == 0:
                break
            idx_offs = offset
            self._get_variable_width_value(offset)
            offset += self._consumed
            name = data[offset:offset + self._value].decode("utf-8")
            offset += self._value
            self.ctoc_data[idx_offs] = name

    def _get_variable_width_value(self, offset: int) -> None:
        self._consumed = 0
        self._value = 0
        finish = False
        while not finish:
            x = self.raw[offset + self._consumed]
            self._consumed += 1
            if (x & 0x80) > 0:
                finish = True
            self._value = (self._value << 7) | (x & 0x7F)


class Font_Section(Section):
    _ZLIB = 0x1
    _XOR = 0x2

    def __init__(self, section: Section):
        Section._copy_init(self, section)
        self.original_length = util.get_uint32(self.raw, 0x04)
        self.flags = util.get_uint32(self.raw, 0x08)
        self.font_data_start = util.get_uint32(self.raw, 0x0C)
        self.xor_length = util.get_uint32(self.raw, 0x10)
        self.xor_start = util.get_uint32(self.raw, 0x14)
        data = bytearray(self.raw[self.font_data_start:])
        if self._XOR & self.flags:
            key = self.raw[self.xor_start:self.xor_start + self.xor_length]
            klen = len(key)
            for i in range(min(1040, len(data))):
                data[i] ^= key[i % klen]
        if self._ZLIB & self.flags:
            d = zlib.decompressobj()
            out = d.decompress(bytes(data)) + d.flush()
            data = bytearray(out[:self.original_length])
        self.data = bytes(data)
        header = util.ascii_str(self.data[0:4])
        if header == "OTTO":
            self.ext = ".otf"
        elif header in ("ttcf", "true", "\0\x01\0\0"):
            self.ext = ".ttf"
        else:
            self.ext = None
            from . import log
            log.log("[Warn] unknown font header: 0x{:X}{:X}{:X}{:X}".format(
                self.data[0], self.data[1], self.data[2], self.data[3]))
