from unpackkindles.sections import CTOC_Section, RESC_Section, Section


def test_ctoc_variable_width_and_names():
    # 0x82 -> varwidth value 2 (len of "hi"), then "hi"; 0x00 terminates.
    data = b"\x82hi\x00"
    ctoc = CTOC_Section(data)
    assert ctoc.type == "CTOC"
    assert ctoc.ctoc_data == {0: "hi"}


def test_ctoc_multibyte_varwidth():
    # value 130 -> two bytes: 0x01 0x82  ((1<<7)|2 == 130)
    name = b"x" * 130
    data = b"\x01\x82" + name + b"\x00"
    ctoc = CTOC_Section(data)
    assert ctoc.ctoc_data[0] == "x" * 130


def test_resc_parses_spine_and_metadata():
    payload = (b"RESC\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
               b'<x><metadata><dc>t</dc></metadata>'
               b'<spine><itemref idref="a"/></spine></x>'
               + b"\x00\x00\x00")
    sec = RESC_Section(Section(payload))
    assert sec.spine is not None
    assert sec.metadata is not None
    itemrefs = [e for e in sec.spine.iter() if e.tag == "itemref"]
    assert itemrefs[0].get("idref") == "a"
