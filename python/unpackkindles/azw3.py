"""AZW3 (MOBI8) parser. Ported from Azw3File.cs."""

from __future__ import annotations

from typing import List, Optional

from . import util
from . import log
from .errors import UnpackKindleSException
from .palmdb import AzwFile
from .headers import MobiHeader
from .decompress import PalmdocDecoder, HuffmanDecoder
from .models import Skeleton_item, Fragment_item, Guide_item, IndexInfo_item
from .sections import (
    Section, Text_Section, Huffman_Section, HuffmanCDIC_Section, Image_Section,
    FDST_Section, RESC_Section, Font_Section,
    INDX_Section_Main, INDX_Section_Extra, CTOC_Section,
)


class Azw3File(AzwFile):
    def __init__(self, path: str):
        super().__init__(path)
        self.rawML = b""
        self.mobi_header: Optional[MobiHeader] = None
        self.decoder = None
        self.fdst: Optional[FDST_Section] = None
        self.resc: Optional[RESC_Section] = None
        self.xhtmls: List[str] = []
        self.flows: List[str] = []
        self.flow_process_log: List[Optional[str]] = []
        self.skeleton_table: Optional[List[Skeleton_item]] = None
        self.frag_table: Optional[List[Fragment_item]] = None
        self.guide_table: Optional[List[Guide_item]] = None
        self.index_info_table: Optional[List[IndexInfo_item]] = None

        if self.section_count > 0:
            self.sections = [None] * self.section_count
            if self.ident == "BOOKMOBI":
                self.mobi_header = MobiHeader(self.get_section_data(0))
                self.sections[0] = self.mobi_header
                if self.mobi_header.codepage != 65001:
                    raise UnpackKindleSException("not UTF8")
                if self.mobi_header.version != 8:
                    raise UnpackKindleSException(
                        "Unhandle mobi version:" + str(self.mobi_header.version))
                self._get_raw_ml()
                self._process_res()
                self._process_index()
                self._build_parts()
                for i in range(self.section_count):
                    if self.sections[i] is None:
                        self.sections[i] = Section(self.get_section_data(i))

    @property
    def title(self) -> str:
        return self.mobi_header.title

    @property
    def author(self) -> str:
        meta = self.mobi_header.ext_meta
        if 100 in meta.id_string:
            return meta.id_string[100]
        return ""

    def _get_raw_ml(self) -> None:
        mh = self.mobi_header
        if mh.compression == 2:
            self.decoder = PalmdocDecoder()
        elif mh.compression == 0x4448:
            r = self.get_section_data(mh.huffman_start_index)
            decoder = HuffmanDecoder(r)
            self.sections[mh.huffman_start_index] = Huffman_Section(r)
            for i in range(mh.huffman_count - 1):
                r = self.get_section_data(mh.huffman_start_index + i + 1)
                decoder.add_cdic(r)
                self.sections[mh.huffman_start_index + i + 1] = HuffmanCDIC_Section(r)
            self.decoder = decoder
        else:
            raise UnpackKindleSException("Unhandled compression type.")

        multibyte = (mh.mobi_flags & 1) > 0
        trailers = 0
        t = mh.mobi_flags
        while t > 1:
            if (t & 2) > 0:
                trailers += 1
            t = t >> 1

        def trim(data: bytes) -> bytes:
            for _ in range(trailers):
                num = 0
                for j in range(max(len(data) - 4, 0), len(data)):
                    if data[j] > 0x80:
                        num = 0
                    num = (num << 7) | (data[j] & 0x7F)
                data = data[:len(data) - num]
            if multibyte:
                num = (data[-1] & 3) + 1
                data = data[:len(data) - num]
            return data

        raw_ml = bytearray()
        for i in range(mh.records):
            self.sections[i + 1] = Text_Section(self.get_section_data(i + 1))
            raw_ml.extend(self.decoder.decode(trim(self.get_section_data(i + 1))))
        self.rawML = bytes(raw_ml)

    def _process_res(self) -> None:
        mh = self.mobi_header
        for i in range(mh.first_res_index, self.section_count):
            self.sections[i] = Section(self.get_section_data(i))
            t = self.sections[i].type
            if t == "FDST":
                self.sections[i] = FDST_Section(self.sections[i])
                self.fdst = self.sections[i]
            elif t == "RESC":
                self.sections[i] = RESC_Section(self.sections[i])
                self.resc = self.sections[i]
            elif t == "FONT":
                self.sections[i] = Font_Section(self.sections[i])
            else:
                r = util.guess_image_type(self.sections[i].raw)
                if r is not None:
                    self.sections[i] = Image_Section(self.sections[i], r)

    def _read_ctoc_dict(self, base_index: int, main_indx: INDX_Section_Main) -> dict:
        ctoc_dict = {}
        ctoc_off = 0
        for i in range(main_indx.header["ctoc_count"]):
            off = base_index + main_indx.header["any_count"] + 1 + i
            ctoc = CTOC_Section(self.get_section_data(off))
            self.sections[off] = ctoc
            for key in ctoc.ctoc_data:
                ctoc_dict[key + ctoc_off] = ctoc.ctoc_data[key]
            ctoc_off += 0x10000
        return ctoc_dict

    def _process_index(self) -> None:
        mh = self.mobi_header

        if mh.skel_index != 0xFFFFFFFF:
            self.skeleton_table = []
            main_indx = INDX_Section_Main(self.get_section_data(mh.skel_index), "INDX(Skeleton)")
            self.sections[mh.skel_index] = main_indx
            main_indx.read_tag()
            for i in range(main_indx.header["any_count"]):
                ext_indx = INDX_Section_Extra(
                    self.get_section_data(mh.skel_index + i + 1), main_indx)
                ext_indx.read_tag_map()
                self.sections[mh.skel_index + i + 1] = ext_indx
                for j in range(len(ext_indx.texts)):
                    values = ext_indx.tagmaps[j][1]
                    self.skeleton_table.append(
                        Skeleton_item(ext_indx.texts[j], values[0], values[2], values[3]))

        if mh.frag_index != 0xFFFFFFFF:
            self.frag_table = []
            main_indx = INDX_Section_Main(self.get_section_data(mh.frag_index), "INDX(Fragment)")
            self.sections[mh.frag_index] = main_indx
            main_indx.read_tag()
            ctoc_dict = self._read_ctoc_dict(mh.frag_index, main_indx)
            for i in range(main_indx.header["any_count"]):
                ext_indx = INDX_Section_Extra(
                    self.get_section_data(mh.frag_index + i + 1), main_indx)
                self.sections[mh.frag_index + i + 1] = ext_indx
                ext_indx.read_tag_map()
                for j in range(len(ext_indx.texts)):
                    values = ext_indx.tagmaps[j][2]
                    self.frag_table.append(Fragment_item(
                        ext_indx.texts[j], ctoc_dict[values[0]],
                        values[1], values[2], values[3], values[4]))

        if mh.guide_index != 0xFFFFFFFF:
            self.guide_table = []
            main_indx = INDX_Section_Main(self.get_section_data(mh.guide_index), "INDX(Guide)")
            self.sections[mh.guide_index] = main_indx
            main_indx.read_tag()
            ctoc_dict = self._read_ctoc_dict(mh.guide_index, main_indx)
            for i in range(main_indx.header["any_count"]):
                ext_indx = INDX_Section_Extra(
                    self.get_section_data(mh.guide_index + i + 1), main_indx)
                self.sections[mh.guide_index + i + 1] = ext_indx
                ext_indx.read_tag_map()
                for j in range(len(ext_indx.texts)):
                    values = ext_indx.tagmaps[j][1]
                    self.guide_table.append(Guide_item(
                        ext_indx.texts[j], ctoc_dict[values[0]], values[1]))

        if mh.ncx_index != 0xFFFFFFFF:
            self.index_info_table = []
            main_indx = INDX_Section_Main(self.get_section_data(mh.ncx_index), "INDX(NCX)")
            self.sections[mh.ncx_index] = main_indx
            main_indx.read_tag()
            ctoc_dict = self._read_ctoc_dict(mh.ncx_index, main_indx)
            for i in range(main_indx.header["any_count"]):
                ext_indx = INDX_Section_Extra(
                    self.get_section_data(mh.ncx_index + i + 1), main_indx)
                self.sections[mh.ncx_index + i + 1] = ext_indx
                ext_indx.read_tag_map()
                for j in range(len(ext_indx.tagmaps)):
                    item = IndexInfo_item()
                    item.name = ext_indx.texts[j]
                    for a in ext_indx.tagmaps[j].values():
                        item.position = a[0]
                        item.length = a[1]
                        item.title = ctoc_dict[a[2]]
                        item.level = a[3]
                        if item.level > 0:
                            n = len(a)
                            if n == 7:
                                item.parent = a[4]
                                item.fid = a[5]
                                item.off = a[6]
                            elif n == 9:
                                item.parent = a[4]
                                item.children_start = a[5]
                                item.children_end = a[6]
                                item.fid = a[7]
                                item.off = a[8]
                            elif n == 8:
                                item.parent = a[5]
                                item.fid = a[6]
                                item.off = a[7]
                            else:
                                raise UnpackKindleSException("Unhandled Error at INDX")
                        else:
                            n = len(a)
                            if n == 6:
                                item.fid = a[4]
                                item.off = a[5]
                            elif n == 7:
                                item.fid = a[5]
                                item.off = a[6]
                            elif n == 8:
                                item.children_start = a[4]
                                item.children_end = a[5]
                                item.fid = a[6]
                                item.off = a[7]
                            elif n == 9:
                                item.children_start = a[5]
                                item.children_end = a[6]
                                item.fid = a[7]
                                item.off = a[8]
                            else:
                                raise UnpackKindleSException("Unhandled Error at INDX")
                        break
                    self.index_info_table.append(item)

    def _build_parts(self) -> None:
        if self.fdst is None:
            lens = [0]
            texts = self.rawML
            log.log("[Warn]Cannot find FDST Section.")
        else:
            table = self.fdst.table
            lens = [0] * len(table)
            for i in range(len(lens) - 1):
                lens[i] = table[i + 1] - table[i]
            lens[len(table) - 1] = len(self.rawML) - table[len(table) - 1]
            texts = self.rawML[table[0]:table[0] + lens[0]]

        frag_index = 0
        for ske in self.skeleton_table:
            pos = ske.start_pos + ske.length
            part = bytearray(texts[ske.start_pos:ske.start_pos + ske.length])
            for _i in range(ske.record_count):
                frag = self.frag_table[frag_index]
                middle = texts[pos:pos + frag.length]
                frag.pos_in_raw = pos
                frag.xhtml = len(self.xhtmls)
                pos += frag.length
                insert_at = frag.file_postion - ske.start_pos
                part[insert_at:insert_at] = middle
                frag_index += 1
            self.xhtmls.append(bytes(part).decode("utf-8"))

        if self.fdst is not None:
            table = self.fdst.table
            for i in range(1, len(lens)):
                self.flows.append(
                    self.rawML[table[i]:table[i] + lens[i]].decode("utf-8"))
