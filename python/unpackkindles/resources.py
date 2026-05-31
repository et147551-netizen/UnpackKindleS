"""Access to bundled data files (templates + entity DTD).

Replaces the C# CWD-relative `File.ReadAllText("template\\...")` /
`File.ReadAllBytes("Xhtml-Entity-Set.dtd")` with packaged resources so the
tool works regardless of the working directory and when installed as a wheel.
"""

from __future__ import annotations

try:
    from importlib.resources import files as _files
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    from importlib_resources import files as _files


def load_template(name: str) -> str:
    """Read a template file. utf-8-sig drops the BOM, matching C# File.ReadAllText."""
    path = _files("unpackkindles") / "data" / "templates" / name
    return path.read_text(encoding="utf-8-sig")


def dtd_bytes() -> bytes:
    path = _files("unpackkindles") / "data" / "Xhtml-Entity-Set.dtd"
    return path.read_bytes()
