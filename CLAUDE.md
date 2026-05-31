# CLAUDE.md — UnpackKindleS

This file describes the codebase structure, build workflow, and conventions for AI assistants working on this project.

---

## Project Overview

**UnpackKindleS** is a C# .NET 5 command-line tool that:

1. Parses Kindle AZW3 (KF8/MOBI v8) ebook files that have had DRM removed.
2. Optionally merges HD images from a companion `.azw.res` (AZW6/RBINCONT) resource file.
3. Outputs a standards-compliant EPUB 3 file.

Primary audience: Japanese light-novel readers using Kindle for PC 1.19–1.29, where books are stored in two parts (`.azw` + `.azw.res`) inside `B0XXXXXXXX_EBOK` folders.

---

## Repository Layout

```
UnpackKindleS/
├── src/
│   ├── UnpackKindleS.csproj     # .NET 5 project file
│   ├── Program.cs               # Entry point, CLI argument handling
│   ├── Azw3File.cs              # AZW3 (KF8) parser
│   ├── Azw6File.cs              # AZW.res (HD resource container) parser
│   ├── EpubBuilder.cs           # EPUB assembler
│   ├── ProcessSection.cs        # Binary section types (INDX, FDST, RESC, Font, …)
│   ├── Decompress.cs            # PalmDOC and Huffman/CDIC decompressors
│   ├── Headers.cs               # MobiHeader, Azw6Header, ExtMeta parsers
│   ├── Structs&Dictionary.cs    # Shared structs, AzwFile base class, ID mapping tables
│   ├── utils.cs                 # Binary helpers, image-type detection, XML utils
│   ├── Log.cs                   # Console + file logger
│   ├── version.cs               # Version string constant
│   ├── Xhtml-Entity-Set.dtd     # DTD used when parsing XHTML from the AZW3
│   └── template/
│       ├── template_opf.txt     # OPF manifest template
│       ├── template_ncx.txt     # toc.ncx template
│       ├── template_nav.txt     # nav.xhtml template
│       └── template_cover.txt   # Cover XHTML template
├── template_batch/              # Source for the .bat helper scripts
│   ├── _Tool_Drop_Single.txt
│   ├── _Tool_Drop_Single_Dedrm.txt
│   ├── _Tool_Drop_Dump_azwres.txt
│   ├── _Tool_Drop_MyKindleContent.txt
│   └── _Tool_Proc_MyKindleContent.txt
├── _Tool_Drop_Single.bat        # Drag-and-drop conversion helper
├── _Tool_Drop_Single_dedrm.bat  # Drag-and-drop with DeDRM helper
├── _Tool_Drop_Dump_azwres.bat   # Drag-and-drop HD image extractor
├── _Tool_Drop_MyKindleContent.bat
├── _Tool_Proc_MyKindleContent.bat  # Batch-process entire My Kindle Content folder
├── dedrm.bat                    # DeDRM launcher (calls AZW3_PC_DeDRM.exe)
├── publish.bat                  # Full release build script
├── clear.bat                    # Clean build artifacts
├── README.md                    # User-facing README (Chinese + English)
├── FAQ.md                       # Chinese FAQ
└── FAQ_EN.MD                    # English FAQ
```

---

## Architecture

### Data Flow

```
.azw (DRM-removed → .azw3)          .azw.res
         │                                │
    Azw3File ──────────────────────── Azw6File
         │                                │
         └──────────── Epub ─────────────┘
                         │
                     .epub file
```

### Key Classes

| Class | File | Responsibility |
|---|---|---|
| `Program` | `Program.cs` | CLI entry point; parses arguments; orchestrates `ProcPath`, `ProcBatch`, `DumpHDImage`, `DeDRM` |
| `AzwFile` | `Structs&Dictionary.cs` | Base class for both file types; reads PalmDB section table; exposes `GetSectionData(i)` |
| `Azw3File` | `Azw3File.cs` | Full AZW3 parse: header, rawML decompression, resource sections, INDX tables, FDST flow splitting, skeleton/fragment assembly into `xhtmls` and `flows` |
| `Azw6File` | `Azw6File.cs` | AZW.res parse: reads CRES (compressed image) and HREF sections |
| `Epub` | `EpubBuilder.cs` | Builds EPUB from `Azw3File` + optional `Azw6File`; processes Kindle-internal links; generates OPF, NCX, NAV; writes ZIP |
| `MobiHeader` | `Headers.cs` | Parses the first section of an AZW3 — all header fields and EXTH metadata |
| `Azw6Header` | `Headers.cs` | Parses the first section of an AZW.res |
| `ExtMeta` | `Headers.cs` | Decodes EXTH metadata records into string/value/hex maps |
| Section classes | `ProcessSection.cs` | `Section` (base), `FDST_Section`, `RESC_Section`, `INDX_Section_Main/Extra`, `CTOC_Section`, `Font_Section`, `Image_Section`, `Text_Section`, `CRES_Section`, `HREF_Section`, `PlaceHolder_Section` |
| `PalmdocDecoder` / `HuffmanDecoder` | `Decompress.cs` | Decompression for compression types 2 (PalmDOC) and 0x4448 (Huffman + CDIC) |
| `Util` | `utils.cs` | Big-endian binary readers, image-type sniffing, XML helpers, struct deserializer, filename sanitizer, `XmlEscape` |
| `Log` | `Log.cs` | Accumulates log lines; color-codes `[Warn]`/`[Error]`/`[Info]` on console; saves to `lastrun.log` |
| `IdMapping` | `Structs&Dictionary.cs` | Static dictionaries mapping EXTH record IDs to human-readable names |
| `Version` | `version.cs` | Single `version` string constant (date-formatted, e.g. `"20220126"`) |

---

## Build & Run

### Development (source build)

Requires .NET 5 SDK.

```bash
cd src
dotnet build
dotnet run -- <path-to-azw3-or-folder> [output-dir] [switches]
```

The program looks for a `template/` directory relative to the executable; if not found it changes working directory to the executable's folder. When running with `dotnet run`, ensure a `template/` symlink or copy is accessible, or the current directory already contains `template/`.

### Release Build (Windows only)

```bat
publish.bat
```

This script:
1. Cleans `bin/` everywhere.
2. Runs `dotnet publish -c Release -r win10-x64` (self-contained, single-file, trimmed).
3. Copies template files, DTD, batch scripts, and `AZW3_PC_DeDRM.exe` into `bin/`.

The output is a standalone `bin/app/UnpackKindleS.exe` that requires no .NET runtime.

---

## CLI Reference

```
UnpackKindleS <input> [output_dir] [switches]
```

`<input>` can be:
- An `.azw3` file (DRM-removed)
- An `.azw.res` file (the tool will look for a sibling `.azw3`)
- A folder containing either of the above
- A `B0XXXXXXXX_EBOK`-style folder (use with `-dedrm` or after manual DeDRM)

| Switch | Behaviour |
|---|---|
| `-dedrm` | Call `dedrm.bat` on any `.azw` files found before processing |
| `-batch` | Scan the input folder for EBOK subfolders and process each |
| `--just-dump-res` | Extract HD images from `.azw.res` only; no EPUB output |
| `--rename-xhtml-with-id` | Name XHTML files using `idref` values from the RESC spine (produces meaningful filenames for major publishers) |
| `--rename-when-exist` | Auto-increment output filename if it already exists |
| `--overwrite` | Silently overwrite existing output file |
| `--append-log` | Append to `lastrun.log` instead of overwriting |

Output filename defaults to `[Author] Title.epub` in the same directory as the input.

---

## AZW3/KF8 Format Notes

This section summarises the format as implemented in the code.

- **Container**: PalmDB. The section table starts at offset 78. Each entry is 8 bytes (4-byte start address + 4-byte attribute/uid word).
- **Section 0**: MOBI header. Contains compression type (2=PalmDOC, 0x4448=Huffman), record count, codepage (must be 65001/UTF-8), version (must be 8), and offsets to all index sections.
- **Text sections 1…N**: Compressed raw markup (rawML). Decoded and concatenated.
- **FDST section**: Flow section directory table — maps byte ranges in rawML to individual XHTML/CSS flows.
- **RESC section**: XML blob containing `<metadata>` and `<spine>` for the EPUB. Used to build OPF and (with `--rename-xhtml-with-id`) to name XHTML files.
- **INDX sections**: Four index types are used — Skeleton (`skel_index`), Fragment (`frag_index`), Guide (`guide_index`), NCX (`ncx_index`). Each has a main section (with TAGX tag descriptor) followed by N extra sections with variable-width-encoded entries. String data comes from associated CTOC sections.
- **Skeleton + Fragment reconstruction**: Each skeleton item is a base XHTML chunk; its associated fragment items are inserted at `file_position` offsets. This reconstructs the per-spine-item XHTML documents stored in `Azw3File.xhtmls`.
- **Flows**: Everything after flow 0 (the main XHTML) is stored in `Azw3File.flows`. Flows are referenced via `kindle:flow:BASE32?mime=type/subtype` attributes and resolved in `EpubBuilder.ProcTextRef`.
- **Image/Font sections**: Identified by magic bytes. Images become `OEBPS/Images/`; fonts (OTTO/.ttf) are XOR-obfuscated then optionally ZLIB-compressed and go into `OEBPS/Fonts/`.
- **All multi-byte integers are big-endian**. Use `Util.GetUInt8/16/32/64` — never read raw bytes with `BitConverter` directly.

---

## EPUB Output Structure

```
mimetype                       (stored, no compression)
META-INF/container.xml
OEBPS/
  content.opf
  toc.ncx
  nav.xhtml
  Text/
    part0000.xhtml  (or id-based names with --rename-xhtml-with-id)
    …
  Styles/
    flow0001.css
    …
  Images/
    embed0000.jpg / embed0000.png / …  (HD variants: embed0000_HD.*)
  Fonts/
    embed0000.otf / embed0000.ttf
```

Template files (`template_opf.txt`, `template_ncx.txt`, `template_nav.txt`, `template_cover.txt`) use `{❕placeholder}` tokens for substitution. `template_opf.txt` placeholders: `{❕meta}`, `{❕othermeta}`, `{❕version}`, `{❕manifest}`, `{❕spine}`, `{❕guide}`.

---

## Kindle-Internal Link Schemes

The XHTML in rawML uses Kindle-proprietary URI schemes that must be rewritten:

| Scheme | Handler | Translates to |
|---|---|---|
| `kindle:pos:fid:FFFF:off:OOOO` | `ProcLink` | `xhtml_filename#anchor` |
| `kindle:flow:BASE32?mime=type/subtype` | `ProcTextRef` | CSS href (`../Styles/flowNNNN.css`) or inlined SVG |
| `kindle:embed:BASE32?mime=image/ext` | `ProcEmbed` | `../Images/embedNNNN.ext` (HD image if azw6 is present), or `../Fonts/embedNNNN.ttf` for fonts |

BASE32 uses digits 0–9 then A–V (not standard base32 alphabet). Decoded by `Util.DecodeBase32`.

---

## Logging Conventions

`Log.log(string)` is the only logging API. Prefix conventions:

| Prefix | Console colour | Meaning |
|---|---|---|
| `[Warn]` | Yellow | Recoverable issue; processing continues |
| `[Error]` | Red | Non-fatal failure logged but not thrown |
| `[Info]` | Green | Notable informational message |
| (none) | White | Normal progress output |

Log is saved to `lastrun.log` one level above the executable after each run. Use `--append-log` for batch runs where you want a cumulative log.

---

## Error Handling

- `UnpackKindleSException` is the project's custom exception for format errors (e.g. wrong MOBI version, unsupported compression, encrypted file).
- In **Debug** builds the `CreateIndexDoc()` call in `EpubBuilder` is not wrapped; exceptions propagate immediately.
- In **Release** builds it is caught and logged so a malformed NCX/NAV does not abort the whole conversion. (Note: this means a TOC-generation bug can be silently swallowed in Release — check `lastrun.log` for `[Error]Cannot Create NCX or NAV.`)
- Per-book exceptions in `-batch` mode are always caught and logged so one bad book does not stop the batch.

---

## EPUB Compatibility Notes

These points are non-obvious and exist to prevent regressions — do not "simplify" them away.

### Cover image — triple declaration
The cover must be declared in three complementary ways in `content.opf` (`EpubBuilder.cs` `CreateOPF`):

1. **EPUB3 manifest property**: `<item properties="cover-image" .../>` — required by the EPUB 3 spec.
2. **EPUB2 legacy metadata**: `<meta name="cover" content="[image-id]"/>` — required by Google Play Books, Kobo, and most cloud/embedded readers that still use the EPUB2 heuristic.
3. **OPF guide reference**: `<guide><reference type="cover" .../></guide>` pointing at the cover XHTML page — extra insurance for older readers.

Removing any of these can break cover display on at least one class of reader. The cover image id is `Path.GetFileNameWithoutExtension(cover_name)` and matches the manifest item id.

### Font MIME types
Fonts in `OEBPS/Fonts/` use IANA-registered types: `.ttf` → `font/ttf`, `.otf` → `font/otf`. Do **not** revert to `application/font-sfnt` (never formally registered; rejected by some Readium-based readers).

### Font deduplication
`ProcEmbed`'s FONT branch must dedupe against `font_names` before adding (mirroring `AddImage`'s `img_names.Find` check). A font referenced from multiple CSS `@font-face` rules would otherwise be added multiple times, producing duplicate manifest `<item>` entries with the same id — an invalid EPUB.

### NCX / NAV require manual XML escaping
`toc.ncx` and `nav.xhtml` are assembled by **raw string concatenation** (`CreateIndexDoc_Helper`, the NAV guide loop, and the NCX `docTitle`), not via `XmlDocument`. Any text taken from CTOC (chapter titles, `docTitle`, guide names) **must** pass through `Util.XmlEscape` or a `&`/`<`/`>` in a title produces invalid XML and breaks the TOC (or the whole book) in strict readers. Content built through `XmlDocument` (manifest, spine, OPF metadata) is auto-escaped and does not need this.

### EXTH metadata access
Always use `ContainsKey` before indexing `ExtMeta.id_string[]` / `id_value[]`. Retail Kindle books always include fields 504 (ASIN) and 524 (language), but non-retail/malformed files may omit them and would otherwise throw `KeyNotFoundException` and abort. Fallbacks: language → `"ja"`, ASIN → `Guid.NewGuid().ToString()`.

### `dc:language` / `dc:identifier` use InnerText
Set these via `XmlElement.InnerText` (auto-escapes), not `InnerXml` (treats the value as markup).

### `dcterms:modified` timestamp format
Use `DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ssZ")` — uppercase `HH` (24-hour). Lowercase `hh` produces incorrect PM timestamps (15:30 → `T03:30:00Z`).

### `page-progression-direction` on the spine element
EXTH field 527 carries the reading direction (`rtl` for Japanese). It must be applied as an attribute on the `<spine>` element in the OPF, **not** as a `<meta>` element.

---

## Conventions & Code Style

- **Namespace**: `UnpackKindleS` (single namespace for the entire project).
- **Big-endian reads**: Always use `Util.GetUInt8/16/32/64`. Never use `BitConverter` directly on raw bytes from the file.
- **Struct deserialization**: `Util.GetStructBE<T>` reverses the byte array before pinning it, converting from big-endian to the host's little-endian layout.
- **No NuGet dependencies** beyond `System.Drawing.Common` (used only for `GetImageSize` in `Util`).
- Code comments and commit messages are primarily in **Chinese**; English is used for identifiers.
- Version string in `version.cs` follows `YYYYMMDD` format.
- When bumping the version, update only `src/version.cs`.

---

## DeDRM Integration

`dedrm.bat` (single line: calls `AZW3_PC_DeDRM.exe %1`) must be present next to the executable or one level up. It is invoked via `Process.Start` and `WaitForExit`. The `-dedrm` switch enables this path; without it the tool expects pre-decrypted `.azw3` files.

---

## Development Notes

- The project targets **net5** only. Do not upgrade to net6+ without verifying `System.Drawing.Common` still works on Windows (it was removed from cross-platform support in net6).
- `PublishTrimmed` + `TrimMode=Link` is used in Release; avoid reflection-based features or mark them with `[DynamicallyAccessedMembers]` if added.
- `publish.bat` expects a `Released\AZW3_PC_DeDRM.exe` file to exist in the repo root; this binary is not committed to source control but is required for a full release build.
- The `.gitattributes` file is present; check it if line-ending issues arise with the template `.txt` files.
