#!/usr/bin/env python3
"""
후원 아동 감사레터(PDF) 손글씨 자동 전사 스크립트.

Claude Code CLI(`claude -p`)를 구독 계정으로 호출해 PDF에 담긴 손글씨를
텍스트로 옮기고, 판독 신뢰도·언어·내용 정책(부적절한 요청 등) 플래그를
함께 매겨 output/results.html 리포트로 정리한다.

사용법 (Windows는 실행하기.bat 더블클릭으로 대체 가능):
    1) input_pdfs/ 폴더에 PDF 파일들을 넣는다.
    2) `claude` CLI가 설치되어 있고 로그인되어 있는지 확인한다.
    3) python3 extract.py 실행.
    4) output/results.html 을 브라우저로 열어서 확인한다.

사용량 한도(5시간/주간)에 걸리면 스크립트를 종료하지 않고, 한도가
초기화될 것으로 보이는 시각까지 자동으로 대기했다가 스스로 재시도한다.
그냥 창을 열어둔 채로 두면 된다. (도중에 그만두고 싶으면 창을 닫거나
Ctrl+C를 누르면 되고, 나중에 다시 실행해도 이어서 처리된다.)
"""

import datetime
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# ---- 설정값 (필요에 따라 조정) -------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input_pdfs"
OUTPUT_DIR = BASE_DIR / "output"
RESULTS_JSONL = OUTPUT_DIR / "results.jsonl"   # 처리 결과 원본 (재개 판단 기준)
RESULTS_HTML = OUTPUT_DIR / "results.html"     # 사람이 보는 최종 리포트

BATCH_SIZE = 8              # 한 번의 claude 호출에 묶어서 보낼 PDF 개수
CONFIDENCE_THRESHOLD = 90   # 이 값 미만이면 needs_review = TRUE
DELAY_BETWEEN_CALLS = 3     # 호출 사이 대기 시간(초)

# 사용량 한도 오류 메시지에서 정확한 재개 시각을 못 찾았을 때 기본으로
# 기다리는 시간(초). 그 시간이 지나면 자동으로 다시 시도한다.
DEFAULT_RETRY_WAIT_SECONDS = 30 * 60
# 대기하는 동안 "아직 살아있다"는 메시지를 몇 초마다 찍을지
HEARTBEAT_INTERVAL_SECONDS = 10 * 60

# 편지 내용의 특성을 안다면 여기에 한 줄 힌트를 추가하면 판독 정확도가 올라간다.
# 예: "이 편지들은 초등학생 나이의 아동이 쓴 것으로, 철자 실수가 흔하다."
DOMAIN_HINT = ""

RESULT_FIELDS = ["filename", "extracted_text", "confidence", "needs_review", "language", "flagged", "flag_reason"]

# ---- 프롬프트 --------------------------------------------------------------

def build_prompt(pdf_paths):
    file_list = "\n".join(f"- {p}" for p in pdf_paths)
    hint = f"\n참고 사항: {DOMAIN_HINT}\n" if DOMAIN_HINT else ""
    return f"""다음은 후원 아동이 후원자에게 쓴 손글씨 감사레터 PDF 파일들이다.
편지는 영어로 쓰여 있을 수도 있고, 아동의 현지어(예: Chichewa 등)로 쓰여
있을 수도 있다. 아래 각 파일을 Read 툴로 읽고 다음 네 가지를 수행하라.

1. 손글씨를 쓰여진 언어 그대로, 최대한 정확하게 텍스트로 옮겨라(번역하지
   말 것). 철자나 문법을 임의로 교정하지 말고 쓰여진 그대로 옮겨라.
   판독이 어려운 단어는 최선의 추측값을 적어라.
2. 편지에 주로 사용된 언어를 짧게 적어라 (예: "English", "Chichewa",
   "Mixed" 등).
3. 전체 판독에 대한 신뢰도를 0~100 사이의 정수로 매겨라(글씨가 깨끗하고
   확신이 높으면 높은 점수, 흐리거나 판독이 애매하거나 익숙하지 않은
   언어라 확신이 낮으면 낮은 점수).
4. 편지 내용에 다음과 같이 감사레터에 부적절한 내용이 있는지 판단하라:
   금전이나 선물을 직접 요청하는 내용, 전화번호·이메일·SNS 계정·집주소 등
   개인연락처를 교환하자는 요청, 만남이나 방문 약속을 요청하는 내용, 그 외
   위험하거나 부적절해 보이는 내용. 해당 사항이 있으면 flagged를 true로
   하고 flag_reason에 한 문장으로 사유를 적어라. 없으면 flagged는 false,
   flag_reason은 빈 문자열로 하라.
{hint}
대상 파일 (파일명은 정확히 아래에 적힌 그대로 사용하라):
{file_list}

다른 설명이나 코드블록 없이, 아래 형식의 JSON 배열만 출력하라:
[{{"filename": "파일명.pdf", "text": "옮긴 텍스트", "language": "언어", "confidence": 0-100, "flagged": true/false, "flag_reason": "사유 또는 빈 문자열"}}]
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


def parse_retry_wait_seconds(message: str) -> int:
    """사용량 한도 오류 메시지에서 '언제 다시 시도해야 하는지' 최대한 추측한다.
    정확한 시각을 못 찾으면 DEFAULT_RETRY_WAIT_SECONDS를 반환한다.
    (claude CLI 버전에 따라 오류 문구가 다를 수 있어 최선을 다한 추정치다.)
    """
    now = time.time()

    # 1) 10~13자리 유닉스 타임스탬프(초 또는 밀리초)
    m = re.search(r"\b(\d{10,13})\b", message)
    if m:
        ts = int(m.group(1))
        if ts > 10 ** 12:
            ts //= 1000
        if ts > now:
            return int(ts - now) + 30

    # 2) "in N hour(s)" / "in N minute(s)"
    m = re.search(r"in\s+(\d+)\s*hour", message, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 3600 + 60
    m = re.search(r"in\s+(\d+)\s*minute", message, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 60 + 30

    # 3) "HH:MM" 형태의 다음 재개 시각
    m = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", message, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23:
            now_dt = datetime.datetime.now()
            target = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now_dt:
                target += datetime.timedelta(days=1)
            return int((target - now_dt).total_seconds()) + 30

    return DEFAULT_RETRY_WAIT_SECONDS


def sleep_with_heartbeat(total_seconds: int):
    """대기하는 동안 주기적으로 진행 상황을 출력해 '멈춘 게 아니다'를 알려준다."""
    remaining = total_seconds
    while remaining > 0:
        step = min(HEARTBEAT_INTERVAL_SECONDS, remaining)
        time.sleep(step)
        remaining -= step
        if remaining > 0:
            print(f"  ...아직 대기 중입니다 (남은 시간 약 {max(remaining // 60, 1)}분). 창을 그대로 두시면 자동으로 재시도합니다.")


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


# ---- 결과 저장(JSONL, 재개 판단용) -----------------------------------------

def load_already_processed():
    if not RESULTS_JSONL.exists():
        return set()
    names = set()
    with RESULTS_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            names.add(json.loads(line)["filename"])
    return names


def load_all_results():
    if not RESULTS_JSONL.exists():
        return []
    entries = []
    with RESULTS_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def append_results(rows):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with RESULTS_JSONL.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---- HTML 리포트 생성 --------------------------------------------------------

PAGE_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>감사레터 추출 리포트</title>
<style>
  :root {
    --bg: #eceee6;
    --surface: #ffffff;
    --surface-2: #f4f5ef;
    --ink: #1e232a;
    --ink-soft: #5c6470;
    --hairline: #d8dbd0;
    --accent: #2b4c7e;
    --accent-soft: #dce6f2;
    --good: #3f7d4b;
    --good-soft: #e4efe4;
    --warn: #a06a1c;
    --warn-soft: #f3e6cd;
    --bad: #a83a3a;
    --bad-soft: #f5e1e1;
    --serif: Georgia, 'Iowan Old Style', 'Palatino Linotype', 'Book Antiqua', serif;
    --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    --mono: ui-monospace, 'SF Mono', 'Cascadia Mono', Menlo, Consolas, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14171c; --surface: #1b1f26; --surface-2: #20252d;
      --ink: #e7e9ee; --ink-soft: #a7adb8; --hairline: #2c313b;
      --accent: #8fb2e3; --accent-soft: #26364d;
      --good: #6fbf7c; --good-soft: #1c2f22;
      --warn: #d9a441; --warn-soft: #362b16;
      --bad: #e08080; --bad-soft: #38201f;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans); line-height: 1.5; -webkit-font-smoothing: antialiased; }
  .page { max-width: 840px; margin: 0 auto; padding: 56px 24px 96px; }
  header.masthead { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
  .eyebrow { font-family: var(--mono); font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent); }
  h1 { font-family: var(--serif); font-weight: 400; font-size: 34px; margin: 0; text-wrap: balance; }
  .dek { font-size: 15px; color: var(--ink-soft); max-width: 62ch; margin: 4px 0 0; }
  .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--hairline); border: 1px solid var(--hairline); border-radius: 4px; overflow: hidden; margin: 36px 0 44px; }
  .stat { background: var(--surface); padding: 18px 16px; display: flex; flex-direction: column; gap: 4px; }
  .stat .n { font-family: var(--serif); font-size: 28px; font-variant-numeric: tabular-nums; }
  .stat .n.good { color: var(--good); } .stat .n.warn { color: var(--warn); } .stat .n.bad { color: var(--bad); }
  .stat .label { font-size: 11.5px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-soft); }
  .log { display: flex; flex-direction: column; }
  .entry { padding: 28px 0; border-top: 1px solid var(--hairline); display: grid; grid-template-columns: 168px 1fr; gap: 24px; }
  .entry:last-child { border-bottom: 1px solid var(--hairline); }
  .entry-meta { display: flex; flex-direction: column; gap: 10px; }
  .child-id { font-family: var(--mono); font-size: 12px; color: var(--ink-soft); letter-spacing: 0.03em; word-break: break-all; }
  .meter-wrap { display: flex; flex-direction: column; gap: 4px; }
  .meter-label { display: flex; justify-content: space-between; font-size: 11px; color: var(--ink-soft); }
  .meter-value { font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--ink); }
  .meter { height: 5px; border-radius: 3px; background: var(--surface-2); border: 1px solid var(--hairline); overflow: hidden; }
  .meter > span { display: block; height: 100%; border-radius: 3px; }
  .meter > span.good { background: var(--good); } .meter > span.warn { background: var(--warn); } .meter > span.bad { background: var(--bad); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { font-size: 11px; letter-spacing: 0.02em; padding: 3px 8px; border-radius: 100px; white-space: nowrap; }
  .chip.clear { background: var(--good-soft); color: var(--good); }
  .chip.review { background: var(--warn-soft); color: var(--warn); }
  .chip.flagged { background: var(--bad-soft); color: var(--bad); }
  .chip.lang { background: var(--accent-soft); color: var(--accent); }
  .entry-body { min-width: 0; }
  .transcript { font-family: var(--serif); font-size: 16.5px; line-height: 1.65; max-width: 64ch; white-space: pre-line; }
  .review-note { margin-top: 12px; font-size: 13px; color: var(--ink-soft); border-left: 2px solid var(--warn); padding-left: 10px; }
  .flag-note { margin-top: 12px; font-size: 13px; color: var(--bad); border-left: 2px solid var(--bad); padding-left: 10px; }
  footer.colophon { margin-top: 56px; padding-top: 20px; border-top: 1px solid var(--hairline); font-size: 12.5px; color: var(--ink-soft); }
  @media (max-width: 620px) { .entry { grid-template-columns: 1fr; } .summary { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
<div class="page">
  <header class="masthead">
    <span class="eyebrow">__COUNT__건 처리됨</span>
    <h1>감사레터 추출 리포트</h1>
    <p class="dek">extract.py가 자동 생성한 리포트입니다. 확인필요 또는 플래그 항목을 우선 검토하세요.</p>
  </header>
  <section class="summary">
    <div class="stat"><span class="n">__COUNT__</span><span class="label">처리된 레터</span></div>
    <div class="stat"><span class="n good">__PASS_COUNT__</span><span class="label">신뢰도 __THRESHOLD__%+ (통과)</span></div>
    <div class="stat"><span class="n warn">__REVIEW_COUNT__</span><span class="label">확인필요</span></div>
    <div class="stat"><span class="n bad">__FLAG_COUNT__</span><span class="label">내용 플래그</span></div>
  </section>
  <div class="log">
__ENTRIES__
  </div>
  <footer class="colophon">
    <span>내용 플래그 기준: 금전·선물 직접 요청 / 개인연락처 교환 요청 / 만남·방문 약속 요청 / 기타 부적절한 내용. 이 판정은 참고용 스크리닝이며 최종 확인은 사람이 진행해야 합니다.</span>
  </footer>
</div>
</body>
</html>
"""

ENTRY_TEMPLATE = """    <article class="entry">
      <div class="entry-meta">
        <span class="child-id">__FILENAME__</span>
        <div class="meter-wrap">
          <div class="meter-label"><span>신뢰도</span><span class="meter-value">__CONFIDENCE__%</span></div>
          <div class="meter"><span class="__METER_CLASS__" style="width:__CONFIDENCE__%"></span></div>
        </div>
        <div class="chips">
          __REVIEW_CHIP__
          __FLAG_CHIP__
          __LANG_CHIP__
        </div>
      </div>
      <div class="entry-body">
        <p class="transcript">__TEXT__</p>__NOTES__
      </div>
    </article>"""


def meter_class(confidence):
    if confidence >= CONFIDENCE_THRESHOLD:
        return "good"
    if confidence >= 70:
        return "warn"
    return "bad"


def render_entry(item):
    confidence = item.get("confidence", 0)
    needs_review = item.get("needs_review", confidence < CONFIDENCE_THRESHOLD)
    flagged = item.get("flagged", False)
    language = (item.get("language") or "").strip()

    review_chip = (
        '<span class="chip review">확인필요</span>' if needs_review
        else '<span class="chip clear">통과</span>'
    )
    flag_chip = (
        '<span class="chip flagged">내용 플래그</span>' if flagged
        else '<span class="chip clear">내용 이상없음</span>'
    )
    lang_chip = ""
    if language and language.lower() not in ("english", "en", ""):
        lang_chip = f'<span class="chip lang">{html.escape(language)}</span>'

    notes = ""
    if needs_review:
        notes += f'\n        <p class="review-note">신뢰도 {confidence}%로 낮게 판정되었습니다. 원문과 대조 확인을 권장합니다.</p>'
    if flagged and item.get("flag_reason"):
        notes += f'\n        <p class="flag-note">플래그 사유: {html.escape(item["flag_reason"])}</p>'

    entry_html = ENTRY_TEMPLATE
    entry_html = entry_html.replace("__FILENAME__", html.escape(item.get("filename", "")))
    entry_html = entry_html.replace("__CONFIDENCE__", str(confidence))
    entry_html = entry_html.replace("__METER_CLASS__", meter_class(confidence))
    entry_html = entry_html.replace("__REVIEW_CHIP__", review_chip)
    entry_html = entry_html.replace("__FLAG_CHIP__", flag_chip)
    entry_html = entry_html.replace("__LANG_CHIP__", lang_chip)
    entry_html = entry_html.replace("__TEXT__", html.escape(item.get("extracted_text", "")))
    entry_html = entry_html.replace("__NOTES__", notes)
    return entry_html


def generate_html():
    entries = load_all_results()
    # 플래그 -> 확인필요 -> 나머지 순으로 정렬해 우선순위가 높은 항목이 위로 오게 한다.
    entries.sort(key=lambda e: (
        not e.get("flagged", False),
        not e.get("needs_review", e.get("confidence", 0) < CONFIDENCE_THRESHOLD),
        e.get("filename", ""),
    ))

    pass_count = sum(1 for e in entries if not e.get("needs_review", e.get("confidence", 0) < CONFIDENCE_THRESHOLD))
    review_count = sum(1 for e in entries if e.get("needs_review", e.get("confidence", 0) < CONFIDENCE_THRESHOLD))
    flag_count = sum(1 for e in entries if e.get("flagged", False))

    entries_html = "\n".join(render_entry(e) for e in entries) if entries else "    <p>아직 처리된 레터가 없습니다.</p>"

    page = PAGE_TEMPLATE
    page = page.replace("__COUNT__", str(len(entries)))
    page = page.replace("__PASS_COUNT__", str(pass_count))
    page = page.replace("__REVIEW_COUNT__", str(review_count))
    page = page.replace("__FLAG_COUNT__", str(flag_count))
    page = page.replace("__THRESHOLD__", str(CONFIDENCE_THRESHOLD))
    page = page.replace("__ENTRIES__", entries_html)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_HTML.write_text(page, encoding="utf-8")


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
        generate_html()
        print(f"결과 리포트: {RESULTS_HTML}")
        return

    processed_this_run = 0
    needs_review_count = 0
    flagged_count = 0

    for batch_names in chunk(remaining, BATCH_SIZE):
        batch_paths = [f"input_pdfs/{name}" for name in batch_names]
        prompt = build_prompt(batch_paths)

        print(f"\n배치 처리 중 ({len(batch_names)}개): {', '.join(batch_names)}")

        items = None
        while True:
            try:
                raw_response = call_claude(prompt)
                items = extract_json_array(raw_response)
                break
            except Exception as exc:
                message = str(exc).lower()
                if any(marker in message for marker in USAGE_LIMIT_MARKERS):
                    wait_seconds = parse_retry_wait_seconds(str(exc))
                    resume_at = datetime.datetime.now() + datetime.timedelta(seconds=wait_seconds)
                    print("사용량 한도에 도달했습니다. 여기까지 결과는 이미 저장되어 있습니다.")
                    print(f"{resume_at.strftime('%H:%M:%S')}쯤 자동으로 다시 시도합니다 (약 {max(wait_seconds // 60, 1)}분 대기). 창은 그대로 두세요.")
                    sleep_with_heartbeat(wait_seconds)
                    print("대기 시간이 끝나 다시 시도합니다...")
                    continue
                print(f"이 배치 처리 중 오류 발생, 다음 배치로 넘어갑니다: {exc}")
                break

        if items is None:
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
                "language": item.get("language", ""),
                "flagged": flagged,
                "flag_reason": item.get("flag_reason", ""),
            })
            returned_filenames.add(filename)
            processed_this_run += 1

        missing = set(batch_names) - returned_filenames
        for name in missing:
            print(f"경고: 응답에 '{name}' 결과가 없습니다. 다음 실행 시 다시 시도됩니다.")

        append_results(rows)
        generate_html()
        time.sleep(DELAY_BETWEEN_CALLS)

    total_remaining_after = len(remaining) - processed_this_run
    print("\n--- 실행 요약 ---")
    print(f"이번 실행 처리 건수: {processed_this_run}")
    print(f"남은 건수: {max(total_remaining_after, 0)}")
    print(f"확인필요(신뢰도 {CONFIDENCE_THRESHOLD}% 미만): {needs_review_count}")
    print(f"플래그(내용 우려): {flagged_count}")
    print(f"결과 리포트: {RESULTS_HTML}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단했습니다. 지금까지 처리된 결과는 저장되어 있으니, 나중에 다시 실행하면 이어서 처리됩니다.")
