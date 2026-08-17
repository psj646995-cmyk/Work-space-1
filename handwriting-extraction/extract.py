#!/usr/bin/env python3
"""
후원 아동 감사레터(PDF) 손글씨 자동 전사 스크립트.

Claude Code CLI(`claude -p`)를 구독 계정으로 호출해 PDF에 담긴 손글씨를
텍스트로 옮기고, 판독 신뢰도와 내용 정책(부적절한 요청 등) 플래그를 함께
매겨 output/results.csv 에 누적 저장한다.

사용법:
    1) input_pdfs/ 폴더에 PDF 파일들을 넣는다.
    2) `claude` CLI가 설치되어 있고 로그인되어 있는지 확인한다.
    3) python3 extract.py 실행. 사용량 한도에 걸려 중단되면,
       나중에 다시 python3 extract.py 를 실행하면 이어서 처리된다.
"""

import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# ---- 설정값 (필요에 따라 조정) -------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input_pdfs"
OUTPUT_CSV = BASE_DIR / "output" / "results.csv"

BATCH_SIZE = 8              # 한 번의 claude 호출에 묶어서 보낼 PDF 개수
CONFIDENCE_THRESHOLD = 90   # 이 값 미만이면 needs_review = TRUE
DELAY_BETWEEN_CALLS = 3     # 호출 사이 대기 시간(초)

# 편지 내용의 특성을 안다면 여기에 한 줄 힌트를 추가하면 판독 정확도가 올라간다.
# 예: "이 편지들은 초등학생 나이의 아동이 쓴 것으로, 철자 실수가 흔하다."
DOMAIN_HINT = ""

CSV_FIELDS = ["filename", "extracted_text", "confidence", "needs_review", "flagged", "flag_reason"]

# ---- 프롬프트 --------------------------------------------------------------

def build_prompt(pdf_paths):
    file_list = "\n".join(f"- {p}" for p in pdf_paths)
    hint = f"\n참고 사항: {DOMAIN_HINT}\n" if DOMAIN_HINT else ""
    return f"""다음은 후원 아동이 후원자에게 쓴 영어 손글씨 감사레터 PDF 파일들이다.
아래 각 파일을 Read 툴로 읽고 다음 세 가지를 수행하라.

1. 손글씨를 최대한 정확하게 영어 텍스트로 옮겨라. 철자나 문법을 임의로
   교정하지 말고 쓰여진 그대로 옮겨라. 판독이 어려운 단어는 최선의
   추측값을 적어라.
2. 전체 판독에 대한 신뢰도를 0~100 사이의 정수로 매겨라(글씨가 깨끗하고
   확신이 높으면 높은 점수, 흐리거나 판독이 애매하면 낮은 점수).
3. 편지 내용에 다음과 같이 감사레터에 부적절한 내용이 있는지 판단하라:
   금전이나 선물을 직접 요청하는 내용, 전화번호·이메일·SNS 계정·집주소 등
   개인연락처를 교환하자는 요청, 만남이나 방문 약속을 요청하는 내용, 그 외
   위험하거나 부적절해 보이는 내용. 해당 사항이 있으면 flagged를 true로
   하고 flag_reason에 한 문장으로 사유를 적어라. 없으면 flagged는 false,
   flag_reason은 빈 문자열로 하라.
{hint}
대상 파일 (파일명은 정확히 아래에 적힌 그대로 사용하라):
{file_list}

다른 설명이나 코드블록 없이, 아래 형식의 JSON 배열만 출력하라:
[{{"filename": "파일명.pdf", "text": "옮긴 텍스트", "confidence": 0-100, "flagged": true/false, "flag_reason": "사유 또는 빈 문자열"}}]
"""


# ---- claude CLI 호출 --------------------------------------------------------

USAGE_LIMIT_MARKERS = ("usage limit", "rate limit", "quota", "5-hour limit", "weekly limit")


def call_claude(prompt: str) -> str:
    """claude -p 를 호출하고 최종 텍스트 응답을 반환한다."""
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
    )
    combined_output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI 오류 (returncode={result.returncode}): {combined_output[:500]}")

    try:
        envelope = json.loads(result.stdout)
        return envelope.get("result", result.stdout)
    except json.JSONDecodeError:
        return result.stdout


def extract_json_array(text: str):
    """응답 텍스트에서 JSON 배열 부분만 뽑아 파싱한다."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError("응답에서 JSON 배열을 찾지 못했습니다.")


# ---- CSV 입출력 --------------------------------------------------------

def load_already_processed():
    if not OUTPUT_CSV.exists():
        return set()
    with OUTPUT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return {row["filename"] for row in reader}


def append_rows(rows):
    is_new = not OUTPUT_CSV.exists()
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---- 메인 로직 --------------------------------------------------------

def chunk(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main():
    if not INPUT_DIR.exists():
        print(f"입력 폴더가 없습니다: {INPUT_DIR}")
        sys.exit(1)

    all_pdfs = sorted(p.name for p in INPUT_DIR.glob("*.pdf"))
    if not all_pdfs:
        print(f"{INPUT_DIR} 안에 PDF 파일이 없습니다. 먼저 파일을 넣어주세요.")
        sys.exit(1)

    done = load_already_processed()
    remaining = [name for name in all_pdfs if name not in done]

    print(f"전체 PDF: {len(all_pdfs)}개 / 이미 처리됨: {len(done)}개 / 이번에 처리할 대상: {len(remaining)}개")

    if not remaining:
        print("남은 파일이 없습니다. 모두 처리 완료.")
        return

    processed_this_run = 0
    needs_review_count = 0
    flagged_count = 0

    for batch_names in chunk(remaining, BATCH_SIZE):
        batch_paths = [f"input_pdfs/{name}" for name in batch_names]
        prompt = build_prompt(batch_paths)

        print(f"\n배치 처리 중 ({len(batch_names)}개): {', '.join(batch_names)}")

        try:
            raw_response = call_claude(prompt)
            items = extract_json_array(raw_response)
        except Exception as exc:
            message = str(exc).lower()
            if any(marker in message for marker in USAGE_LIMIT_MARKERS):
                print(f"사용량 한도에 도달한 것으로 보입니다: {exc}")
                print("여기까지 결과는 저장되었습니다. 한도가 초기화된 뒤 다시 실행하면 이어서 처리됩니다.")
                break
            print(f"이 배치 처리 중 오류 발생, 다음 배치로 넘어갑니다: {exc}")
            continue

        rows = []
        returned_filenames = set()
        for item in items:
            filename = item.get("filename", "")
            confidence = item.get("confidence", 0)
            flagged = bool(item.get("flagged", False))
            needs_review = confidence < CONFIDENCE_THRESHOLD

            if needs_review:
                needs_review_count += 1
            if flagged:
                flagged_count += 1

            rows.append({
                "filename": filename,
                "extracted_text": item.get("text", ""),
                "confidence": confidence,
                "needs_review": needs_review,
                "flagged": flagged,
                "flag_reason": item.get("flag_reason", ""),
            })
            returned_filenames.add(filename)
            processed_this_run += 1

        missing = set(batch_names) - returned_filenames
        for name in missing:
            print(f"경고: 응답에 '{name}' 결과가 없습니다. 다음 실행 시 다시 시도됩니다.")

        append_rows(rows)
        time.sleep(DELAY_BETWEEN_CALLS)

    total_remaining_after = len(remaining) - processed_this_run
    print("\n--- 실행 요약 ---")
    print(f"이번 실행 처리 건수: {processed_this_run}")
    print(f"남은 건수: {max(total_remaining_after, 0)}")
    print(f"확인필요(신뢰도 {CONFIDENCE_THRESHOLD}% 미만): {needs_review_count}")
    print(f"플래그(내용 우려): {flagged_count}")
    print(f"결과 파일: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
