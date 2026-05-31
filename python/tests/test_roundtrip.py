"""End-to-end round-trip test.

Skipped unless UKS_SAMPLE_AZW3 points to a DRM-free .azw3 file (optionally
UKS_SAMPLE_AZW6 for the matching .azw.res). This validates the full pipeline
and the structural correctness of the produced EPUB without shipping any
copyrighted sample in the repo.
"""

import os
import zipfile

import pytest
from lxml import etree

SAMPLE = os.environ.get("UKS_SAMPLE_AZW3")
SAMPLE6 = os.environ.get("UKS_SAMPLE_AZW6")

pytestmark = pytest.mark.skipif(
    not SAMPLE, reason="set UKS_SAMPLE_AZW3 to a DRM-free .azw3 to run")


def test_full_pipeline(tmp_path):
    from unpackkindles.azw3 import Azw3File
    from unpackkindles.azw6 import Azw6File
    from unpackkindles.epub import Epub

    azw3 = Azw3File(SAMPLE)
    azw6 = Azw6File(SAMPLE6) if SAMPLE6 else None
    epub = Epub(azw3, azw6, rename_xhtml_with_id=False)

    out = tmp_path / "out.epub"
    epub.save(str(out))

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        # OCF: mimetype first and stored uncompressed.
        assert names[0] == "mimetype"
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert zf.read("mimetype") == b"application/epub+zip"

        # content.opf parses and every manifest href exists in the archive.
        opf = etree.fromstring(zf.read("OEBPS/content.opf"))
        hrefs = [it.get("href") for it in opf.iter()
                 if etree.QName(it).localname == "item"]
        entryset = set(names)
        for h in hrefs:
            assert ("OEBPS/" + h) in entryset, h

        # every XHTML part parses as XML.
        for n in names:
            if n.startswith("OEBPS/Text/") and n.endswith(".xhtml"):
                etree.fromstring(zf.read(n))
