#!/usr/bin/env python3
"""
후원 아동 크리스마스 편지 자동 합성 스크립트.

사진 / 그림 / 편지 문구(엑셀) / 편지지 템플릿(PDF) 네 가지 재료를 받아,
아동별로 완성된 편지 JPG 이미지를 만든다. 템플릿 위에 사진·그림·글자를
벡터로 겹쳐 그린 뒤 마지막에만 고해상도로 래스터화하므로, 중간 과정에서
품질 손실 없이 선명한 JPG가 나온다.

사용법 (Windows는 실행하기.bat 더블클릭으로 대체 가능):
    1) 대량 처리:
       - photos/, drawings/ 폴더에 엑셀의 이름과 같은 파일명으로 사진·그림을
         넣는다 (예: 이름이 "Alesi Yokonia"면 photos/Alesi Yokonia.jpg).
       - letters.xlsx에 번호(ID)/이름/편지 문구 3열을 채운다.
       - `python3 compose.py` 실행.
       - 결과는 output/ID_이름.jpg 로 저장되고, output/mismatch_report.html
         에 누락된 사진/그림/편지 목록이 정리된다.
    2) 한 명만 미리 확인(레이아웃 조정용):
       python3 compose.py --single --id "MWI 0040003" --name "ALESI YOKONIA" \
           --photo photos/x.jpg --drawing drawings/y.jpg \
           --letter "Dear Sponsor,\nThank you for your support.\nMerry Christmas~" \
           --out output/test.jpg
"""

import argparse
import html
import io
import re
import sys
from pathlib import Path

import pymupdf as fitz  # PDF 페이지를 JPG로 래스터화하는 데만 사용
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageOps
from openpyxl import load_workbook

# ---- 설정값 (필요에 따라 조정) -------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "template" / "template.pdf"
PHOTOS_DIR = BASE_DIR / "photos"
DRAWINGS_DIR = BASE_DIR / "drawings"
LETTERS_XLSX = BASE_DIR / "letters.xlsx"
OUTPUT_DIR = BASE_DIR / "output"
MISMATCH_REPORT = OUTPUT_DIR / "mismatch_report.html"
FONT_PATH = BASE_DIR / "assets" / "fonts" / "PatrickHand-Regular.ttf"
HANDWRITING_FONT_NAME = "PatrickHand"

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")

# 편지 문구 엑셀의 실제 컬럼명이 다르면 여기만 바꾸면 된다 (대소문자/앞뒤
# 공백은 자동으로 무시하고 비교한다).
COLUMN_MAP = {
    "id": "Child's ID",
    "name": "Child's Name",
    "letter": "Letter",
}

RASTER_DPI = 250        # 최종 JPG 해상도 (인쇄에도 충분한 수준)
JPEG_QUALITY = 92

fitz.TOOLS.mupdf_display_errors(False)  # 템플릿 PDF의 사소한 리소스 경고를 숨김(결과물에는 영향 없음)

# ---- 레이아웃 (페이지 비율 기준 0~1, 좌상단이 원점) -----------------------
# id_value/name_value는 template.pdf를 실제로 렌더링해 라벨 위치를 픽셀
# 단위로 측정해서 얻은 값(정확함). photo/letter/drawing 박스는 1차 추정치라
# 실제 사진으로 생성해보고 조정이 필요할 수 있다.

LAYOUT = {
    # 단순 텍스트 위치: (x, y) — y는 글자 베이스라인
    "id_value": {"x": 0.565, "y": 0.1188, "font": "Helvetica", "size": 16},
    "name_value": {"x": 0.565, "y": 0.1624, "font": "Helvetica-Bold", "size": 18},
    # 이미지/텍스트 박스: (x0, y0, x1, y1) — (x0,y0)=좌상단, (x1,y1)=우하단
    "photo_box": (0.08, 0.20, 0.46, 0.46),     # 좌측 상단
    "letter_box": (0.52, 0.20, 0.94, 0.46),    # 우측 상단
    "drawing_box": (0.25, 0.50, 0.75, 0.80),   # 하단 중앙
}

LETTER_FONT_MAX_SIZE = 17
LETTER_FONT_MIN_SIZE = 10
LETTER_LEADING_RATIO = 1.45
LETTER_TEXT_COLOR = (0.12, 0.16, 0.35)  # 진한 남색 (손글씨 잉크 느낌)


# ---- 좌표 변환 --------------------------------------------------------

def frac_to_pt(x_frac, y_frac, page_w, page_h):
    """비율 좌표(좌상단 원점) -> PDF 포인트(좌하단 원점)."""
    return x_frac * page_w, (1 - y_frac) * page_h


def frac_box_to_pt(box, page_w, page_h):
    """(x0,y0,x1,y1) 비율 박스 -> (x, y_bottom, width, height) PDF 포인트."""
    x0, y0, x1, y1 = box
    x_pt = x0 * page_w
    y_top_pt = (1 - y0) * page_h
    y_bottom_pt = (1 - y1) * page_h
    return x_pt, y_bottom_pt, (x1 - x0) * page_w, y_top_pt - y_bottom_pt


# ---- 이미지 처리 --------------------------------------------------------

def load_and_normalize_image(path: Path) -> Image.Image:
    """사진 회전(EXIF) 보정, RGB 변환. 손상 파일이면 예외를 그대로 올린다
    (호출부에서 파일별로 잡아서 경고 후 건너뛰도록)."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def place_image(c: canvas.Canvas, img: Image.Image, box, page_w, page_h):
    """box 안에 이미지 비율을 유지하며 중앙 정렬로 맞춰 넣는다(contain-fit)."""
    x, y, w, h = frac_box_to_pt(box, page_w, page_h)
    c.drawImage(
        ImageReader(img), x, y, width=w, height=h,
        preserveAspectRatio=True, anchor="c", mask="auto",
    )


# ---- 텍스트 자동 맞춤 --------------------------------------------------

def wrap_and_fit_text(c: canvas.Canvas, text: str, box, page_w, page_h,
                       font_name=HANDWRITING_FONT_NAME,
                       max_size=LETTER_FONT_MAX_SIZE,
                       min_size=LETTER_FONT_MIN_SIZE,
                       leading_ratio=LETTER_LEADING_RATIO):
    """box 폭에 맞게 줄바꿈하고, box 높이를 넘으면 글자 크기를 줄여 다시
    시도한다. 원래 줄바꿈(엔터)은 그대로 존중하고, 그 안에서 폭 초과분만
    추가로 줄바꿈한다. box 높이를 넘치면 True를 반환한다(호출부에서 경고용)."""
    x, y_bottom, w, h = frac_box_to_pt(box, page_w, page_h)
    paragraphs = text.split("\n")

    def wrap_for_size(size):
        lines = []
        for para in paragraphs:
            if para.strip() == "":
                lines.append("")
                continue
            words = para.split(" ")
            current = ""
            for word in words:
                candidate = (current + " " + word).strip()
                if pdfmetrics.stringWidth(candidate, font_name, size) <= w or not current:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    size = max_size
    while size >= min_size:
        lines = wrap_for_size(size)
        leading = size * leading_ratio
        block_height = leading * len(lines)
        if block_height <= h:
            break
        size -= 1
    else:
        lines = wrap_for_size(min_size)
        leading = min_size * leading_ratio

    overflow = (leading * len(lines)) > h

    c.setFont(font_name, size)
    c.setFillColorRGB(*LETTER_TEXT_COLOR)
    cursor_y = y_bottom + h - leading  # 첫 줄 베이스라인 (박스 상단에서 한 줄 내려온 위치)
    for line in lines:
        c.drawString(x, cursor_y, line)
        cursor_y -= leading

    return overflow


# ---- ID / 이름 값 --------------------------------------------------------

def draw_value(c: canvas.Canvas, text, spec, page_w, page_h):
    x, y = frac_to_pt(spec["x"], spec["y"], page_w, page_h)
    c.setFont(spec["font"], spec["size"])
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(x, y, text)


# ---- 한 명 합성 --------------------------------------------------------

def register_fonts():
    if HANDWRITING_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(HANDWRITING_FONT_NAME, str(FONT_PATH)))


def render_pdf_bytes_to_jpg(pdf_bytes: bytes, output_path: Path,
                             dpi=RASTER_DPI, quality=JPEG_QUALITY):
    """단일 페이지 PDF(bytes)를 고해상도 JPG로 래스터화해 저장한다."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "JPEG", quality=quality)
    doc.close()


def compose_one(child_id: str, child_name: str, letter_text: str,
                 photo_path: Path, drawing_path: Path, output_path: Path) -> bool:
    """한 아동의 편지 JPG를 생성한다. 편지 문구가 넘쳐서 잘렸으면 True를
    반환한다(호출부에서 경고로 기록하도록)."""
    register_fonts()

    reader = PdfReader(str(TEMPLATE_PATH))
    page = reader.pages[0]
    page_w = float(page.mediabox.width)
    page_h = float(page.mediabox.height)

    overlay_buf = io.BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=(page_w, page_h))

    draw_value(c, child_id, LAYOUT["id_value"], page_w, page_h)
    draw_value(c, child_name.upper(), LAYOUT["name_value"], page_w, page_h)

    photo_img = load_and_normalize_image(photo_path)
    place_image(c, photo_img, LAYOUT["photo_box"], page_w, page_h)

    drawing_img = load_and_normalize_image(drawing_path)
    place_image(c, drawing_img, LAYOUT["drawing_box"], page_w, page_h)

    overflow = wrap_and_fit_text(c, letter_text, LAYOUT["letter_box"], page_w, page_h)

    c.save()
    overlay_buf.seek(0)

    overlay_reader = PdfReader(overlay_buf)
    page.merge_page(overlay_reader.pages[0])

    writer = PdfWriter()
    writer.add_page(page)
    pdf_buf = io.BytesIO()
    writer.write(pdf_buf)

    render_pdf_bytes_to_jpg(pdf_buf.getvalue(), output_path)
    return overflow


# ---- 이름 매칭 --------------------------------------------------------

def normalize_name(name) -> str:
    """공백/대소문자 차이를 무시하고 비교하기 위한 정규화."""
    return re.sub(r"\s+", " ", str(name).strip()).casefold()


def safe_filename_part(text: str) -> str:
    """ID/이름을 출력 파일명에 안전하게 쓰기 위해 경로 구분자 등을 제거."""
    return re.sub(r'[\\/:*?"<>|]', "", str(text).strip()) or "unknown"


def find_asset(directory: Path, name: str) -> Path | None:
    """directory 안에서 정규화한 이름이 일치하는 이미지 파일을 찾는다.
    여러 개가 일치하면 첫 번째를 쓰고 경고를 출력한다."""
    if not directory.exists():
        return None
    target = normalize_name(name)
    matches = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        and normalize_name(p.stem) == target
    ]
    if not matches:
        return None
    if len(matches) > 1:
        print(f"  경고: '{name}' 이름으로 파일이 {len(matches)}개 일치합니다 "
              f"({', '.join(p.name for p in matches)}). 첫 번째 파일을 사용합니다.")
    return matches[0]


# ---- 엑셀 읽기 --------------------------------------------------------

def load_letters(xlsx_path: Path) -> dict:
    """엑셀을 읽어 {정규화된 이름: {"id":.., "name":.., "letter":..}} 딕셔너리로
    반환한다. 컬럼명이 COLUMN_MAP과 다르면 실제 헤더 목록을 담은 오류를 낸다."""
    try:
        wb = load_workbook(xlsx_path, data_only=True, read_only=True)
    except PermissionError:
        raise RuntimeError(
            f"{xlsx_path.name}이(가) 열려있으면 읽을 수 없습니다. "
            "엑셀에서 파일을 닫고 다시 실행해주세요."
        )
    sheet = wb.active

    header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if header_row is None:
        raise RuntimeError(f"{xlsx_path.name}에 헤더 행이 없습니다.")
    headers = [str(h).strip() if h is not None else "" for h in header_row]
    header_lookup = {h.casefold(): i for i, h in enumerate(headers) if h}

    col_index = {}
    missing_cols = []
    for key, wanted_header in COLUMN_MAP.items():
        idx = header_lookup.get(wanted_header.strip().casefold())
        if idx is None:
            missing_cols.append(wanted_header)
        else:
            col_index[key] = idx

    if missing_cols:
        raise RuntimeError(
            f"{xlsx_path.name}에서 다음 컬럼을 찾을 수 없습니다: {', '.join(missing_cols)}\n"
            f"  실제 엑셀의 헤더: {', '.join(h for h in headers if h)}\n"
            f"  compose.py 상단의 COLUMN_MAP 값을 실제 헤더명에 맞게 고쳐주세요."
        )

    letters = {}
    duplicate_names = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row is None or all(v is None for v in row):
            continue
        name = row[col_index["name"]]
        if name is None or str(name).strip() == "":
            continue
        child_id = row[col_index["id"]]
        letter_text = row[col_index["letter"]]
        key = normalize_name(name)
        if key in letters:
            duplicate_names.append(str(name).strip())
        letters[key] = {
            "id": "" if child_id is None else str(child_id).strip(),
            "name": str(name).strip(),
            "letter": "" if letter_text is None else str(letter_text).strip(),
        }

    if duplicate_names:
        print(f"경고: 엑셀에 이름이 중복된 행이 있습니다 (나중 행으로 덮어씀): "
              f"{', '.join(duplicate_names)}")

    wb.close()
    return letters


# ---- 매칭 --------------------------------------------------------

def match_children(letters: dict):
    """엑셀의 각 아동에 대해 사진/그림 파일을 찾아 매칭한다.
    matched: 사진+그림 모두 찾은 아동 목록
    missing: 사진 또는 그림이 없는 아동 목록 (이유 포함)
    """
    matched = []
    missing = []
    for key, rec in letters.items():
        photo_path = find_asset(PHOTOS_DIR, rec["name"])
        drawing_path = find_asset(DRAWINGS_DIR, rec["name"])
        reasons = []
        if photo_path is None:
            reasons.append("사진 없음")
        if drawing_path is None:
            reasons.append("그림 없음")
        if not rec["letter"]:
            reasons.append("편지 문구 없음")
        if reasons:
            missing.append({**rec, "reasons": reasons})
        else:
            matched.append({**rec, "photo_path": photo_path, "drawing_path": drawing_path})
    return matched, missing


# ---- 리포트 --------------------------------------------------------

def write_mismatch_report(missing: list, processing_warnings: list):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in missing:
        rows.append(
            f"<tr><td>{html.escape(m.get('id',''))}</td>"
            f"<td>{html.escape(m['name'])}</td>"
            f"<td>{html.escape(', '.join(m['reasons']))}</td></tr>"
        )
    warn_rows = []
    for w in processing_warnings:
        warn_rows.append(
            f"<tr><td>{html.escape(w.get('id',''))}</td>"
            f"<td>{html.escape(w['name'])}</td>"
            f"<td>{html.escape(w['reason'])}</td></tr>"
        )
    page = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>크리스마스 편지 처리 결과</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 32px; color: #222; }}
h1 {{ font-size: 20px; }}
table {{ border-collapse: collapse; margin-bottom: 32px; width: 100%; max-width: 720px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 14px; }}
th {{ background: #f2f2f2; }}
</style></head><body>
<h1>누락된 자료 (사진/그림/편지 문구가 없어 건너뛴 아동)</h1>
<table><tr><th>ID</th><th>이름</th><th>사유</th></tr>
{''.join(rows) if rows else '<tr><td colspan="3">없음</td></tr>'}
</table>
<h1>생성 중 경고 (편지 문구가 넘쳐 글자를 줄인 경우 등)</h1>
<table><tr><th>ID</th><th>이름</th><th>사유</th></tr>
{''.join(warn_rows) if warn_rows else '<tr><td colspan="3">없음</td></tr>'}
</table>
</body></html>"""
    MISMATCH_REPORT.write_text(page, encoding="utf-8")


# ---- 대량 처리 --------------------------------------------------------

def run_batch():
    if not LETTERS_XLSX.exists():
        print(f"{LETTERS_XLSX.name}이(가) 없습니다. christmas-letter 폴더에 "
              f"편지 문구 엑셀을 '{LETTERS_XLSX.name}' 이름으로 넣어주세요.")
        sys.exit(1)

    try:
        letters = load_letters(LETTERS_XLSX)
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)

    if not letters:
        print("엑셀에서 처리할 아동을 찾지 못했습니다 (이름 열이 모두 비어있음).")
        sys.exit(1)

    matched, missing = match_children(letters)
    print(f"엑셀 아동 수: {len(letters)}개 / 사진·그림 모두 매칭됨: {len(matched)}개 / "
          f"누락: {len(missing)}개")

    processed = 0
    skipped = 0
    processing_warnings = []

    for rec in matched:
        out_name = f"{safe_filename_part(rec['id'])}_{safe_filename_part(rec['name'])}.jpg"
        output_path = OUTPUT_DIR / out_name
        if output_path.exists():
            skipped += 1
            continue
        try:
            overflow = compose_one(
                rec["id"], rec["name"], rec["letter"],
                rec["photo_path"], rec["drawing_path"], output_path,
            )
            if overflow:
                processing_warnings.append({
                    "id": rec["id"], "name": rec["name"],
                    "reason": "편지 문구가 길어 최소 글자 크기로도 넘칠 수 있음 (결과물 확인 권장)",
                })
            processed += 1
            print(f"생성됨: {output_path.name}")
        except Exception as exc:
            processing_warnings.append({
                "id": rec["id"], "name": rec["name"],
                "reason": f"처리 중 오류로 건너뜀: {exc}",
            })
            print(f"  경고: {rec['name']} 처리 중 오류, 건너뜁니다: {exc}")

    write_mismatch_report(missing, processing_warnings)

    print("\n--- 처리 요약 ---")
    print(f"새로 생성: {processed}개")
    print(f"이미 있어서 건너뜀: {skipped}개")
    print(f"자료 누락으로 제외: {len(missing)}개")
    print(f"처리 중 경고: {len(processing_warnings)}개")
    print(f"결과 확인: {MISMATCH_REPORT}")


# ---- CLI --------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="크리스마스 편지 자동 합성")
    parser.add_argument("--single", action="store_true", help="한 명만 합성해서 레이아웃 확인")
    parser.add_argument("--id", dest="child_id")
    parser.add_argument("--name", dest="child_name")
    parser.add_argument("--photo", type=Path)
    parser.add_argument("--drawing", type=Path)
    parser.add_argument("--letter", dest="letter_text")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        print(f"템플릿 파일이 없습니다: {TEMPLATE_PATH}")
        sys.exit(1)

    if args.single:
        missing = [n for n in ("child_id", "child_name", "photo", "drawing", "letter_text", "out")
                   if getattr(args, n) is None]
        if missing:
            print(f"--single 모드에는 다음 옵션이 모두 필요합니다: {', '.join(missing)}")
            sys.exit(1)
        letter_text = args.letter_text.replace("\\n", "\n")
        compose_one(args.child_id, args.child_name, letter_text,
                    args.photo, args.drawing, args.out)
        print(f"생성됨: {args.out}")
        return

    run_batch()


if __name__ == "__main__":
    main()
