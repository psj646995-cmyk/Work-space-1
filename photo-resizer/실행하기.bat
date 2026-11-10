@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo  Photo resizer: shrink photos over 5MB
echo  input  folder : put your photos here
echo  output folder : results appear here
echo ============================================
echo.

set PY=
where python >nul 2>nul && set PY=python
if not defined PY (
    where py >nul 2>nul && set PY=py
)
if not defined PY (
    echo Python was not found on this computer.
    echo Please install it from https://python.org
    echo ^(check "Add python.exe to PATH" during setup^),
    echo then double-click this file again.
    goto :done
)

%PY% -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing Pillow ^(first run only^)...
    %PY% -m pip install --quiet pillow
)
%PY% -c "import pillow_heif" >nul 2>nul
if errorlevel 1 (
    echo Installing HEIC support ^(first run only^)...
    %PY% -m pip install --quiet pillow-heif
)
echo.

%PY% -X utf8 resize.py

:done
echo.
echo ============================================
echo  Finished. Check the output folder.
echo  Press any key to close this window.
echo ============================================
pause >nul
