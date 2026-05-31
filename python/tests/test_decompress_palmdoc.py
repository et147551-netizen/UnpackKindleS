from unpackkindles.decompress import PalmdocDecoder


def d(data):
    return PalmdocDecoder().decode(data)


def test_single_byte_literals():
    assert d(b"\x41\x42") == b"AB"


def test_literal_run():
    # 0x02 -> copy next 2 bytes verbatim.
    assert d(b"\x02\x41\x42") == b"AB"
    assert d(b"\x08abcdefgh") == b"abcdefgh"


def test_space_plus_char():
    # c >= 192 -> emit space then (c ^ 0x80).
    assert d(b"\xc1") == b" A"  # 0xC1 ^ 0x80 == 0x41 == 'A'


def test_back_reference_non_overlapping():
    # 8-byte context, then \x80\x40 copies 8 back for 3 bytes -> "abc".
    assert d(b"\x08abcdefgh\x80\x40") == b"abcdefghabc"


def test_back_reference_overlapping_run():
    # context "ab", then \x80\x08 -> m=1, n=3: repeat last byte 3 times.
    assert d(b"\x61\x62\x80\x08") == b"abbbb"
