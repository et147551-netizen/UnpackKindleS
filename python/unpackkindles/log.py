"""Logging. Ported from Log.cs.

Keeps a module-level buffer of every line logged (CRLF terminated, matching the
C# original) and echoes to the console with ANSI colours for Warn/Error/Info.
"""

from __future__ import annotations

import sys

from .idmapping import id_map_strings, id_map_values, id_map_hex
from .util import number

# ANSI colour codes (cross-platform: modern Windows terminals understand these).
_YELLOW = "\033[93m"
_RED = "\033[91m"
_GREEN = "\033[92m"
_RESET = "\033[0m"

# Accumulated log text. Matches the static `t` field in Log.cs.
_buffer = ""
_level = ""


def log(s: str) -> None:
    """Log a single line: append to the buffer and print (coloured)."""
    global _buffer
    _buffer += s + "\r\n"
    colour = ""
    if s.startswith("[Warn"):
        colour = _YELLOW
    elif s.startswith("[Error"):
        colour = _RED
    elif s.startswith("[Info"):
        colour = _GREEN
    if colour:
        print(colour + s + _RESET)
    else:
        print(s)
    sys.stdout.flush()


def log_tab(s: str) -> None:
    log(_level + s)


def log_azw3(azw3) -> None:
    """Dump an overview of an Azw3File. Ported from Log.log(Azw3File)."""
    global _level
    log("|Azw3 Over View")
    log("|[" + azw3.author + "]" + azw3.title)
    log("|Meta:")
    _level = "| |"
    meta = azw3.mobi_header.ext_meta
    for k, v in meta.id_string.items():
        log_tab(id_map_strings[k] + " " + str(v))
    for k, v in meta.id_value.items():
        log_tab(id_map_values[k] + " " + str(v))
    for k, v in meta.id_hex.items():
        log_tab(id_map_hex[k] + " " + str(v))
    log("|Sections:")
    _level = "| |"
    i = 0
    log_tab("Section|   bytes  |type|comment")
    for a in azw3.sections:
        log_tab("    {0}|{1}|{2}|{3}".format(
            number(i, 3), number(a.get_size(), 10), a.type, a.comment))
        i += 1
    log("|Flows (flow0 is xhtmls)")
    i = 1
    for a in azw3.flow_process_log:
        log_tab(number(i, 3) + ":" + (a if a is not None else ""))
        i += 1


def save(path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(_buffer)


def append(path: str) -> None:
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write("\r\n\r\n" + _buffer)
