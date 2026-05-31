"""PalmDB container base class and binary struct layouts.

Ported from the AzwFile/SectionInfo classes and the struct definitions in
Structs&Dictionary.cs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from . import util


# Field layout for Azw6HeaderInfo (name, width_in_bytes, is_byte_array), in C# order.
AZW6_HEADER_FIELDS = [
    ("title_length", 4, False),
    ("title_offset", 4, False),
    ("unknown2", 4, False),
    ("offset_to_hrefs", 4, False),
    ("num_wo_placeholders", 4, False),
    ("num_resc_recs", 4, False),
    ("unknown1", 4, False),
    ("unknown0", 4, False),
    ("codepage", 4, False),
    ("count", 2, False),
    ("type", 2, False),
    ("record_size", 4, False),
    ("magic", 4, True),
]

# Field layout for INDX_Section_Header (13 x UInt32), in C# order.
INDX_HEADER_FIELDS = [
    ("ctoc_count", 4, False),
    ("ligt_count", 4, False),
    ("ligt", 4, False),
    ("ordt", 4, False),
    ("total", 4, False),
    ("lng", 4, False),
    ("codepage", 4, False),
    ("any_count", 4, False),
    ("index_offset", 4, False),
    ("gen", 4, False),
    ("type", 4, False),
    ("nul1", 4, False),
    ("tag_part_start", 4, False),
]


@dataclass
class SectionInfo:
    start_addr: int = 0
    end_addr: int = 0

    @property
    def length(self) -> int:
        return self.end_addr - self.start_addr


class AzwFile:
    """Base PalmDB-style container parser."""

    def __init__(self, path: str):
        with open(path, "rb") as f:
            self.raw_data = f.read()
        self.section_count: int = 0
        self.section_info: List[SectionInfo] = []
        self.sections: List = []
        self.ident: str = ""
        self._get_section_info()

    def _get_section_info(self) -> None:
        self.ident = util.ascii_str(self.raw_data[0x3C:0x3C + 8])
        self.section_count = util.get_uint16(self.raw_data, 76)
        self.section_info = [SectionInfo() for _ in range(self.section_count)]
        if self.section_count == 0:
            return
        self.section_info[0].start_addr = util.get_uint32(self.raw_data, 78)
        for i in range(1, self.section_count):
            self.section_info[i].start_addr = util.get_uint32(self.raw_data, 78 + i * 8)
            self.section_info[i - 1].end_addr = self.section_info[i].start_addr
        self.section_info[self.section_count - 1].end_addr = len(self.raw_data)

    def get_section_data(self, i: int) -> bytes:
        info = self.section_info[i]
        return self.raw_data[info.start_addr:info.end_addr]


def get_struct_be_indx_header(data: bytes, offset: int) -> dict:
    return util.get_struct_be(data, offset, INDX_HEADER_FIELDS)


def get_struct_be_azw6_header(data: bytes, offset: int) -> dict:
    return util.get_struct_be(data, offset, AZW6_HEADER_FIELDS)
