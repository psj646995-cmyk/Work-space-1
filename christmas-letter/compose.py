#!/usr/bin/env python3
"""
후원 아동 크리스마스 편지 자동 합성 스크립트.

사진 / 그림 / 편지 문구(엑셀) / 편지지 템플릿(PDF) 네 가지 재료를 받아,
아동별로 완성된 편지 PDF를 만든다. 템플릿은 그대로(벡터) 유지한 채 그 위에
사진·그림·글자만 겹쳐 그리므로 인쇄 품질이 원본 그대로 유지된다.

사용법:
    1) 대량 처리: photos/, drawings/ 폴더에 "ID_이름.jpg" 형식 파일을 넣고,
       letters.xlsx를 채운 뒤 `python3 compose.py` 실행.
    2) 배치 하나만 미리 확인(레이아웃 조정용):
       python3 compose.py --single --id "MWI 0040003" --name "ALESI YOKONIA" \
           --photo photos/x.jpg --drawing drawings/y.jpg \
           --letter "Dear Sponsor,\nThank you for your support.\nMerry Christmas~" \
           --out output/test.pdf
"""

import argparse
import io
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageOps

# ---- 설정값 (필요에 따라 조정) -------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "template" / "template.pdf"
PHOTOS_DIR = BASE_DIR / "photos"
DRAWINGS_DIR = BASE_DIR / "drawings"
LETTERS_XLSX = BASE_DIR / "letters.xlsx"
OUTPUT_DIR = BASE_DIR / "output"
FONT_PATH = BASE_DIR / "assets" / "fonts" / "PatrickHand-Regular.ttf"
HANDWRITING_FONT_NAME = "PatrickHand"

# 편지 문구 엑셀의 실제 컬럼명이 오면 여기만 바꾸면 된다.
COLUMN_MAP = {
    "id": "Child's ID",
    "name": "Child's Name",
    "letter": "Letter",
}

# ---- 레이아웃 (페이지 비율 기준 0~1, 좌상단이 원점) -----------------------
# 완성 예시를 보고 눈대중으로 잡은 1차 값. 실제 출력물을 보고 조정할 것.

LAYOUT = {
    # 단순 텍스트 위치: (x, y) — y는 글자 베이스라인
    # id_value/name_value의 x,y는 template.pdf를 실제로 렌더링해 라벨 위치를
    # 픽셀 단위로 측정해서 얻은 값 (assets 없이도 바뀌지 않는 값들).
    "id_value": {"x": 0.565, "y": 0.1188, "font": "Helvetica", "size": 16},
    "name_value": {"x": 0.565, "y": 0.1624, "font": "Helvetica-Bold", "size": 18},
    # 이미지/텍스트 박스: (x0, y0, x1, y1) — (x0,y0)=좌상단, (x1,y1)=우하단
    "drawing_box": (0.08, 0.27, 0.47, 0.55),
    "photo_box": (0.56, 0.465, 0.94, 0.735),
    "letter_box": (0.08, 0.565, 0.75, 0.66),
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
    추가로 줄바꿈한다."""
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
    if overflow:
        print(f"  경고: 편지 문구가 할당된 영역보다 깁니다 (최소 글자 크기 {min_size}pt로도 넘침). "
              f"문구를 줄이거나 letter_box를 넓혀야 합니다.")

    c.setFont(font_name, size)
    c.setFillColorRGB(*LETTER_TEXT_COLOR)
    cursor_y = y_bottom + h - leading  # 첫 줄 베이스라인 (박스 상단에서 한 줄 내려온 위치)
    for line in lines:
        c.drawString(x, cursor_y, line)
        cursor_y -= leading


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


def compose_one(child_id: str, child_name: str, letter_text: str,
                 photo_path: Path, drawing_path: Path, output_path: Path):
    register_fonts()

    reader = PdfReader(str(TEMPLATE_PATH))
    page = reader.pages[0]
    page_w = float(page.mediabox.width)
    page_h = float(page.mediabox.height)

    overlay_buf = io.BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=(page_w, page_h))

    draw_value(c, child_id, LAYOUT["id_value"], page_w, page_h)
    draw_value(c, child_name.upper(), LAYOUT["name_value"], page_w, page_h)

    drawing_img = load_and_normalize_image(drawing_path)
    place_image(c, drawing_img, LAYOUT["drawing_box"], page_w, page_h)

    photo_img = load_and_normalize_image(photo_path)
    place_image(c, photo_img, LAYOUT["photo_box"], page_w, page_h)

    wrap_and_fit_text(c, letter_text, LAYOUT["letter_box"], page_w, page_h)

    c.save()
    overlay_buf.seek(0)

    overlay_reader = PdfReader(overlay_buf)
    page.merge_page(overlay_reader.pages[0])

    writer = PdfWriter()
    writer.add_page(page)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)


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

    print("대량 처리 모드는 letters.xlsx가 도착한 뒤 이어서 구현합니다.")
    print("지금은 --single 옵션으로 레이아웃 확인용 샘플 1건을 만들 수 있습니다.")


if __name__ == "__main__":
    main()
