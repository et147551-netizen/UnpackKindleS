# UnpackKindleS — Claude Code Guide

## Project Overview

UnpackKindleS is a Windows-only C# (.NET 5) CLI tool that converts DRM-free Kindle azw3 files to EPUB format, optionally merging high-resolution images from paired azw.res files. It targets Japanese light novel readers using Kindle for PC on Windows.

---

## Build & Run

### Development (from source)

Run from the `src/` directory:

```
cd src
dotnet run -- <args>
```

The `template/` subdirectory must exist relative to the working directory. `Program.cs:21-22` auto-detects this: if `template/` is not found in cwd, the program switches cwd to the exe's directory.

### Release Build

Run `publish.bat` from the repo root (Windows only). It:

1. Runs `dotnet publish -c Release -r win10-x64` (single-file self-contained exe)
2. Moves output to `bin/app/`
3. Copies `src/template/*.txt` and `src/Xhtml-Entity-Set.dtd` to `bin/app/`
4. Copies batch scripts from `template_batch/` to `bin/`
5. Copies `Released/AZW3_PC_DeDRM.exe` to `bin/` — **this file is not in source control and must exist locally**

Clean build artifacts with `clear.bat`.

### No Test Suite

There are no automated tests. Test manually with real azw3/azw.res files and inspect the output EPUB and `lastrun.log`.

---

## Architecture

### Data Flow

```
azw3 file  →  Azw3File (parse)  →  Epub.Save()  →  .epub (zip archive)
azw.res file →  Azw6File (parse)  →  Epub (HD image merge, optional)
```

### Key Files

| File | Role |
|------|------|
| `Program.cs` | CLI entry; parses args; routes to `ProcBatch`/`ProcPath`/`DumpHDImage` |
| `Azw3File.cs` | KF8/MOBI8 parser; supports only version 8, UTF-8 (codepage 65001), unencrypted (crypto_type == 0) |
| `Azw6File.cs` | azw.res parser; container identifier "RBINCONT"; extracts CRES sections |
| `EpubBuilder.cs` | Builds EPUB 3 zip; resolves `kindle:pos/flow/embed` URIs; reads 4 template files |
| `ProcessSection.cs` | Section type hierarchy; type is determined by the first 4 ASCII bytes of each section |
| `Headers.cs` | MobiHeader and Azw6Header parsers; all integers are big-endian (`Util.GetUInt32/16/8`) |
| `Decompress.cs` | PalmDOC (compression type 2) and Huffman/CDIC (type 0x4448) decompressors |
| `Structs&Dictionary.cs` | Data structures and EXTH metadata ID map — **filename contains `&`, always quote in shell** |
| `utils.cs` | Big-endian readers; image type detection by magic bytes; filename sanitization (special chars → fullwidth Unicode) |
| `Log.cs` | Static logger; console colors by prefix: `[Warn]`=yellow, `[Error]`=red, `[Info]`=green; writes `lastrun.log` |
| `version.cs` | Single version string in YYYYMMDD format (e.g., `"20220126"`) |

### Template System

`EpubBuilder.cs` reads 4 files from `template/` at runtime (path relative to the exe, not cwd):

- `template_cover.txt` — cover XHTML document
- `template_nav.txt` — EPUB 3 nav.xhtml
- `template_ncx.txt` — EPUB 2 toc.ncx
- `template_opf.txt` — OPF package document

Substitution token format: `{❕keyword}` where `❕` is **U+2757** (heavy exclamation mark ornament). Do not confuse with ASCII `!` (U+0021).

---

## Domain Knowledge

### File Pairing

azw3 and azw.res must be in the same directory for automatic pairing. Kindle for PC stores each book under:
`%USERPROFILE%\Documents\My Kindle Content\B0XXXXXXXXX_EBOK\`

### Batch Mode (`-batch`)

Only processes subdirectories whose name contains `"EBOK"`. Non-EBOK directories are silently skipped.

### DRM Removal (`-dedrm`)

Delegates to `dedrm.bat` → `AZW3_PC_DeDRM.exe`. Compatible with Kindle for PC 1.19–1.29 only. The Kindle key is cached in `kindlekey.k4i`; delete it and retry if DRM removal fails.

### HD Image Merging

When azw.res is present, HD images from azw6 replace azw3 images matched by resource index (not filename). Falls back to the azw3 image when no HD version exists.

### Output Naming

Output is `[Author] Title.epub`. Special characters in title/author are replaced with fullwidth Unicode equivalents (e.g., `?` → `？`, `/` → `／`).

### Supported Kindle Format

MOBI version 8 and UTF-8 only. Any other version throws `UnpackKindleSException`. Pre-KF8 formats are not supported.

---

## Common Tasks

### Add a New Section Type

1. Add a new class extending `Section` in `ProcessSection.cs`
2. Add an instantiation case in `Azw3File.ProcessRes()` or `Azw6File.ProcessRes()`

### Modify EPUB Output Structure

Edit `EpubBuilder.cs`. `Epub.Save()` defines the zip structure. Template files in `src/template/` control OPF/NCX/NAV/cover documents.

### Debug a Parse Failure

Run with a single file and check `lastrun.log` (written one level above the exe). Look for `[Error]`/`[Warn]` lines. The log also prints a section-by-section table with type, size, and comment for every section in the azw3 file.

### Update the Version String

Edit `src/version.cs`. The format is `YYYYMMDD`.

---

## Constraints & Gotchas

- **Windows only**: Batch scripts use cmd syntax; csproj targets `win10-x64`; `System.Drawing.Common` has non-Windows limitations.
- **`template/` must exist**: A missing template directory causes `FileNotFoundException` at runtime.
- **`Structs&Dictionary.cs`**: The filename contains `&`. Always quote it in shell commands.
- **Interactive prompt on output collision**: Without `--overwrite` or `--rename-when-exist`, the tool pauses for user input if the output file already exists — this blocks unattended batch runs.
- **Log path**: `Log.Save("..\\lastrun.log")` writes one level above the exe. In development (`dotnet run` from `src/`), `lastrun.log` appears at the repo root.
- **Only MOBI version 8 is supported**: Older Kindle formats throw unconditionally; there is no fallback.
- **`Released/AZW3_PC_DeDRM.exe`** is not in source control; `publish.bat` will fail if it is absent.
