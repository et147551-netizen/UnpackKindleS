# UnpackKindleS — Python port (.NET-independent)

A complete port of [UnpackKindleS](https://github.com/Aeroblast/UnpackKindleS)
from C# / .NET 5 to **pure Python**, so it runs on **Windows and Linux** (and
macOS) without any .NET runtime.

It converts DRM-free Kindle `.azw3` files into EPUB, merging the high-resolution
images found in the companion `.azw.res` (`Azw6`) file.

## Requirements

- Python 3.9+
- [lxml](https://lxml.de/) — XHTML/OPF/NCX parsing with the XHTML entity DTD
- [Pillow](https://python-pillow.org/) — cover image dimensions (replaces `System.Drawing`)

```bash
pip install -r requirements.txt
# or install the package (provides the `unpackkindles` command):
pip install .
```

## Usage

```bash
# as an installed command
unpackkindles <xxx_nodrm.azw3 | xxx.azw.res | directory> [output_dir] [switches]

# or without installing
python -m unpackkindles <input> [output_dir] [switches]
```

Switches (same as the original):

| Switch | Meaning |
| --- | --- |
| `-dedrm` | Run DRM removal first (`dedrm.bat` on Windows, `dedrm.sh` elsewhere) |
| `-batch` | Batch-process `EBOK` folders under the given directory |
| `--just-dump-res` | Only extract HD images from a `.azw.res` file |
| `--rename-xhtml-with-id` | Name XHTML files after their spine ids |
| `--rename-when-exist` | Auto-rename output if it already exists |
| `--overwrite` | Overwrite existing output without prompting |
| `--append-log` | Append to `lastrun.log` instead of overwriting |

> DeDRM itself is **out of scope** — the tool only shells out to a `dedrm`
> script you provide. See `dedrm.sh.example`.

## Module map (C# → Python)

| C# file | Python module |
| --- | --- |
| `Program.cs` | `unpackkindles/cli.py` |
| `Azw3File.cs` | `unpackkindles/azw3.py` |
| `Azw6File.cs` | `unpackkindles/azw6.py` |
| `Headers.cs` | `unpackkindles/headers.py` |
| `Decompress.cs` | `unpackkindles/decompress.py` |
| `ProcessSection.cs` | `unpackkindles/sections.py` |
| `Structs&Dictionary.cs` | `unpackkindles/palmdb.py` + `models.py` + `idmapping.py` |
| `utils.cs` | `unpackkindles/util.py` |
| `EpubBuilder.cs` | `unpackkindles/epub.py` |
| `Log.cs` | `unpackkindles/log.py` |
| `version.cs` | `unpackkindles/version.py` |
| `template/`, `Xhtml-Entity-Set.dtd` | `unpackkindles/data/` (loaded via `importlib.resources`) |

## Testing

```bash
python -m pytest tests/ -q
```

Tier 1 unit tests (synthetic vectors) need no Kindle files. The end-to-end
round-trip test is skipped unless you point it at a DRM-free sample:

```bash
UKS_SAMPLE_AZW3=/path/to/book_nodrm.azw3 \
UKS_SAMPLE_AZW6=/path/to/book.azw.res \
python -m pytest tests/test_roundtrip.py -q
```
