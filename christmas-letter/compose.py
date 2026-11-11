#!/usr/bin/env python3
"""
후원 아동 크리스마스 편지 자동 합성 스크립트.

사진 / 그림 / 편지 문구(엑셀) / 편지지 템플릿(PDF) 네 가지 재료를 받아,
아동별로 완성된 편지 JPG 이미지를 만든다. 템플릿 위에 사진·그림·글자를
벡터로 겹쳐 그린 뒤 마지막에만 고해상도로 래스터화하므로, 중간 과정에서
품질 손실 없이 선명한 JPG가 나온다.

사용법 (Windows는 실행하기.bat 더블클릭으로 대체 가능):
    1) 대량 처리:
       - photos/, drawings/ 폴더에 엑셀의 아동 ID와 같은 파일명으로 사진·그림을
         넣는다 (예: ID가 "MWI0040001"이면 photos/MWI0040001.jpg).
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
from PIL import Image, ImageOps, ImageFilter
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

# 편지 문구 엑셀의 실제 컬럼명 후보들. 각 항목마다 여러 후보를 적어두면 그 중
# 하나라도 일치하는 헤더를 사용한다(대소문자/앞뒤 공백은 자동 무시). "name"은
# 사진·그림 파일명과 매칭하는 데도 쓰이므로 영어 이름 컬럼을 우선순위 앞쪽에
# 둔다. "letter" 후보가 하나도 안 맞으면, 헤더가 비어있으면서 실제 편지
# 내용이 들어있는 첫 번째 열을 자동으로 편지 문구 열로 인식한다(엑셀에 편지
# 문구 열 제목이 없는 경우를 위한 안전장치).
COLUMN_MAP = {
    "id": ["아동Id(Child Code)", "Child's ID", "ID", "번호"],
    "name": ["아동명(Child Name(ENG))", "Child's Name", "Name", "이름"],
    "letter": ["Letter", "편지", "편지 내용", "편지문구"],
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
    "drawing_box": (0.10, 0.47, 0.90, 0.81),   # 하단 중앙 (사진/문구 박스 폭에 맞춰 확대)
}

LETTER_FONT_MAX_SIZE = 17
LETTER_FONT_MIN_SIZE = 10
LETTER_LEADING_RATIO = 1.45
LETTER_TEXT_COLOR = (0.12, 0.16, 0.35)  # 진한 남색 (손글씨 잉크 느낌)

# 그림 스캔본(A5 용지 등)의 흰 여백을 자동으로 잘라내는 설정. 그림이 실제
# 용지보다 훨씬 작게 그려져 있으면 이 크롭이 그림을 훨씬 크게 보이게 해준다.
AUTOCROP_DRAWINGS = True
AUTOCROP_BACKGROUND_THRESHOLD = 235   # 밝기(0~255)가 이보다 밝으면 "여백"으로 간주
AUTOCROP_PADDING_FRAC = 0.03          # 크롭 후 사방에 남기는 여유(원본 크기 대비 비율)
AUTOCROP_BORDER_IGNORE_FRAC = 0.01    # 스캐너 가장자리 그림자/테두리 오탐 방지용으로 무시할 바깥쪽 폭
AUTOCROP_MIN_KEEP_FRAC = 0.05         # 감지된 영역이 이보다 작으면(오탐 의심) 크롭하지 않고 원본 사용


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


def autocrop_scan(img: Image.Image) -> Image.Image:
    """A5 등 스캔 용지의 흰 여백을 자동으로 잘라내고 실제 그림이 있는
    영역만 남긴다. 여백이 거의 없거나(이미 크롭된 이미지) 감지에 실패하면
    안전하게 원본을 그대로 반환한다."""
    w, h = img.size
    gray = img.convert("L").filter(ImageFilter.GaussianBlur(radius=2))

    # 스캐너 가장자리의 그림자/검은 테두리 때문에 전체가 "그림"으로 오탐되는
    # 것을 막기 위해, 가장 바깥쪽 얇은 테두리는 검사에서 제외한다.
    bx = max(1, int(w * AUTOCROP_BORDER_IGNORE_FRAC))
    by = max(1, int(h * AUTOCROP_BORDER_IGNORE_FRAC))
    inner = gray.crop((bx, by, w - bx, h - by))

    mask = inner.point(lambda p: 255 if p < AUTOCROP_BACKGROUND_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox is None:
        return img  # 여백만 있고 내용이 감지되지 않음 -> 원본 그대로

    x0, y0, x1, y1 = bbox
    pad_x = int(w * AUTOCROP_PADDING_FRAC)
    pad_y = int(h * AUTOCROP_PADDING_FRAC)
    x0 = max(0, x0 + bx - pad_x)
    y0 = max(0, y0 + by - pad_y)
    x1 = min(w, x1 + bx + pad_x)
    y1 = min(h, y1 + by + pad_y)

    if (x1 - x0) < w * AUTOCROP_MIN_KEEP_FRAC or (y1 - y0) < h * AUTOCROP_MIN_KEEP_FRAC:
        return img  # 감지 영역이 비정상적으로 작음(오탐 의심) -> 원본 그대로

    return img.crop((x0, y0, x1, y1))


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
    if AUTOCROP_DRAWINGS:
        drawing_img = autocrop_scan(drawing_img)
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


def normalize_id(child_id) -> str:
    """아동 ID 비교용 정규화. "MWI 0040001", "MWI-0040001", "mwi0040001"처럼
    공백/하이픈/언더스코어 유무나 대소문자가 다르게 표기돼도 같은 ID로
    취급하도록 그런 문자를 전부 제거하고 대문자로 통일한다."""
    return re.sub(r"[\s_\-]+", "", str(child_id).strip()).upper()


def safe_filename_part(text: str) -> str:
    """ID/이름을 출력 파일명에 안전하게 쓰기 위해 경로 구분자 등을 제거."""
    return re.sub(r'[\\/:*?"<>|]', "", str(text).strip()) or "unknown"


def find_asset_by_id(directory: Path, child_id: str, child_name: str = "") -> Path | None:
    """directory 안에서 정규화한 아동 ID가 일치하는 이미지 파일을 찾는다.
    같은 ID로 여러 파일이 잡히면(파일 하나의 ID가 다른 아동과 겹치는 오타
    등), 그 후보들 중 파일명에 이 아동의 이름(엑셀 기준)이 들어있는 파일을
    우선으로 골라 애매함을 해소한다. 그래도 못 정하면 첫 번째를 쓰고 경고."""
    if not directory.exists():
        return None
    target = normalize_id(child_id)
    # 정확히 일치하는 파일을 최우선으로 찾고("MWI0040001.jpg"), 없으면
    # 파일명이 그 ID로 시작하는 파일도 허용한다("MWI0040001 ABGIRL
    # MANDALIZA.jpg"처럼 ID 뒤에 이름이 붙어있는 실제 파일명 형식을 위함).
    # 모든 ID가 "MWI"+7자리 숫자로 길이가 고정돼 있어 접두어 매칭으로 다른
    # 아동과 혼동될 위험은 없다.
    exact = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        and normalize_id(p.stem) == target
    ]
    matches = exact or [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        and normalize_id(p.stem).startswith(target)
    ]
    if not matches:
        return None
    if len(matches) > 1:
        name_tokens = _word_tokens(child_name) if child_name else []
        by_name = [
            p for p in matches
            if name_tokens and _tokens_contain_subsequence(_word_tokens(p.stem), name_tokens)
        ]
        if len(by_name) == 1:
            return by_name[0]
        matches = by_name if by_name else matches
        if len(matches) > 1:
            print(f"  경고: ID '{child_id}'로 파일이 {len(matches)}개 일치하고, "
                  f"이름으로도 구분이 안 됩니다 ({', '.join(p.name for p in matches)}). "
                  f"첫 번째 파일을 사용합니다.")
    return matches[0]


def _word_tokens(s) -> list:
    """문자/숫자가 아닌 문자를 기준으로 토큰화 (파일명·이름 비교용)."""
    return [t.lower() for t in re.split(r"[^0-9A-Za-z]+", str(s)) if t]


def _tokens_contain_subsequence(haystack: list, needle: list) -> bool:
    if not needle:
        return False
    n = len(needle)
    return any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def find_asset_by_name(directory: Path, child_name: str) -> Path | None:
    """ID로 못 찾았을 때 쓰는 폴백. 파일명 토큰 안에 아동 이름의 토큰들이
    순서대로(붙어서) 들어있는 파일을 찾는다 — ID 부분에 오타가 있어도
    ("MWI00040332 HOSSEA JONAS.jpg") 이름이 맞으면 잡아낸다. 부분 단어
    일치가 아니라 단어 단위로 비교해서 엉뚱한 아동과 혼동될 위험을 줄인다."""
    if not directory.exists():
        return None
    name_tokens = _word_tokens(child_name)
    if not name_tokens:
        return None
    matches = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
        and _tokens_contain_subsequence(_word_tokens(p.stem), name_tokens)
    ]
    if not matches:
        return None
    if len(matches) > 1:
        print(f"  경고: 이름 '{child_name}'(으)로 파일이 {len(matches)}개 일치합니다 "
              f"({', '.join(p.name for p in matches)}). 첫 번째 파일을 사용합니다.")
    return matches[0]


def list_asset_filenames(directory: Path, limit: int = 5) -> list:
    if not directory.exists():
        return []
    names = sorted(
        p.name for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )
    return names[:limit]


# ---- 엑셀 읽기 --------------------------------------------------------

def _column_letter(idx: int) -> str:
    """0-based 열 인덱스를 엑셀 열 문자로 바꾼다 (0->A, 4->E ...)."""
    letters = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def load_letters(xlsx_path: Path) -> dict:
    """엑셀을 읽어 {정규화된 이름: {"id":.., "name":.., "letter":..}} 딕셔너리로
    반환한다. COLUMN_MAP의 후보 헤더 중 하나라도 일치하면 그 열을 쓴다.
    "letter" 열은 후보로 못 찾으면, 헤더가 비어있으면서 첫 데이터 행에 실제
    글자가 들어있는 첫 번째 열을 자동으로 편지 문구 열로 인식한다."""
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

    first_data_row = next(sheet.iter_rows(min_row=2, max_row=2, values_only=True), None) or ()

    col_index = {}
    missing_keys = []
    for key, candidates in COLUMN_MAP.items():
        idx = None
        for candidate in candidates:
            idx = header_lookup.get(candidate.strip().casefold())
            if idx is not None:
                break
        if idx is None and key == "letter":
            # 헤더가 비어있는 열 중, 첫 데이터 행에 실제 글자(10자 이상)가
            # 들어있는 첫 번째 열을 편지 문구 열로 추정한다.
            for i, h in enumerate(headers):
                if h:
                    continue
                value = first_data_row[i] if i < len(first_data_row) else None
                if value is not None and len(str(value).strip()) >= 10:
                    idx = i
                    print(f"  편지 문구 열 제목이 비어있어 {_column_letter(i)}열을 "
                          f"편지 문구 열로 자동 인식했습니다.")
                    break
        if idx is None:
            missing_keys.append(key)
        else:
            col_index[key] = idx

    if missing_keys:
        missing_desc = ", ".join(
            f"{key}({'/'.join(COLUMN_MAP[key])})" for key in missing_keys
        )
        raise RuntimeError(
            f"{xlsx_path.name}에서 다음 컬럼을 찾을 수 없습니다: {missing_desc}\n"
            f"  실제 엑셀의 헤더: {', '.join(h for h in headers if h)}\n"
            f"  compose.py 상단의 COLUMN_MAP 값을 실제 헤더명에 맞게 고쳐주세요."
        )

    letters = {}
    duplicate_ids = []
    skipped_no_id = 0
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row is None or all(v is None for v in row):
            continue
        name = row[col_index["name"]]
        if name is None or str(name).strip() == "":
            continue
        child_id = row[col_index["id"]]
        if child_id is None or str(child_id).strip() == "":
            skipped_no_id += 1
            continue
        letter_text = row[col_index["letter"]]
        key = normalize_id(child_id)
        if key in letters:
            duplicate_ids.append(str(child_id).strip())
        letters[key] = {
            "id": str(child_id).strip(),
            "name": str(name).strip(),
            "letter": "" if letter_text is None else str(letter_text).strip(),
        }

    if duplicate_ids:
        print(f"경고: 엑셀에 ID가 중복된 행이 있습니다 (나중 행으로 덮어씀): "
              f"{', '.join(duplicate_ids)}")
    if skipped_no_id:
        print(f"경고: ID가 비어있는 행 {skipped_no_id}개는 건너뛰었습니다.")

    wb.close()
    return letters


# ---- 매칭 --------------------------------------------------------

def match_children(letters: dict):
    """엑셀의 각 아동에 대해 아동 ID로 사진/그림 파일을 찾아 매칭한다.
    ID로 못 찾으면(파일명의 ID 부분에 오타가 있는 경우 등) 파일명 안의
    이름으로 다시 찾아본다 — 어느 쪽으로 찾았든, 편지지에 쓰이는 ID/이름은
    항상 엑셀 값을 쓰므로 파일명의 오타가 결과물에 영향을 주지 않는다.

    matched: 사진+그림 모두 찾은 아동 목록
    missing: 사진 또는 그림이 없는 아동 목록 (이유 포함)
    name_fallback: ID로는 못 찾고 이름으로 찾은 항목 기록 (감사용 — 파일명의
    ID 오타를 사용자가 나중에 알 수 있도록 리포트에 남긴다)
    """
    matched = []
    missing = []
    name_fallback = []

    for key, rec in letters.items():
        photo_path = find_asset_by_id(PHOTOS_DIR, rec["id"], rec["name"])
        photo_via_name = False
        if photo_path is None:
            photo_path = find_asset_by_name(PHOTOS_DIR, rec["name"])
            photo_via_name = photo_path is not None

        drawing_path = find_asset_by_id(DRAWINGS_DIR, rec["id"], rec["name"])
        drawing_via_name = False
        if drawing_path is None:
            drawing_path = find_asset_by_name(DRAWINGS_DIR, rec["name"])
            drawing_via_name = drawing_path is not None

        if photo_via_name or drawing_via_name:
            via = []
            if photo_via_name:
                via.append(f"사진: {photo_path.name}")
            if drawing_via_name:
                via.append(f"그림: {drawing_path.name}")
            name_fallback.append({**rec, "via": via})

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
    return matched, missing, name_fallback


# ---- 리포트 --------------------------------------------------------

def write_mismatch_report(missing: list, processing_warnings: list, name_fallback: list):
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
    fallback_rows = []
    for f in name_fallback:
        fallback_rows.append(
            f"<tr><td>{html.escape(f.get('id',''))}</td>"
            f"<td>{html.escape(f['name'])}</td>"
            f"<td>{html.escape(', '.join(f['via']))}</td></tr>"
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
<h1>ID 대신 이름으로 찾은 아동 (파일명의 ID 부분에 오타가 있을 수 있음)</h1>
<table><tr><th>ID(엑셀 기준, 정상 인쇄됨)</th><th>이름</th><th>이름으로 찾은 파일</th></tr>
{''.join(fallback_rows) if fallback_rows else '<tr><td colspan="3">없음</td></tr>'}
</table>
<h1>생성 중 경고 (편지 문구가 넘쳐 글자를 줄인 경우 등)</h1>
<table><tr><th>ID</th><th>이름</th><th>사유</th></tr>
{''.join(warn_rows) if warn_rows else '<tr><td colspan="3">없음</td></tr>'}
</table>
</body></html>"""
    MISMATCH_REPORT.write_text(page, encoding="utf-8")


# ---- 대량 처리 --------------------------------------------------------

def find_letters_file() -> Path:
    """LETTERS_XLSX("letters.xlsx")가 있으면 그걸 쓰고, 없으면 이 폴더 안의
    .xlsx 파일을 자동으로 찾는다. 사용자가 letters.xlsx로 이름을 바꾸지
    않고 원래 파일명 그대로 넣어도 동작하게 하기 위함."""
    if LETTERS_XLSX.exists():
        return LETTERS_XLSX

    candidates = [
        p for p in BASE_DIR.glob("*.xlsx")
        if not p.name.startswith("~$")  # 엑셀이 열려있을 때 생기는 잠금 임시파일 제외
    ]
    if len(candidates) == 1:
        print(f"'{LETTERS_XLSX.name}' 파일은 없지만 '{candidates[0].name}'을(를) "
              f"편지 문구 엑셀로 사용합니다.")
        return candidates[0]
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        print(f"christmas-letter 폴더에 엑셀 파일이 여러 개 있어 어떤 걸 써야 할지 "
              f"알 수 없습니다: {names}")
        print(f"사용할 파일 하나만 남기고 나머지를 지우거나, 그 파일 이름을 "
              f"'{LETTERS_XLSX.name}'로 바꿔주세요.")
        sys.exit(1)

    print(f"{LETTERS_XLSX.name}이(가) 없습니다. christmas-letter 폴더에 "
          f"편지 문구 엑셀 파일(.xlsx)을 넣어주세요.")
    sys.exit(1)


def run_batch():
    letters_path = find_letters_file()

    try:
        letters = load_letters(letters_path)
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)

    if not letters:
        print("엑셀에서 처리할 아동을 찾지 못했습니다 (이름 열이 모두 비어있음).")
        sys.exit(1)

    photo_files = list_asset_filenames(PHOTOS_DIR, limit=10**9)
    drawing_files = list_asset_filenames(DRAWINGS_DIR, limit=10**9)
    print(f"photos 폴더에서 찾은 이미지 파일: {len(photo_files)}개 / "
          f"drawings 폴더에서 찾은 이미지 파일: {len(drawing_files)}개")

    matched, missing, name_fallback = match_children(letters)
    print(f"엑셀 아동 수: {len(letters)}개 / 사진·그림 모두 매칭됨: {len(matched)}개 / "
          f"누락: {len(missing)}개")
    if name_fallback:
        print(f"  참고: {len(name_fallback)}명은 파일명의 ID로는 못 찾아서 이름으로 "
              f"대신 찾았습니다 (파일명의 ID 오타로 보임 — mismatch_report.html에 목록 있음).")

    if not matched and (photo_files or drawing_files):
        sample_ids = [rec["id"] for rec in list(letters.values())[:5]]
        print("  매칭이 하나도 안 됐습니다 — 파일명이 아동 ID와 다른 것 같습니다. 비교해보세요:")
        print(f"    엑셀 ID 예시:        {', '.join(sample_ids)}")
        print(f"    photos 파일명 예시:   {', '.join(photo_files[:5]) or '(없음)'}")
        print(f"    drawings 파일명 예시: {', '.join(drawing_files[:5]) or '(없음)'}")
        print("    파일명이 아동 ID(확장자 제외)와 일치해야 합니다. 예: ID가 "
              f"'{sample_ids[0] if sample_ids else 'MWI0040001'}'이면 "
              f"photos/{sample_ids[0] if sample_ids else 'MWI0040001'}.jpg")

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

    write_mismatch_report(missing, processing_warnings, name_fallback)

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
