"""
사진 용량 줄이기 (5MB 이하로)

- input 폴더의 사진 중 5MB 이하인 것은 손대지 않고 그대로 output 으로 복사합니다.
- 5MB 를 넘는 사진만, 화질을 최대한 유지하면서 5MB 미만으로 줄여 output 에 저장합니다.
  1) 먼저 해상도는 그대로 두고 JPEG 품질만 살짝 낮춰봅니다 (95 -> 85).
  2) 그래도 크면 그때 해상도를 필요한 만큼만 줄입니다.
- 촬영 정보(EXIF: 날짜, 회전 방향 등)와 색상 프로필은 유지합니다.
"""

import io
import math
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    print("Pillow 가 설치되어 있지 않습니다. 실행하기.bat 으로 실행하거나")
    print("  pip install pillow")
    print("를 먼저 실행해 주세요.")
    sys.exit(1)

# HEIC(아이폰 사진) 지원 - 설치되어 있으면 사용
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_OK = True
except Exception:
    HEIC_OK = False

Image.MAX_IMAGE_PIXELS = None  # 아주 큰 사진도 열 수 있게

BASE = Path(__file__).resolve().parent
INPUT_DIR = BASE / "input"
OUTPUT_DIR = BASE / "output"

# 사이트마다 5MB 를 5,000,000 바이트로 보기도 하고 5,242,880 바이트로 보기도 해서
# 더 엄격한 5,000,000 기준으로 판단하고, 결과는 여유 있게 4,900,000 이하로 만듭니다.
LIMIT = 5_000_000
TARGET = 4_900_000

BEST_QUALITY = 95
MIN_QUALITY = 85  # 이보다 낮추느니 해상도를 조금 줄이는 게 화질이 더 좋습니다

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}


def human(n: int) -> str:
    return f"{n / 1_000_000:.2f}MB"


def prepare(img: Image.Image) -> Image.Image:
    """JPEG 로 저장할 수 있는 형태(RGB)로 바꿉니다. 투명 배경은 흰색으로."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        return bg
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def encode(img: Image.Image, quality: int, extra: dict) -> bytes:
    buf = io.BytesIO()
    img.save(
        buf,
        "JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
        subsampling=2,  # 4:2:0 - 휴대폰 카메라 원본과 같은 방식
        **extra,
    )
    return buf.getvalue()


def best_quality_that_fits(img: Image.Image, extra: dict):
    """해상도 고정 상태에서 TARGET 이하가 되는 가장 높은 품질을 찾습니다."""
    lo, hi = MIN_QUALITY, BEST_QUALITY
    best = None
    while lo <= hi:
        q = (lo + hi) // 2
        data = encode(img, q, extra)
        if len(data) <= TARGET:
            best = (q, data)
            lo = q + 1
        else:
            hi = q - 1
    return best


def compress(src: Path):
    with Image.open(src) as opened:
        opened.load()
        exif = opened.info.get("exif")
        icc = opened.info.get("icc_profile")
        if src.suffix.lower() in (".heic", ".heif"):
            # HEIC 는 회전 정보를 미리 적용해 두는 편이 안전합니다
            opened = ImageOps.exif_transpose(opened)
            exif = None
        img = prepare(opened)

    extra = {}
    if exif:
        extra["exif"] = exif
    if icc:
        extra["icc_profile"] = icc

    original_size = img.size
    scale = 1.0
    for _ in range(30):
        if scale < 1.0:
            w = max(1, round(original_size[0] * scale))
            h = max(1, round(original_size[1] * scale))
            work = img.resize((w, h), Image.LANCZOS)
        else:
            work = img

        found = best_quality_that_fits(work, extra)
        if found:
            q, data = found
            return data, q, work.size, original_size

        # 최소 품질에서도 크다면, 넘친 비율만큼 해상도를 줄여서 다시 시도
        size_at_min = len(encode(work, MIN_QUALITY, extra))
        ratio = math.sqrt(TARGET / size_at_min) * 0.97
        scale *= min(ratio, 0.95)

    # 혹시 EXIF 자체가 너무 큰 특이한 경우를 대비한 마지막 수단
    extra.pop("exif", None)
    data = encode(img.resize((max(1, img.width // 2), max(1, img.height // 2)), Image.LANCZOS), MIN_QUALITY, extra)
    return data, MIN_QUALITY, (img.width // 2, img.height // 2), original_size


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


class Tee:
    """화면에 출력하면서 같은 내용을 log.txt 에도 저장합니다."""

    def __init__(self, stream, path: Path):
        self.stream = stream
        self.file = open(path, "w", encoding="utf-8")

    def write(self, text):
        self.stream.write(text)
        self.stream.flush()
        self.file.write(text)
        self.file.flush()

    def flush(self):
        self.stream.flush()
        self.file.flush()


def main():
    sys.stdout = Tee(sys.stdout, BASE / "log.txt")
    sys.stderr = sys.stdout

    import PIL

    print("[점검] Python  :", sys.version.split()[0], f"({sys.executable})")
    print("[점검] Pillow  :", PIL.__version__, "- OK")
    print("[점검] HEIC 지원:", "OK" if HEIC_OK else "없음 (아이폰 HEIC 사진만 처리 못 함, 나머지는 정상)")
    print("[점검] input 폴더 :", INPUT_DIR)
    print("[점검] output 폴더:", OUTPUT_DIR)
    print()

    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    files = sorted(
        p for p in INPUT_DIR.rglob("*")
        if p.is_file() and not p.name.startswith(".") and p.name.lower() != "desktop.ini"
    )
    if not files:
        print("[오류] input 폴더에 사진이 없습니다.")
        print(f"       {INPUT_DIR}")
        print("       위 폴더에 사진을 넣고 다시 실행해 주세요.")
        return

    big = sum(1 for p in files if p.stat().st_size > LIMIT)
    copied = shrunk = failed = 0
    print(f"총 {len(files)}개 파일 (5MB 초과 {big}개는 줄이고, 나머지 {len(files) - big}개는 그대로 복사)\n")

    for i, src in enumerate(files, 1):
        rel = src.relative_to(INPUT_DIR)
        size = src.stat().st_size
        prefix = f"[{i}/{len(files)}] {rel}"

        try:
            if size <= LIMIT:
                dst = OUTPUT_DIR / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
                print(f"{prefix}  {human(size)}  -> 그대로 복사")
                continue

            if src.suffix.lower() not in IMAGE_EXTS:
                print(f"{prefix}  {human(size)}  -> 사진 파일이 아니라서 건너뜀")
                failed += 1
                continue

            if src.suffix.lower() in (".heic", ".heif") and not HEIC_OK:
                print(f"{prefix}  -> HEIC 를 열 수 없음 (pip install pillow-heif 필요)")
                failed += 1
                continue

            print(f"{prefix}  {human(size)}  -> 줄이는 중...", flush=True)
            data, q, new_dim, old_dim = compress(src)
            if src.suffix.lower() in (".jpg", ".jpeg"):
                dst = OUTPUT_DIR / rel  # 원래 파일 이름 그대로
            else:
                # PNG/HEIC 등은 JPG 로 바뀌므로 같은 이름이 겹치지 않게
                dst = unique_path((OUTPUT_DIR / rel).with_suffix(".jpg"))
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            shutil.copystat(src, dst)  # 파일 날짜 유지

            resized = "" if new_dim == old_dim else f", 해상도 {old_dim[0]}x{old_dim[1]} -> {new_dim[0]}x{new_dim[1]}"
            print(f"{prefix}  {human(size)} -> {human(len(data))}  완료 (품질 {q}{resized})")
            shrunk += 1
        except Exception as e:
            print(f"{prefix}  -> [오류] {type(e).__name__}: {e}")
            failed += 1

    print("\n==========================================")
    print(f" 그대로 복사: {copied}개")
    print(f" 용량 줄임:   {shrunk}개")
    if failed:
        print(f" 실패/건너뜀: {failed}개 (위 목록 확인)")
    print(f" 결과 폴더:   {OUTPUT_DIR}")
    print(f" 기록 파일:   {BASE / 'log.txt'}")
    print("==========================================")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        print("\n[오류] 예상치 못한 문제로 멈췄습니다. 아래 내용을 그대로 알려주세요:\n")
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)
