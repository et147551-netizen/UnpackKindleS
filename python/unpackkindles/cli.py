"""Command-line entry point. Ported from Program.cs.

Cross-platform: DeDRM shells out to dedrm.bat on Windows or dedrm.sh elsewhere.
Templates and the entity DTD are loaded as packaged resources, so (unlike the
C# version) the working directory is never changed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import List, Optional

from . import log
from .version import VERSION
from .util import filename_check
from .azw3 import Azw3File
from .azw6 import Azw6File
from .epub import Epub

_USAGE = ("Usage: <xxx_nodrm.azw3 or xxx.azw.res or the directory> "
          "[<output_path>] [switches ...]")


class _State:
    dedrm = False
    end_of_proc = False
    append_log = False
    overwrite = False
    rename_when_exist = False
    rename_xhtml_with_id = False


def _ext(path: str) -> str:
    return os.path.splitext(path)[1]


def main(argv: Optional[List[str]] = None) -> None:
    if argv is None:
        argv = sys.argv[1:]
    st = _State()

    print("UnpackKindleS Ver." + VERSION)
    print("https://github.com/Aeroblast/UnpackKindleS")

    if len(argv) < 1:
        print(_USAGE)
        return
    if not os.path.isdir(argv[0]) and not os.path.isfile(argv[0]):
        print("The file or folder does not exist:" + argv[0])
        print(_USAGE)
        return

    for a in argv:
        al = a.lower()
        if al == "-dedrm":
            st.dedrm = True
        if al == "--just-dump-res":
            _dump_hd_image(argv)
            st.end_of_proc = True
        if al == "--append-log":
            st.append_log = True
        if al == "--overwrite":
            st.overwrite = True
        if al == "--rename-when-exist":
            st.rename_when_exist = True
        if al == "--rename-xhtml-with-id":
            st.rename_xhtml_with_id = True

    if not st.end_of_proc:
        for a in argv:
            if a.lower() == "-batch":
                _proc_batch(argv, st)

    if not st.end_of_proc:
        _proc_path(argv, st)

    if st.append_log:
        log.append("lastrun.log")
    else:
        log.save("lastrun.log")


def _proc_batch(argv: List[str], st: _State) -> None:
    log.log("Batch Process:" + argv[0])
    dirs = [os.path.join(argv[0], d) for d in os.listdir(argv[0])
            if os.path.isdir(os.path.join(argv[0], d))]
    for s in dirs:
        if "EBOK" not in s:
            continue
        args2 = [s, ""]
        if len(argv) >= 2 and os.path.isdir(argv[1]):
            args2[1] = argv[1]
        else:
            args2[1] = os.getcwd()
        try:
            _proc_path(args2, st)
        except Exception as e:  # noqa: BLE001
            log.log(str(e))
    st.end_of_proc = True


def _proc_path(argv: List[str], st: _State) -> None:
    azw3_path = None
    azw6_path = None
    p = argv[0]

    if os.path.isdir(p):
        files = [os.path.join(p, f) for f in os.listdir(p)]
        if st.dedrm:
            for n in files:
                if _ext(n).lower() == ".azw":
                    _dedrm(n)
            files = [os.path.join(p, f) for f in os.listdir(p)]
        for n in files:
            if _ext(n).lower() == ".azw3":
                azw3_path = n
            if _ext(n) == ".res":
                azw6_path = n
    else:
        if st.dedrm and _ext(p).lower() == ".azw":
            _dedrm(p)
            d = os.path.dirname(p)
            for n in [os.path.join(d, f) for f in os.listdir(d)]:
                if _ext(n) == ".res":
                    azw6_path = n
                if _ext(n).lower() == ".azw3":
                    azw3_path = n
        elif _ext(p).lower() == ".azw3":
            azw3_path = p
            d = os.path.dirname(p)
            for n in [os.path.join(d, f) for f in os.listdir(d)]:
                if _ext(n) == ".res":
                    azw6_path = n
                    break
        elif _ext(p).lower() == ".res":
            azw6_path = p
            d = os.path.dirname(p)
            for n in [os.path.join(d, f) for f in os.listdir(d)]:
                if _ext(n).lower() == ".azw3":
                    azw3_path = n
                    break

    azw3 = None
    azw6 = None
    if azw3_path is not None:
        log.log("==============START===============")
        azw3 = Azw3File(azw3_path)
    if azw6_path is not None:
        azw6 = Azw6File(azw6_path)

    if azw3 is not None:
        author = ""
        if 100 in azw3.mobi_header.ext_meta.id_string:
            author = "[" + azw3.mobi_header.ext_meta.id_string[100].split("&")[0] + "] "
        outname = author + azw3.title + ".epub"
        outname = filename_check(outname)
        epub = Epub(azw3, azw6, st.rename_xhtml_with_id)
        log.log_azw3(azw3)
        if len(argv) >= 2 and os.path.isdir(argv[1]):
            output_path = os.path.join(argv[1], outname)
        else:
            output_path = os.path.join(os.path.dirname(argv[0]), outname)

        if os.path.exists(output_path):
            log.log("[Warn]Output already exist.")
            if st.rename_when_exist:
                output_path = _rename_path(output_path)
                log.log("[Warn]Save as...")
            elif not st.overwrite:
                print("Output file already exist. N(Abort,Defualt)/y(Overwrite)/r(Rename)?")
                print("Output path:" + output_path)
                inp = input().lower()
                if inp == "y":
                    log.log("[Warn]Old file will be replaced.")
                elif inp == "r":
                    output_path = _rename_path(output_path)
                    log.log("[Warn]Save as...")
                else:
                    log.log("[Error]Operation aborted. You can use --overwrite "
                            "or --rename-when-exist to avoid pause.")
                    output_path = ""
            else:
                log.log("[Warn]Old file will be replaced.")

        if output_path != "":
            epub.save(output_path)
        log.log("azw3 source:" + azw3_path)
        if azw6_path is not None:
            log.log("azw6 source:" + azw6_path)
    else:
        print("Cannot find .azw3 file in " + p)


def _rename_path(output_path: str) -> str:
    r_dir = os.path.dirname(output_path)
    r_name = os.path.splitext(os.path.basename(output_path))[0]
    r_path = os.path.join(r_dir, r_name)
    for i in range(2, 50):
        r_test = r_path + "(" + str(i) + ").epub"
        if not os.path.exists(r_test):
            return r_test
    return ""


def _dump_hd_image(argv: List[str]) -> None:
    log.log("Dump azw.res")
    log.log("azw6 source:" + argv[0])
    if not os.path.isfile(argv[0]):
        log.log("File was not found:" + argv[0])
        return
    azw = Azw6File(argv[0])
    if len(argv) >= 3:
        outputdir = argv[1]
    else:
        outputdir = os.path.join(os.path.dirname(argv[0]), filename_check(azw.header.title))
    if not _create_directory(outputdir):
        return
    for a in azw.image_sections:
        sec = azw.sections[a]
        filename = Epub.image_name_hd(a - 1, sec)
        with open(os.path.join(outputdir, filename), "wb") as f:
            f.write(sec.img)
        log.log("Saved:" + os.path.join(outputdir, filename))


def _dedrm(file: str) -> None:
    # Windows: dedrm.bat; other platforms: dedrm.sh.
    candidates = (["dedrm.bat", os.path.join("..", "dedrm.bat")]
                  if os.name == "nt"
                  else ["dedrm.sh", os.path.join("..", "dedrm.sh")])
    fn = None
    for c in candidates:
        if os.path.isfile(c):
            fn = c
            break
    if fn is None:
        log.log("Cannot found " + candidates[0])
        return
    subprocess.run([fn, file], check=False)


def _create_directory(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        log.log(str(e))
        return False
    return True
