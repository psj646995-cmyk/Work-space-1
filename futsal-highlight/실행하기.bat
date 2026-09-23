@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo  풋살 하이라이트 / 경기 분석 도구
echo ============================================
echo.
echo  1) 하이라이트 모드  (골 장면 후보를 클립으로 추출)
echo  2) 경기 분석 모드   (터치/슈팅 후보를 HTML 리포트로 정리)
echo.
set /p MODE_CHOICE="번호를 입력하세요 (1 또는 2): "

if "%MODE_CHOICE%"=="1" (
    set MODE=highlight
) else if "%MODE_CHOICE%"=="2" (
    set MODE=analyze
) else (
    echo 1 또는 2만 입력할 수 있습니다.
    goto :end
)

set VIDEO=
for %%F in (input_videos\*.mp4 input_videos\*.mov input_videos\*.avi input_videos\*.mkv) do (
    if not defined VIDEO set VIDEO=%%F
)

if not defined VIDEO (
    echo input_videos 폴더에 영상 파일(.mp4/.mov/.avi/.mkv)을 넣고 다시 실행하세요.
    goto :end
)

echo.
echo 사용할 영상: %VIDEO%
echo 모드: %MODE%
echo.

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python run.py --mode %MODE% "%VIDEO%" --output-dir output\%MODE%
    goto :done
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py run.py --mode %MODE% "%VIDEO%" --output-dir output\%MODE%
    goto :done
)

echo Python이 설치되어 있지 않습니다.
echo https://python.org 에서 설치하세요.
echo (설치 화면에서 "Add python.exe to PATH"를 꼭 체크하세요)
echo 설치 후 이 파일을 다시 더블클릭하세요.
goto :end

:done
echo.
echo ============================================
echo  완료되었습니다.
echo  output\%MODE% 폴더를 확인하세요.
echo  (경기 분석 모드는 report.html 을 브라우저로 열어보세요)
echo ============================================

:end
echo.
pause >nul
