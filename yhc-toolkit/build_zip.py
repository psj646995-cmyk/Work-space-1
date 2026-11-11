"""Build YHC_도구모음.zip (A/B/C tools + read-me) at the repo root.

Run from anywhere:  python3 yhc-toolkit/build_zip.py
"""
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOP = "YHC_도구모음"
TOOLS = {
    "A_크리스마스카드 프로그램": REPO / "christmas-letter",
    "B_글자추출 프로그램": REPO / "handwriting-extraction",
    "C_사진용량 줄이기 프로그램": REPO / "photo-resizer",
}
SKIP_NAMES = {".gitignore", ".gitkeep", "__pycache__", "log.txt", ".DS_Store"}
SKIP_TOP_DIRS = {"photos", "drawings", "output", "input", "input_pdfs"}  # ship empty


def add_dir(z, path):
    z.writestr(zipfile.ZipInfo(path.rstrip("/") + "/"), "")


def to_crlf_bom(text):
    return ("﻿" + text.replace("\r\n", "\n").replace("\n", "\r\n")).encode("utf-8")


out = REPO / f"{TOP}.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    add_dir(z, TOP)
    readme = (Path(__file__).parent / "처음 읽어주세요.txt").read_text(encoding="utf-8")
    z.writestr(f"{TOP}/처음 읽어주세요.txt", to_crlf_bom(readme))
    for name, src in TOOLS.items():
        add_dir(z, f"{TOP}/{name}")
        for p in sorted(src.rglob("*")):
            rel = p.relative_to(src)
            if any(part in SKIP_NAMES for part in rel.parts):
                continue
            if rel.parts[0] in SKIP_TOP_DIRS:
                if len(rel.parts) == 1 and p.is_dir():
                    add_dir(z, f"{TOP}/{name}/{rel.as_posix()}")
                continue
            arc = f"{TOP}/{name}/{rel.as_posix()}"
            if p.is_dir():
                add_dir(z, arc)
            else:
                z.write(p, arc)
print(out, out.stat().st_size)
