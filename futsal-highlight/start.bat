@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo  풋살 하이라이트 / 경기 분석 도구
echo ============================================
echo.

set PYCMD=
where python >nul 2>nul
if %ERRORLEVEL%==0 set PYCMD=python
if defined PYCMD goto :havepython

where py >nul 2>nul
if %ERRORLEVEL%==0 set PYCMD=py
if defined PYCMD goto :havepython

echo Python이 설치되어 있지 않습니다.
echo https://python.org 에서 설치하세요.
echo 설치 화면에서 "Add python.exe to PATH"를 꼭 체크하세요.
echo 설치 후 이 파일을 다시 더블클릭하세요.
goto :end

:havepython
where ffmpeg >nul 2>nul
if %ERRORLEVEL%==0 goto :ffmpegok
echo [주의] ffmpeg가 설치되어 있지 않은 것 같습니다.
echo        https://ffmpeg.org/download.html 에서 받아 PATH에 추가해야
echo        영상 자르기/썸네일 기능이 동작합니다. 일단 계속 진행합니다...
echo.

:ffmpegok
echo 필요한 프로그램을 확인하고 있습니다...
echo (처음 실행할 때는 몇 분 정도 걸릴 수 있습니다. 창을 닫지 말고 기다려주세요)
echo.
%PYCMD% -m pip install -r requirements.txt -q
if not %ERRORLEVEL%==0 (
    echo.
    echo 설치 중 문제가 발생했습니다. 인터넷 연결을 확인하고 다시 시도해보세요.
    goto :end
)

echo.
echo  1^) 하이라이트 모드   골 장면 후보를 클립으로 추출
echo  2^) 경기 분석 모드    터치/슈팅 후보를 HTML 리포트로 정리
echo.
set MODE_CHOICE=
set /p MODE_CHOICE=번호를 입력하세요 (1 또는 2):

set MODE=
if "%MODE_CHOICE%"=="1" set MODE=highlight
if "%MODE_CHOICE%"=="2" set MODE=analyze

if not defined MODE (
    echo 1 또는 2만 입력할 수 있습니다.
    goto :end
)

set VIDEO=
for %%F in (input_videos\*.mp4 input_videos\*.mov input_videos\*.avi input_videos\*.mkv) do (
    if not defined VIDEO set VIDEO=%%F
)

if not defined VIDEO (
    echo input_videos 폴더에 영상 파일을 넣고 다시 실행하세요.
    goto :end
)

echo.
echo 사용할 영상: %VIDEO%
echo 모드: %MODE%
echo.

%PYCMD% run.py --mode %MODE% "%VIDEO%" --output-dir output\%MODE%

echo.
echo ============================================
echo  완료되었습니다.
echo  output\%MODE% 폴더를 확인하세요.
echo ============================================

:end
echo.
pause >nul
