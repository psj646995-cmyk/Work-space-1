# 크리스마스 편지 자동 합성 도구

후원 아동의 사진, 그림, 편지 문구(엑셀)를 정해진 편지지 템플릿에 자동으로
합쳐서 아동별 완성된 편지 이미지(JPG)를 만들어주는 도구입니다. 사진 400장이
넘어도 폴더에 파일만 채워 넣으면 한 번에 처리됩니다. 별도 API 과금은 없습니다.

## 사전 준비 (한 번만 하면 됨)

**Python 3.9 이상** 설치. Windows는 `python.org/downloads`에서 설치 파일을
받아 설치하되, 설치 화면에서 **"Add python.exe to PATH"** 체크박스를 꼭
체크하세요. (Mac/Linux는 보통 이미 설치되어 있습니다.)

필요한 프로그램 구성요소(reportlab, pypdf, Pillow, openpyxl, PyMuPDF)는
`실행하기.bat`을 실행하면 자동으로 설치됩니다. 직접 설치하려면:
```
pip install -r requirements.txt
```

## 폴더 구조

```
christmas-letter/
├── 실행하기.bat          # (Windows) 더블클릭으로 바로 실행
├── template/template.pdf # 편지지 템플릿 (이미 준비되어 있음, 건드릴 필요 없음)
├── photos/                # 여기에 아동 사진을 넣으세요 ("아동ID.jpg")
├── drawings/               # 여기에 아동 그림을 넣으세요 ("아동ID.jpg")
├── (편지 문구 엑셀).xlsx    # 아무 이름이나 OK (번호/이름/편지 문구 3열)
├── output/
│   ├── ID_이름.jpg          # 완성된 편지 이미지
│   └── mismatch_report.html # 누락되거나 경고가 있는 아동 목록
├── compose.py
├── requirements.txt
└── README.md
```

## 사용 방법

### 1) 편지 문구 엑셀 준비

`christmas-letter` 폴더 바로 아래에 편지 문구 엑셀 파일을 놓으세요.
**파일명을 `letters.xlsx`로 바꿀 필요는 없습니다** — 그 폴더에 `.xlsx`
파일이 하나만 있으면 원래 파일명 그대로 자동으로 찾아서 씁니다 (엑셀 파일이
2개 이상이면 어떤 걸 써야 할지 알려달라는 안내가 뜹니다). 첫 번째 시트에
아래 3개의 열(컬럼) 제목이 정확히 있어야 합니다 (열 순서는 상관없음):

| Child's ID | Child's Name | Letter |
|---|---|---|
| MWI 0040003 | Alesi Yokonia | Dear Sponsor,\nThank you for your support.\nMerry Christmas~ |

- 실제 엑셀의 헤더 이름이 다르면 (예: "ID", "이름", "편지내용" 등)
  `compose.py` 맨 위쪽의 `COLUMN_MAP` 값을 실제 헤더에 맞게 고쳐주세요.
- 한 셀 안에서 줄바꿈된 편지 문구도 그대로 인식됩니다.

### 2) 사진·그림 넣기: `photos/`, `drawings/`

`photos/`, `drawings/` 폴더에 **파일명이 엑셀의 아동 ID(번호)로 시작하도록**
사진과 그림을 넣으세요. 예: ID가 "MWI0040003"이라면 `photos/MWI0040003.jpg`도
되고, `photos/MWI0040003 Alesi Yokonia.jpg`처럼 ID 뒤에 이름이 더 붙어있어도
됩니다(둘 다 인식). 공백·하이픈·언더스코어·대소문자 차이는 자동으로 무시하고
매칭하므로 "MWI 0040003.jpg", "mwi-0040003.jpg"처럼 써도 됩니다. jpg/jpeg/png
모두 지원합니다. (이름은 사람마다 철자/띄어쓰기가 달라질 수 있어 매칭 기준으로
쓰지 않습니다. 카드에 인쇄되는 이름은 엑셀의 이름 열 값을 그대로 사용합니다.)

### 3) 실행하기

**`실행하기.bat` 파일을 더블클릭**하세요. (Mac/Linux는 터미널에서
`cd christmas-letter && python3 compose.py`)

이미 `output/`에 결과 파일이 있는 아동은 자동으로 건너뛰므로, 사진/그림을
나중에 추가로 넣고 다시 실행해도 이미 처리된 아동은 다시 만들지 않습니다.
새로 만들고 싶으면 `output/` 폴더에서 해당 파일을 지우고 다시 실행하세요.

### 4) 결과 확인

- `output/ID_이름.jpg` — 완성된 편지 이미지 (사진 좌측 상단 / 편지 문구 우측
  상단 / 그림 하단 중앙 배치)
- `output/mismatch_report.html` — 사진·그림·편지 문구 중 하나라도 없어서
  건너뛴 아동 목록과, 편지 문구가 너무 길어 글자가 작아지거나 넘쳤을 수
  있는 경우의 경고 목록. 더블클릭하면 브라우저로 열립니다.

## 한 명만 미리 만들어보기 (레이아웃 확인용)

전체를 돌리기 전에 한 명만 만들어서 배치를 확인하고 싶다면:
```
python3 compose.py --single --id "MWI 0040003" --name "ALESI YOKONIA" \
  --photo photos/MWI0040003.jpg --drawing drawings/MWI0040003.jpg \
  --letter "Dear Sponsor,\nThank you for your support.\nMerry Christmas~" \
  --out output/test.jpg
```

## 문제 해결

- **"...이(가) 없습니다"** — `christmas-letter` 폴더 바로 아래에 `.xlsx`
  편지 문구 엑셀 파일이 있는지 확인하세요.
- **"엑셀 파일이 여러 개 있어 어떤 걸 써야 할지 알 수 없습니다"** — 그
  폴더에 `.xlsx` 파일이 2개 이상 있다는 뜻입니다. 쓸 파일 하나만 남기고
  나머지를 다른 폴더로 옮기거나 지워주세요.
- **"...컬럼을 찾을 수 없습니다"** — 엑셀의 실제 헤더 목록이 함께 출력됩니다.
  `compose.py` 상단의 `COLUMN_MAP` 값을 그 헤더 이름에 맞게 고치세요.
- **"열려있으면 읽을 수 없습니다"** — 편지 문구 엑셀을 Excel에서 열어둔 채로
  실행하면 나는 오류입니다. 엑셀에서 파일을 닫고 다시 실행해주세요.
- 특정 아동만 사진이 이상하거나 처리가 안 되면 `mismatch_report.html`에
  사유가 함께 표시됩니다. 해당 사진/그림 파일을 확인한 뒤 다시 실행하세요.
- **매칭이 0건이거나 이상하게 적으면** — 실행 중 콘솔에 photos/drawings에서
  실제로 찾은 파일 개수와, 엑셀 ID 예시/실제 파일명 예시가 함께 출력됩니다.
  파일명이 아동 ID와 정확히 같은지(확장자 제외) 비교해보세요.

## 설정 조정

`compose.py` 상단의 값들을 필요에 따라 바꿀 수 있습니다.

- `COLUMN_MAP` — 엑셀의 실제 헤더 이름
- `LAYOUT` — 사진/편지 문구/그림 박스 위치와 크기 (페이지 비율 0~1 기준),
  ID·이름 글자 위치·크기
- `RASTER_DPI`, `JPEG_QUALITY` — 결과 이미지 해상도/품질 (인쇄 품질을 더
  높이려면 `RASTER_DPI`를 300 이상으로 올리세요. 파일 용량이 커집니다.)
- `LETTER_FONT_MAX_SIZE`/`LETTER_FONT_MIN_SIZE` — 편지 문구가 길 때 자동으로
  줄어드는 글자 크기 범위
