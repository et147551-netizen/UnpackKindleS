from lxml import etree

from unpackkindles import epub


def test_esc_text_and_attr():
    assert epub._esc_text('a&b<c>d') == "a&amp;b&lt;c&gt;d"
    assert epub._esc_attr('x"&y') == "x&quot;&amp;y"


def test_el_self_closing_and_text():
    assert epub._el("meta", [("name", "k"), ("content", "v")]) == \
        '<meta name="k" content="v" />'
    assert epub._el("dc:title", [("id", "title")], "Hello & <Bye>") == \
        '<dc:title id="title">Hello &amp; &lt;Bye&gt;</dc:title>'


def test_local_and_find_all_local():
    root = etree.fromstring(
        '<h xmlns="urn:x"><svg/><a><svg/></a></h>')
    assert epub._local(root.tag) == "h"
    assert len(epub._find_all_local(root, "svg")) == 2


def test_dtd_entity_resolution():
    parser = epub._make_xhtml_parser()
    doc = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
        '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">\n'
        "<html><body>&copy;&nbsp;&mdash;</body></html>"
    )
    root = etree.fromstring(doc.encode("utf-8"), parser)
    text = root.find("body").text
    assert "©" in text   # &copy;
    assert " " in text   # &nbsp;
    assert "—" in text   # &mdash;
