@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo  [C] Photo resizer: shrink photos over 5MB
echo  input  folder : put your photos here
echo  output folder : results appear here
echo ============================================
echo.
echo [Step 1] Looking for Python...
rem Each candidate is actually RUN. The fake "python" shortcut from the
rem Microsoft Store (it only prints "Python" and does nothing) is skipped.
set "PY="
call :trycmd "py -3"
call :trycmd "python"
call :trycmd "python3"
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "%ProgramFiles(x86)%\Python3*" "%SystemDrive%\Python3*" "%UserProfile%\anaconda3" "%UserProfile%\miniconda3" "%LocalAppData%\anaconda3" "%ProgramData%\anaconda3" "%ProgramData%\miniconda3") do (
    if exist "%%~D\python.exe" call :tryexe "%%~D\python.exe"
)
if defined PY goto :havepy
echo.
echo [ERROR] No working Python was found ^(checked PATH and the usual install folders^).
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

:trycmd
if defined PY goto :eof
set "OUT="
for /f "delims=" %%L in ('%~1 -c "print(4242+1)" 2^>nul') do set "OUT=%%L"
if not "!OUT!"=="4243" goto :trycmd_no
set "PY=%~1"
echo     %~1 ... OK
goto :eof
:trycmd_no
echo     %~1 ... not usable
goto :eof

:tryexe
if defined PY goto :eof
set "OUT="
for /f "delims=" %%L in ('call "%~1" -c "print(4242+1)" 2^>nul') do set "OUT=%%L"
if not "!OUT!"=="4243" goto :tryexe_no
set "PY="%~1""
echo     %~1 ... OK
goto :eof
:tryexe_no
echo     %~1 ... not usable
goto :eof

:havepy
for /f "delims=" %%V in ('call !PY! --version 2^>^&1') do echo     Using: %%V
echo.
echo [Step 2] Checking required packages...
!PY! -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo     Pillow ... missing, installing now. Please wait...
    !PY! -m pip install --disable-pip-version-check pillow
    !PY! -c "import PIL" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo [ERROR] Could not install Pillow ^(the image library^).
        echo  See the pip messages above for the reason.
        echo  Common cause: no internet connection.
        goto :done
    )
)
echo     Pillow ... OK
!PY! -c "import pillow_heif" >nul 2>nul
if errorlevel 1 (
    echo     pillow-heif ^(iPhone HEIC photos^) ... missing, installing now...
    !PY! -m pip install --disable-pip-version-check pillow-heif
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
echo [Step 3] Processing photos...
echo.
!PY! -X utf8 resize.py
if errorlevel 1 echo [ERROR] The resizer stopped with an error. See the messages above.

:done
echo.
echo ============================================
echo  Done. Check the output folder.
echo  A full record is saved in log.txt
echo  Press any key to close this window.
echo ============================================
pause >nul
