@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo  크리스마스 편지 자동 합성을 시작합니다...
echo  이 창을 닫지 말고 기다려주세요.
echo ============================================
echo.

set PYCMD=
where python >nul 2>nul
if %ERRORLEVEL%==0 set PYCMD=python
if not defined PYCMD (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 set PYCMD=py
)

if not defined PYCMD (
    echo 이 컴퓨터에서 Python을 찾을 수 없습니다.
    echo https://python.org 에서 설치해주세요.
    echo ^(설치 화면에서 "Add python.exe to PATH"를 꼭 체크하세요^)
    echo 설치 후 이 파일을 다시 더블클릭해주세요.
    goto :done
)

echo 필요한 프로그램 구성요소를 확인/설치하는 중입니다... ^(처음 실행 시 시간이 걸릴 수 있습니다^)
%PYCMD% -m pip install -q -r requirements.txt
if not %ERRORLEVEL%==0 (
    echo.
    echo 구성요소 설치에 실패했습니다. 인터넷 연결을 확인해주세요.
    goto :done
)

echo.
%PYCMD% -X utf8 compose.py
goto :done

:done
echo.
echo ============================================
echo  종료되었습니다.
echo  output 폴더를 열어 결과를 확인해주세요.
echo  아무 키나 누르면 창이 닫힙니다.
echo ============================================
pause >nul
