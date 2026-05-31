from unpackkindles import util


def test_big_endian_readers():
    b = bytes([0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07])
    assert util.get_uint16(b, 0) == 0x0001
    assert util.get_uint32(b, 0) == 0x00010203
    assert util.get_uint64(b, 0) == 0x0001020304050607
    assert util.get_uint8(b, 5) == 0x05


def test_to_hex_string_uppercase():
    assert util.to_hex_string(bytes([0xDE, 0xAD, 0xBE, 0xEF]), 0, 4) == "DEADBEEF"
    assert util.to_hex_string(bytes([0x0A, 0xFF]), 1, 1) == "FF"


def test_decode_base32():
    assert util.decode_base32("0") == 0
    assert util.decode_base32("A") == 10
    assert util.decode_base32("V") == 31
    assert util.decode_base32("10") == 32
    assert util.decode_base32("1A") == 42


def test_number_padding():
    assert util.number(5) == "0005"
    assert util.number(123, 3) == "123"
    assert util.number(12345, 3) == "12345"


def test_filename_check():
    assert util.filename_check('a/b:c*?"|<>\\d') == "a／b：c＊？＂｜＜＞＼d"


def test_guess_image_type():
    assert util.guess_image_type(b"\xff\xd8\xff\xe0extra") == ".jpg"
    assert util.guess_image_type(b"GIF89a") == ".gif"
    assert util.guess_image_type(b"\x89PNG\r\n") == ".png"
    assert util.guess_image_type(b"abc") is None
    assert util.guess_image_type(b"abcd") is None


def test_ascii_str_replaces_high_bytes():
    assert util.ascii_str(bytes([0x41, 0x42, 0x80, 0xFF])) == "AB??"


def test_get_struct_be_reversed_semantics():
    # Two uint32 fields; the C# whole-block reversal reads fields in reverse byte order.
    data = bytes([0, 0, 0, 1, 0, 0, 0, 2])
    fields = [("a", 4, False), ("b", 4, False)]
    r = util.get_struct_be(data, 0, fields)
    assert r["a"] == 2
    assert r["b"] == 1


def test_get_struct_be_byte_array_field():
    # Layout: u16 count, byte[4] magic. size = 6.
    # bytes: 00 05 | M A G C  -> reversed: C G A M | 05 00
    data = bytes([0x00, 0x05, ord("M"), ord("A"), ord("G"), ord("C")])
    fields = [("count", 2, False), ("magic", 4, True)]
    r = util.get_struct_be(data, 0, fields)
    # reversed block = [C, G, A, M, 05, 00]; count read first (LE of [C,G]).
    assert r["count"] == (ord("G") << 8) | ord("C")
    assert r["magic"] == bytes([ord("A"), ord("M"), 0x05, 0x00])


def test_get_outer_xml():
    s = 'prefix<spine a="1"><itemref/></spine>suffix'
    assert util.get_outer_xml(s, "spine") == '<spine a="1"><itemref/></spine>'
    assert util.get_outer_xml(s, "metadata") is None
