"""EPUB builder. Ported from EpubBuilder.cs.

Uses lxml (with a custom resolver returning the bundled XHTML entity DTD) in
place of System.Xml, and the stdlib zipfile module in place of
System.IO.Compression.
"""

from __future__ import annotations

import datetime
import os
import re
import uuid
import zipfile
from typing import List, Optional

from lxml import etree

from . import util
from . import log
from . import idmapping
from . import resources
from .version import VERSION
from .errors import UnpackKindleSException

_XHTML11_DOCTYPE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
    '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
)

_CONTAINER = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
    '    <rootfiles><rootfile full-path="OEBPS/content.opf" '
    'media-type="application/oebps-package+xml"/>    </rootfiles></container>'
)


# --- XML string helpers (used to build the OPF metadata/manifest exactly like
#     the C# XmlDocument.OuterXml / InnerXml output) -------------------------

def _esc_text(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    return _esc_text(s).replace('"', "&quot;")


def _el(name: str, attrs=None, text: Optional[str] = None) -> str:
    """Build an element string. Empty -> self-closing (like XmlElement.OuterXml)."""
    a = ""
    if attrs:
        for k, v in attrs:
            a += ' {0}="{1}"'.format(k, _esc_attr(v))
    if text is None or text == "":
        return "<{0}{1} />".format(name, a)
    return "<{0}{1}>{2}</{0}>".format(name, a, _esc_text(text))


def _local(tag) -> Optional[str]:
    if not isinstance(tag, str):
        return None
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_all_local(root, name: str) -> list:
    return [e for e in root.iter() if _local(e.tag) == name]


def _ns_of(el) -> Optional[str]:
    tag = el.tag
    if isinstance(tag, str) and tag.startswith("{"):
        return tag[1:tag.index("}")]
    return None


# --- lxml parser with the bundled entity DTD resolver ----------------------

class _EntityResolver(etree.Resolver):
    def __init__(self, dtd: bytes):
        self._dtd = dtd

    def resolve(self, url, id, context):  # noqa: A002 - lxml signature
        return self.resolve_string(self._dtd, context)


def _make_xhtml_parser() -> etree.XMLParser:
    parser = etree.XMLParser(load_dtd=True, resolve_entities=True, no_network=True)
    parser.resolvers.add(_EntityResolver(resources.dtd_bytes()))
    return parser


class _IndexNode:
    def __init__(self, href, title):
        self.href = href
        self.title = title
        self.children = None
        self.parent = None


class Epub:
    def __init__(self, azw3, azw6, rename_xhtml_with_id: bool):
        self.azw3 = azw3
        self.azw6 = azw6
        self.rename_xhtml_with_id = rename_xhtml_with_id

        self.xhtmls = []            # list of lxml root elements
        self.xhtml_names: List[str] = []
        self.csss: List[str] = []
        self.css_names: List[str] = []
        self.imgs: List[bytes] = []
        self.img_names: List[str] = []
        self.font_names: List[str] = []
        self.fonts: List[bytes] = []
        self.cover_name: Optional[str] = None
        self.opf = None
        self.ncx = None
        self.nav = None
        self.extra_cover_doc_added = False
        self._play_order = 1
        self._parser = _make_xhtml_parser()

        azw3.flow_process_log = [None] * len(azw3.flows)
        for i in range(len(azw3.xhtmls)):
            self.xhtml_names.append("part" + util.number(i) + ".xhtml")

        if self.rename_xhtml_with_id:
            log.log("[Info]Rename xhtmls with id.")
            i = 0
            offset = 0
            if self._need_create_cover_document():
                i = 1
                offset = -1
            itemrefs = _find_all_local(azw3.resc.spine, "itemref")
            while (i + offset < len(self.xhtml_names)) and (i < len(itemrefs)):
                idref = itemrefs[i].get("idref")
                self.xhtml_names[i + offset] = idref + ".xhtml"
                i += 1

        for xhtml in azw3.xhtmls:
            doc = self._load_xhtml(xhtml)
            self.xhtmls.append(doc)
            self._proc_nodes(doc)

        self._set_cover()

        try:
            self._create_index_doc()
        except Exception as e:  # noqa: BLE001 - mirror C# release-mode behaviour
            log.log("[Error]Cannot Create NCX or NAV.")
            log.log("[Error]" + repr(e))

        meta = azw3.mobi_header.ext_meta
        if 202 in meta.id_value:
            thumb_offset = meta.id_value[202]
            azw3.sections[azw3.mobi_header.first_res_index + thumb_offset].comment = \
                "Thumb Cover, Ignored"

        for a in list(azw3.sections):
            if a.type == "Image" and not a.comment:
                i = azw3.sections.index(a) - azw3.mobi_header.first_res_index
                name = self._add_image(i, "Not referred")
                log.log("[Warn] {0} is not referred.".format(name))

        self._create_opf()

    # ------------------------------------------------------------------ save
    def save(self, path: str) -> None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            # mimetype must be first and stored uncompressed.
            zi = zipfile.ZipInfo("mimetype")
            zi.compress_type = zipfile.ZIP_STORED
            zf.writestr(zi, "application/epub+zip")

            zf.writestr("META-INF/container.xml", _CONTAINER)
            for i in range(len(self.xhtml_names)):
                p = "OEBPS/Text/" + self.xhtml_names[i]
                s = etree.tostring(self.xhtmls[i], encoding="unicode")
                ss = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n'
                      + s[s.index("<html"):])
                zf.writestr(p, ss)
            for i in range(len(self.css_names)):
                zf.writestr("OEBPS/Styles/" + self.css_names[i], self.csss[i])
            for i in range(len(self.img_names)):
                zf.writestr("OEBPS/Images/" + self.img_names[i], self.imgs[i])
            for i in range(len(self.font_names)):
                zf.writestr("OEBPS/Fonts/" + self.font_names[i], self.fonts[i])
            # If index creation failed, ncx/nav stay None; C# writes an empty
            # file in that case (StreamWriter.Write(null) -> ""), so mirror that.
            zf.writestr("OEBPS/toc.ncx", self.ncx or "")
            zf.writestr("OEBPS/nav.xhtml", self.nav or "")
            zf.writestr("OEBPS/content.opf", self.opf or "")
        log.log("Saved: " + path)

    # ------------------------------------------------------------ xhtml load
    def _load_xhtml(self, xhtml: str):
        htmlstart = xhtml.lower().find("<html")
        xhtml = _XHTML11_DOCTYPE + xhtml[htmlstart:]
        return etree.fromstring(xhtml.encode("utf-8"), self._parser)

    # --------------------------------------------------------- node walking
    def _proc_nodes(self, node) -> None:
        tag = node.tag
        if isinstance(tag, str):
            # Remove kindle-specific attributes.
            for dead in ("aid", "amzn-src-id"):
                if dead in node.attrib:
                    del node.attrib[dead]
            for name in list(node.attrib.keys()):
                value = node.attrib[name]
                if value.find("kindle:") == 0:
                    h = value[len("kindle:"):len("kindle:") + 4]
                    if h == "pos:":
                        self._proc_link(node, name)
                    elif h == "flow":
                        self._proc_text_ref(node, name)
                    elif h == "embe":
                        node.set(name, self._proc_embed(value))
                if _local_attr(name) == "style":
                    node.set(name, self._proc_css(node.attrib[name]))
            if _local(tag) == "style":
                node.text = self._proc_css(node.text or "")

        for child in list(node):
            self._proc_nodes(child)

    def _proc_text_ref(self, el, attr_name: str) -> None:
        value = el.get(attr_name)
        m = re.search(r"kindle:flow:([0-9|A-V]+)\?mime=.*?/(.*)", value)
        if not m:
            log.log("[Error]link unsolved")
            return
        flowid = util.decode_base32(m.group(1))
        mime = m.group(2)
        if flowid < 0:
            el.set(attr_name, "flow" + str(10000 + flowid))
            log.log("[Warn]placeholder link: " + m.group(0))
            return
        if mime == "css":
            name = "flow" + util.number(flowid) + ".css"
            if name not in self.css_names:
                csstext = self.azw3.flows[flowid - 1]
                csstext = self._proc_css(csstext)
                self.csss.append(csstext)
                self.css_names.append(name)
                self.azw3.flow_process_log[flowid - 1] = name
            el.set(attr_name, "../Styles/" + name)
        elif mime == "svg+xml":
            self._proc_svg_flow(el, flowid)

    def _proc_svg_flow(self, el, flowid: int) -> None:
        text = self.azw3.flows[flowid - 1]
        parent = el.getparent()
        fragment = etree.fromstring("<temp>" + text + "</temp>", self._parser)
        # Element children: move <svg> into place; PI children: handle stylesheet.
        for n in list(fragment):
            if _local(n.tag) == "svg":
                if parent is not None:
                    el.addprevious(n)
                    parent.remove(el)
                self._proc_nodes(n)
        for n in fragment.xpath("//processing-instruction('xml-stylesheet')"):
            ml = re.search(r'kindle:flow:([0-9|A-V]+)\?mime=.*?/(.*?)"', n.text or "")
            if ml and ml.group(2) == "css":
                flowid_ = util.decode_base32(ml.group(1))
                name_ = "flow" + util.number(flowid_) + ".css"
                root = el.getroottree().getroot()
                already = any(
                    link.get("href") == "../Styles/" + name_
                    for link in _find_all_local(root, "link"))
                if not already:
                    heads = _find_all_local(root, "head")
                    if heads:
                        link = etree.SubElement(heads[0], _qualify(heads[0], "link"))
                        link.set("href", "../Styles/" + name_)
                        link.set("type", "text/css")
                        link.set("rel", "stylesheet")
                    if name_ not in self.css_names:
                        csstext = self.azw3.flows[flowid_ - 1]
                        csstext = self._proc_css(csstext)
                        self.csss.append(csstext)
                        self.css_names.append(name_)
                        self.azw3.flow_process_log[flowid_ - 1] = name_
            else:
                log.log("cannot find css link in xml-stylesheet")
        self.azw3.flow_process_log[flowid - 1] = \
            "Flow" + util.number(flowid) + " svg has been put into xhtmls"

    def _proc_link(self, el, attr_name: str) -> None:
        value = el.get(attr_name)
        m = re.search(r"kindle:pos:fid:([0-9|A-V]+):off:([0-9|A-V]+)", value)
        if not m:
            log.log("[Error]link unsolved")
            return
        fid = util.decode_base32(m.group(1))
        off = util.decode_base32(m.group(2))
        el.set(attr_name, self._kindle_pos_to_uri(fid, off))

    def _kindle_pos_to_uri(self, fid: int, off: int) -> str:
        extra = 1 if self.extra_cover_doc_added else 0
        frag = self.azw3.frag_table[fid]
        t = self.azw3.rawML[frag.pos_in_raw + off:frag.pos_in_raw + frag.length]
        s = t.decode("utf-8", errors="replace")
        m = re.match(r'^<.*? id="(.*?)".*?>', s)
        if m:
            return self.xhtml_names[frag.xhtml + extra] + "#" + m.group(1)
        return self.xhtml_names[frag.xhtml + extra]

    def _proc_embed(self, uri: str) -> str:
        m = re.search(r"kindle:embed:([0-9|A-V]+)", uri)
        if not m:
            log.log("[Error]link unsolved: " + uri)
            return ""
        resid = util.decode_base32(m.group(1)) - 1
        if uri.find("?") > 1:
            mq = re.search(r"mime=(.*)/(.*)", uri)
            g1 = mq.group(1) if mq else ""
            if g1 == "image":
                name = self._add_image(resid)
                return "../Images/" + name
            raise NotImplementedError()
        section = self.azw3.sections[self.azw3.mobi_header.first_res_index + resid]
        if section.type == "FONT":
            name = "embed" + util.number(resid) + (section.ext or "")
            if section.ext is None:
                log.log("[Warn] The referred font file is unrecognized: " + name)
            if name not in self.font_names:
                section.comment = name
                self.fonts.append(section.data)
                self.font_names.append(name)
            return "../Fonts/" + name
        raise NotImplementedError()

    def _proc_css(self, text: str) -> str:
        r = text
        for m in re.finditer(
                r"url\(kindle:flow:([0-9|A-V]+)\?mime=text/css\)", text):
            flowid = util.decode_base32(m.group(1))
            name = "flow" + util.number(flowid) + ".css"
            if name not in self.css_names:
                csstext = self.azw3.flows[flowid - 1]
                csstext = self._proc_css(csstext)
                self.csss.append(csstext)
                self.css_names.append(name)
                self.azw3.flow_process_log[flowid - 1] = name
            r = r.replace(m.group(0), "url(" + name + ")")
        for m in re.finditer(r"url\((kindle:embed:.+?)\)", text):
            r = r.replace(m.group(1), self._proc_embed(m.group(1)))
        return r

    # --------------------------------------------------------------- index
    def _create_index_doc_helper(self, node, e3, e2, level: int = 0) -> None:
        tabs = "\t" * level
        e3.append("\n" + tabs + "<ol>\n")
        for n in node.children:
            e3.append(tabs + '<li><a href="{0}">{1}</a>'.format(
                _esc_attr(n.href or ""), _esc_text(n.title or "")))
            e2.append(tabs + '<navPoint id="navPoint-{0}" playOrder="{0}">\n'.format(
                self._play_order))
            e2.append(tabs + "\t<navLabel><text>{0}</text></navLabel>\n".format(
                _esc_text(n.title or "")))
            e2.append(tabs + '\t<content src="{0}" />\n'.format(_esc_attr(n.href or "")))
            self._play_order += 1
            if n.children is not None:
                self._create_index_doc_helper(n, e3, e2, level + 1)
            e3.append("</li>\n")
            e2.append(tabs + "</navPoint>\n")
        e3.append(tabs + "</ol>\n")

    def _create_index_doc(self) -> None:
        azw3 = self.azw3
        all_entries = []
        root = _IndexNode("", "")
        root.children = []
        max_level = 0
        if azw3.index_info_table is not None:
            for i in range(len(azw3.index_info_table)):
                info = azw3.index_info_table[i]
                entry = _IndexNode(
                    "Text/" + self._kindle_pos_to_uri(info.fid, info.off), info.title)
                all_entries.append(entry)
                if info.children_start != -1:
                    entry.children = []
                if info.level > 0:
                    entry.parent = all_entries[info.parent]
                    entry.parent.children.append(entry)
                    _item = azw3.index_info_table[info.parent]
                    if _item.children_start > i or _item.children_end < i:
                        raise UnpackKindleSException("Index Error")
                else:
                    root.children.append(entry)
                if info.level > max_level:
                    max_level = info.level
        e3 = []
        e2 = []
        self._create_index_doc_helper(root, e3, e2)

        # NAV
        t = resources.load_template("template_nav.txt")
        t = t.replace("{❕toc}", "".join(e3))
        guide = ""
        if azw3.guide_table is not None:
            for g in azw3.guide_table:
                try:
                    offset = 1 if self.extra_cover_doc_added else 0
                    i = azw3.frag_table[g.num].file_num + offset
                    guide += ('    <li><a epub:type="{2}" href="{1}">{0}</a></li>\n'
                              .format(_esc_text(g.ref_name or ""),
                                      _esc_attr("Text/" + self.xhtml_names[i]),
                                      g.ref_type))
                except Exception as e:  # noqa: BLE001
                    log.log("Error at Gen guide.")
                    log.log(repr(e))
        t = t.replace("{❕guide}", guide)
        t = t.replace("{❕cover}", "Text/" + self.xhtml_names[0])
        self.nav = t

        # NCX
        t = resources.load_template("template_ncx.txt")
        t = t.replace("{❕navMap}", "".join(e2))
        t = t.replace("{❕Title}", _esc_text(azw3.title))
        z = azw3.mobi_header.ext_meta.id_string.get(504) or str(uuid.uuid4())  # ASIN
        t = t.replace("{❕uid}", z)
        t = t.replace("{❕depth}", str(max_level + 1))
        self.ncx = t

    # --------------------------------------------------------------- cover
    def _set_cover(self) -> None:
        azw3 = self.azw3
        meta = azw3.mobi_header.ext_meta
        if 201 in meta.id_value:
            off = meta.id_value[201]  # CoverOffset
            if azw3.mobi_header.first_res_index + off < azw3.section_count:
                if azw3.sections[azw3.mobi_header.first_res_index + off].type == "Image":
                    self.cover_name = self._add_image(off, "Cover")
                    if self._need_create_cover_document():
                        log.log("[Info]Adding a cover document.")
                        t = resources.load_template("template_cover.txt")
                        w, h = util.get_image_size(self.imgs[self.img_names.index(self.cover_name)])
                        cover = (t.replace("{❕image}", self.cover_name)
                                 .replace("{❕w}", str(w))
                                 .replace("{❕h}", str(h)))
                        cover_document_name = "cover.xhtml"
                        if self.rename_xhtml_with_id:
                            idref = _find_all_local(azw3.resc.spine, "itemref")[0].get("idref")
                            cover_document_name = idref + ".xhtml"
                        self.xhtml_names.insert(0, cover_document_name)
                        cover_doc = etree.fromstring(cover.encode("utf-8"), self._parser)
                        self.xhtmls.insert(0, cover_doc)
                        self.extra_cover_doc_added = True
            return
        log.log("[Warn]No Cover!")

    def _need_create_cover_document(self) -> bool:
        itemrefs = _find_all_local(self.azw3.resc.spine, "itemref")
        if len(itemrefs) == len(self.xhtml_names):
            return False
        return True

    # ----------------------------------------------------------------- opf
    def _create_opf(self) -> None:
        azw3 = self.azw3
        meta = azw3.mobi_header.ext_meta
        if azw3.resc is None:
            raise UnpackKindleSException("no resc info!")

        t = resources.load_template("template_opf.txt")

        # ---- manifest ----
        items = []
        i = 0
        spine = azw3.resc.spine
        for itemref in [c for c in list(spine) if isinstance(c.tag, str)]:
            if "skelid" in itemref.attrib:
                del itemref.attrib["skelid"]
            idref = itemref.get("idref")
            attrs = [("href", "Text/" + self.xhtml_names[i]),
                     ("id", idref),
                     ("media-type", "application/xhtml+xml")]
            if self._contains_svg(self.xhtmls[i]):
                attrs.append(("properties", "svg"))
            items.append(_el("item", attrs))
            i += 1
        if i > len(self.xhtmls):
            log.log("[Warn] Missing Parts. Ignore if this is a book sample.")
        if i < len(self.xhtmls):
            log.log("[Warn]Not all xhtmls are refered in spine.")
            while i < len(self.xhtmls):
                attrs = [("href", "Text/" + self.xhtml_names[i]),
                         ("id", self.xhtml_names[i]),
                         ("media-type", "application/xhtml+xml")]
                if self._contains_svg(self.xhtmls[i]):
                    attrs.append(("properties", "svg"))
                items.append(_el("item", attrs))
                new_ref = etree.SubElement(spine, _qualify(spine, "itemref"))
                new_ref.set("idref", self.xhtml_names[i])
                new_ref.set("linear", "yes")
                log.log("[Warn]Added " + self.xhtml_names[i] + " to spine and item")
                i += 1

        for imgname in self.img_names:
            ext = os.path.splitext(imgname)[1].lower()[1:]
            if ext == "jpg":
                ext = "jpeg"
            attrs = [("href", "Images/" + imgname)]
            if imgname == self.cover_name:
                attrs.append(("properties", "cover-image"))
            attrs.append(("id", os.path.splitext(imgname)[0]))
            attrs.append(("media-type", "image/" + ext))
            items.append(_el("item", attrs))
        for cssname in self.css_names:
            items.append(_el("item", [
                ("href", "Styles/" + cssname),
                ("id", os.path.splitext(cssname)[0]),
                ("media-type", "text/css")]))
        for fontname in self.font_names:
            media_type = ""
            ext = os.path.splitext(fontname)[1]
            if ext == ".ttf":
                media_type = "font/ttf"
            elif ext == ".otf":
                media_type = "font/otf"
            items.append(_el("item", [
                ("href", "Fonts/" + fontname),
                ("id", os.path.splitext(fontname)[0]),
                ("media-type", media_type)]))
        items.append(_el("item", [("href", "toc.ncx"), ("id", "ncxuks"),
                                  ("media-type", "application/x-dtbncx+xml")]))
        items.append(_el("item", [("href", "nav.xhtml"), ("id", "navuks"),
                                  ("media-type", "application/xhtml+xml"),
                                  ("properties", "nav")]))
        manifest = ("<manifest>" + "".join(items) + "</manifest>").replace("><", ">\r\n<")
        t = t.replace("{❕manifest}", manifest)

        # ---- metadata ----
        m = []
        m.append(_el("dc:title", [("id", "title")], azw3.title))
        if 508 in meta.id_string:
            m.append(_el("meta", [("refines", "#title"), ("property", "file-as")],
                        meta.id_string[508]))
        m.append(_el("dc:language", text=meta.id_string.get(524, "ja")))
        m.append(_el("dc:identifier", [("id", "ASIN")],
                    meta.id_string.get(504) or str(uuid.uuid4())))
        m.append(_el("meta", [("property", "dcterms:modified")],
                    datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")))
        if 100 in meta.id_string:
            creatername = meta.id_string[100].split("&")
            sortname = meta.id_string[517].split("&") if 517 in meta.id_string else []
            for l in range(len(creatername)):
                m.append(_el("dc:creator", [("id", "creator" + str(l))], creatername[l]))
                if l < len(sortname):
                    m.append(_el("meta",
                                [("refines", "#creator" + str(l)), ("property", "file-as")],
                                sortname[l]))
        if 101 in meta.id_string:
            m.append(_el("dc:publisher", [("id", "publisher")], meta.id_string[101]))
            if 522 in meta.id_string:
                m.append(_el("meta", [("refines", "#publisher"), ("property", "file-as")],
                            meta.id_string[522]))
        if 106 in meta.id_string:
            m.append(_el("dc:date", text=meta.id_string[106]))
        if 122 in meta.id_string and meta.id_string[122] == "true":
            m.append(_el("meta", [("property", "rendition:layout")], "pre-paginated"))
            m.append(_el("meta", [("property", "rendition:orientation")], "auto"))
            m.append(_el("meta", [("property", "rendition:spread")], "landscape"))
        for nm_id, nm_name in [(525, "primary-writing-mode"), (123, "book-type"),
                               (124, "orientation-lock"), (126, "original-resolution")]:
            if nm_id in meta.id_string:
                m.append(_el("meta", [("name", nm_name), ("content", meta.id_string[nm_id])]))
        if len(self.fonts) > 0:
            m.append(_el("meta", [("name", "ibooks:specified-fonts"), ("content", "true")]))
        # EPUB2 legacy cover declaration: required by Google Play Books, Kobo and
        # most cloud readers that still locate the cover via this heuristic.
        if self.cover_name is not None:
            m.append(_el("meta", [("name", "cover"),
                                  ("content", os.path.splitext(self.cover_name)[0])]))

        othermeta = ""
        if 503 in meta.id_string:
            othermeta += '<meta name="{0}" content="{1}" />\n'.format(
                idmapping.id_map_strings[503], meta.id_string[503])
        t = t.replace("{❕othermeta}", othermeta)

        meta_inner = "".join("    " + e + "\n" for e in m)
        t = t.replace("{❕meta}", meta_inner)

        # ---- spine ----
        spine.set("toc", "ncxuks")
        if 527 in meta.id_string:
            spine.set("page-progression-direction", meta.id_string[527])
        spine_str = etree.tostring(spine, encoding="unicode")
        t = t.replace("{❕spine}", spine_str.replace("><", ">\n<"))

        # ---- guide (legacy cover reference for older readers) ----
        guide = ""
        if self.cover_name is not None:
            guide = ('<guide>\n  <reference type="cover" title="Cover" '
                     'href="Text/{0}" />\n</guide>').format(_esc_attr(self.xhtml_names[0]))
        t = t.replace("{❕guide}", guide)
        t = t.replace("{❕version}", VERSION)

        self.opf = t

    # --------------------------------------------------------------- images
    def _contains_svg(self, doc) -> bool:
        return len(_find_all_local(doc, "svg")) > 0

    @staticmethod
    def image_name(resid: int, section) -> str:
        return "embed" + util.number(resid) + section.ext

    @staticmethod
    def image_name_hd(resid: int, section) -> str:
        return "embed" + util.number(resid) + "_HD" + section.ext

    def _add_image(self, id_: int, message: str = "") -> str:
        azw3 = self.azw3
        name = None
        data = None
        to_comment = None
        if self.azw6 is not None:
            r = (id_ + 1) if (id_ + 1) in self.azw6.image_sections else 0
            if r != 0:
                sec = self.azw6.sections[r]
                name = self.image_name_hd(id_, sec)
                data = sec.img
                sec.comment = name
                to_comment = azw3.sections[azw3.mobi_header.first_res_index + id_]
        if name is None:
            section = azw3.sections[azw3.mobi_header.first_res_index + id_]
            name = self.image_name(id_, section)
            data = section.raw
            to_comment = section
        if name in self.img_names:
            return name
        self.imgs.append(data)
        self.img_names.append(name)
        to_comment.comment = name + " | " + message
        return name


def _local_attr(name: str) -> str:
    """Local name of an attribute key (lxml uses {ns}name for namespaced attrs)."""
    return name.split("}", 1)[1] if "}" in name else name


def _qualify(parent, name: str) -> str:
    ns = _ns_of(parent)
    return "{" + ns + "}" + name if ns else name
