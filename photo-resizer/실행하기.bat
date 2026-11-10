@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo  Photo resizer: shrink photos over 5MB
echo  input  folder : put your photos here
echo  output folder : results appear here
echo ============================================
echo.
echo [Step 1/3] Looking for Python...

rem Each candidate is actually RUN, so the fake "python" shortcut
rem from the Microsoft Store (which does nothing) is skipped.
set "PY="
for %%C in ("py -3" "python" "python3") do (
    if not defined PY (
        set "OUT="
        for /f "delims=" %%L in ('%%~C -c "print(4242+1)" 2^>nul') do set "OUT=%%L"
        if "!OUT!"=="4243" (
            set "PY=%%~C"
            echo     %%~C ... OK
        ) else (
            echo     %%~C ... not usable
        )
    )
)

if not defined PY (
    echo.
    echo [ERROR] No working Python was found on this computer.
    echo.
    echo  How to fix:
    echo   1. Go to https://www.python.org/downloads/ and install Python.
    echo   2. On the FIRST install screen, check the box
    echo      "Add python.exe to PATH" before clicking Install.
    echo   3. Close this window and double-click this file again.
    echo.
    echo  If Python is already installed and you still see this:
    echo   Windows Settings - Apps - Advanced app settings -
    echo   App execution aliases - turn OFF "python.exe" and "python3.exe".
    goto :done
)
for /f "delims=" %%V in ('!PY! --version 2^>^&1') do echo     Using: %%V
echo.

echo [Step 2/3] Checking required packages...
!PY! -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo     Pillow ... missing, installing now. Please wait...
    !PY! -m pip install pillow
    !PY! -c "import PIL" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not install Pillow ^(the image library^).
        echo  See the pip messages above for the reason.
        echo  Common causes: no internet connection, or pip missing.
        echo  Try running this in a Command Prompt:  !PY! -m pip install pillow
        goto :done
    )
)
echo     Pillow ... OK

!PY! -c "import pillow_heif" >nul 2>nul
if errorlevel 1 (
    echo     pillow-heif ^(iPhone HEIC photos^) ... missing, installing now...
    !PY! -m pip install pillow-heif
    !PY! -c "import pillow_heif" >nul 2>nul
    if errorlevel 1 (
        echo     [WARNING] pillow-heif could not be installed.
        echo     Only HEIC photos will be skipped. Everything else works.
    ) else (
        echo     pillow-heif ... OK
    )
) else (
    echo     pillow-heif ... OK
)
echo.

echo [Step 3/3] Processing photos...
echo.
!PY! -X utf8 resize.py
if errorlevel 1 (
    echo.
    echo [ERROR] The resizer stopped with an error. See the messages above.
)

:done
echo.
echo ============================================
echo  Done. Check the output folder.
echo  A full record is saved in log.txt
echo  Press any key to close this window.
echo ============================================
pause >nul
