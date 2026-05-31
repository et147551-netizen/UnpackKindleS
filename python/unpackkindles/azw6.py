"""AZW6 (.azw.res) HD resource container parser. Ported from Azw6File.cs."""

from __future__ import annotations

import re
from typing import List

from . import util
from .errors import UnpackKindleSException
from .palmdb import AzwFile
from .headers import Azw6Header
from .sections import Section


class Azw6File(AzwFile):
    def __init__(self, path: str):
        super().__init__(path)
        self.header = None
        self.hrefs_sec = None
        self.image_sections: List[int] = []
        if self.section_count > 0:
            self.sections = [None] * self.section_count
            if self.ident == "RBINCONT":
                self.header = Azw6Header(self.get_section_data(0))
                self.sections[0] = self.header
                self._process_res()
                if len(self.image_sections) != len(self.hrefs):
                    raise UnpackKindleSException(
                        "HD Container herf and section 数量不一致")

    @property
    def title(self) -> str:
        return self.header.title

    @property
    def hrefs(self) -> List[str]:
        return self.hrefs_sec.hrefs

    def _process_res(self) -> None:
        for i in range(self.section_count):
            self.sections[i] = Section(self.get_section_data(i))
            t = self.sections[i].type
            if t == "kind":
                self.hrefs_sec = HREF_Section(self.sections[i].raw)
                self.sections[i] = self.hrefs_sec
            elif t == "CRES":
                self.sections[i] = CRES_Section(self.sections[i])
                self.image_sections.append(i)
            else:
                if util.get_uint32(self.sections[i].raw, 0) == 0xA0A0A0A0:
                    self.sections[i] = PlaceHolder_Section(self.sections[i])


class HREF_Section(Section):
    _regex = re.compile(r"kindle:embed:(.*?)\?mime=image/(.*)")

    def __init__(self, raw: bytes):
        base = Section(raw)
        Section._copy_init(self, base)
        self.type = "href of Images"
        self.raw = raw
        _hrefs = raw.decode("utf-8").split("|")
        self.hrefs: List[str] = []
        for s in _hrefs:
            m = self._regex.match(s)
            if m:
                self.hrefs.append(m.group(0))


class CRES_Section(Section):
    def __init__(self, s: Section):
        Section._copy_init(self, s)
        self.img = self.raw[12:]
        self.ext = util.guess_image_type(self.img)


class PlaceHolder_Section(Section):
    def __init__(self, s: Section):
        Section._copy_init(self, s)
