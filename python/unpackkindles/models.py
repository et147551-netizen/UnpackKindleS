"""Small record types used by the index tables. Ported from Structs&Dictionary.cs."""

from __future__ import annotations


class Skeleton_item:
    __slots__ = ("name", "record_count", "start_pos", "length")

    def __init__(self, name, record_count, start_pos, length):
        self.name = name
        self.record_count = record_count
        self.start_pos = start_pos
        self.length = length


class Fragment_item:
    __slots__ = ("file_postion", "name", "file_num", "squence_num",
                 "start_offset", "length", "pos_in_raw", "xhtml")

    def __init__(self, file_pos, name, file_num, sq_num, off, length):
        self.file_postion = int(file_pos)
        self.name = name
        self.file_num = file_num
        self.squence_num = sq_num
        self.start_offset = off
        self.length = length
        self.pos_in_raw = 0   # filled during BuildParts (reverse search)
        self.xhtml = 0        # filled during BuildParts (reverse search)


class Guide_item:
    __slots__ = ("ref_type", "ref_name", "num")

    def __init__(self, ref_type, ref_name, num):
        self.ref_type = ref_type
        self.ref_name = ref_name
        self.num = num


class IndexInfo_item:
    __slots__ = ("title", "name", "fid", "off", "position", "length",
                 "level", "parent", "children_start", "children_end")

    def __init__(self):
        self.title = None
        self.name = None
        self.fid = 0
        self.off = 0
        self.position = 0
        self.length = 0
        self.level = 0
        self.parent = -1
        self.children_start = -1
        self.children_end = -1
