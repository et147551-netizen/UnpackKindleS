"""MOBI / AZW6 headers and EXTH metadata. Ported from Headers.cs."""

from __future__ import annotations

from typing import Dict

from . import util
from . import log
from . import idmapping
from .errors import UnpackKindleSException
from .palmdb import get_struct_be_azw6_header
from .sections import Section, _make_typed


class ExtMeta:
    """EXTH metadata block."""

    def __init__(self, ext: bytes):
        self.id_value: Dict[int, int] = {}
        self.id_string: Dict[int, str] = {}
        self.id_hex: Dict[int, str] = {}

        num_items = util.get_uint32(ext, 8)
        pos = 12
        for _ in range(num_items):
            id_ = util.get_uint32(ext, pos)
            size = util.get_uint32(ext, pos + 4)
            if id_ in idmapping.id_map_strings:
                a = ext[pos + 8:pos + 8 + (size - 8)].decode("utf-8")
                if id_ in self.id_string:
                    if id_ == 100 or id_ == 517:
                        self.id_string[id_] += "&" + a.replace("&", "＆")
                    else:
                        log.log("Meta id duplicate:{0}\nPervious:{1}  \nLatter:{2}".format(
                            idmapping.id_map_strings[id_], self.id_string[id_], a))
                else:
                    self.id_string[id_] = a
            elif id_ in idmapping.id_map_values:
                a = 0
                if size == 9:
                    a = util.get_uint8(ext, pos + 8)
                elif size == 10:
                    a = util.get_uint16(ext, pos + 8)
                elif size == 12:
                    a = util.get_uint32(ext, pos + 8)
                elif size == 16:
                    a = util.get_uint64(ext, pos + 8)
                else:
                    log.log("unexpected size:" + str(size))
                if id_ in self.id_value:
                    log.log("Meta id duplicate:{0}\nPervious:{1}  \nLatter:{2}".format(
                        idmapping.id_map_values[id_], self.id_value[id_], a))
                else:
                    self.id_value[id_] = a
            elif id_ in idmapping.id_map_hex:
                a = util.to_hex_string(ext, pos + 8, size - 8)
                if id_ in self.id_hex:
                    log.log("Meta id duplicate:{0}\nPervious:{1}  \nLatter:{2}".format(
                        idmapping.id_map_hex[id_], self.id_hex[id_], a))
                else:
                    self.id_hex[id_] = a
            else:
                a = util.to_hex_string(ext, pos + 8, size - 8)
                log.log(" unknown id " + str(id_) + ":" + a)
            pos += size


class MobiHeader(Section):
    def __init__(self, header: bytes):
        base = _make_typed("Mobi Header", header)
        Section._copy_init(self, base)

        self.ext_meta = None
        self.huffman_start_index = 0
        self.huffman_count = 0

        self.records = util.get_uint16(header, 8)
        self.compression = util.get_uint16(header, 0)
        if self.compression == 0x4448:
            self.huffman_start_index = util.get_uint32(header, 0x70)
            self.huffman_count = util.get_uint32(header, 0x74)
        self.length = util.get_uint32(header, 20)
        self.mobi_type = util.get_uint32(header, 24)
        self.codepage = util.get_uint32(header, 28)
        self.unique_id = util.get_uint32(header, 32)
        self.version = util.get_uint32(header, 36)
        title_off = util.get_uint32(header, 0x54)
        title_len = util.get_uint32(header, 0x58)
        self.title = header[title_off:title_off + title_len].decode("utf-8")
        self.exth_flag = util.get_uint32(header, 0x80)
        if (self.exth_flag & 0x40) > 0:
            exth_len = util.get_uint32(header, self.length + 20)
            exth = header[self.length + 16:self.length + 16 + exth_len]
            self.ext_meta = ExtMeta(exth)
        self.crypto_type = util.get_uint16(header, 0xC)
        if self.crypto_type != 0:
            raise UnpackKindleSException(
                "Unable to handle an encrypted file. Crypto Type:" + str(self.crypto_type))
        self.first_res_index = util.get_uint32(header, 0x6C)
        self.first_nontext_index = util.get_uint32(header, 0x50)
        self.ncx_index = util.get_uint32(header, 0xF4)
        self.skel_index = util.get_uint32(header, 0xFC)
        self.frag_index = util.get_uint32(header, 0xF8)
        self.guide_index = util.get_uint32(header, 0x104)
        self.fdst_start_index = util.get_uint32(header, 0xC0)
        self.fdst_count = util.get_uint32(header, 0xC4)
        self.mobi_length = util.get_uint32(header, 0x14)
        self.mobi_version = util.get_uint32(header, 0x68)
        self.mobi_flags = util.get_uint16(header, 0xF2)


class Azw6Header(Section):
    def __init__(self, header_raw: bytes):
        base = _make_typed("Azw6 Header", header_raw)
        Section._copy_init(self, base)
        self.title = None
        self.meta = None
        self.info = get_struct_be_azw6_header(header_raw, 0)
        # C# does Array.Reverse(info.magic) after marshalling.
        self.info["magic"] = self.info["magic"][::-1]
        if self.info["codepage"] != 65001:
            return
        title_off = self.info["title_offset"]
        title_len = self.info["title_length"]
        self.title = header_raw[title_off:title_off + title_len].decode("utf-8")
        ext = header_raw[48:]
        self.meta = ExtMeta(ext)
