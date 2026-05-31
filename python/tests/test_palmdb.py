import struct

from unpackkindles.palmdb import AzwFile


def _build_palmdb(sections):
    """Build a minimal PalmDB-style file from a list of section byte strings."""
    count = len(sections)
    header = bytearray(78)
    header[0x3C:0x44] = b"BOOKMOBI"
    struct.pack_into(">H", header, 76, count)
    records_size = count * 8
    data_start = 78 + records_size
    records = bytearray()
    pos = data_start
    for sec in sections:
        records += struct.pack(">I", pos) + b"\x00\x00\x00\x00"
        pos += len(sec)
    return bytes(header) + bytes(records) + b"".join(sections)


def test_section_boundaries(tmp_path):
    secs = [b"AAAA", b"BBBBBB", b"C"]
    f = tmp_path / "test.bin"
    f.write_bytes(_build_palmdb(secs))

    azw = AzwFile(str(f))
    assert azw.ident == "BOOKMOBI"
    assert azw.section_count == 3
    assert azw.get_section_data(0) == b"AAAA"
    assert azw.get_section_data(1) == b"BBBBBB"
    assert azw.get_section_data(2) == b"C"
    assert azw.section_info[0].length == 4
    assert azw.section_info[2].end_addr == len(f.read_bytes())
