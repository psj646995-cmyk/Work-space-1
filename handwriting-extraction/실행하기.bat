@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo  감사레터 추출을 시작합니다.
echo  이 창을 닫지 말고 그대로 두세요.
echo  (사용량 한도에 걸려도 자동으로 기다렸다가 재시도합니다)
echo ============================================
echo.

where python >nul 2>nul
if %ERRORLEVEL%==0 (
    python extract.py
    goto :done
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py extract.py
    goto :done
)

echo Python이 설치되어 있지 않은 것 같습니다.
echo https://python.org 에서 설치(설치 시 "Add python.exe to PATH" 체크) 후 다시 실행해주세요.

:done
echo.
echo ============================================
echo  작업이 끝났거나 중단되었습니다.
echo  output 폴더의 results.html 을 열어 결과를 확인하세요.
echo  아무 키나 누르면 이 창이 닫힙니다.
echo ============================================
pause >nul
