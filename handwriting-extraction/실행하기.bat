@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo ============================================
echo  [B] Handwriting extraction
echo  Please keep this window open until it finishes.
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
echo [Step 2] Checking the Claude Code program...
where claude >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] The "claude" program ^(Claude Code^) was not found.
    echo  This tool needs Claude Code and a paid Claude plan ^(Pro or higher^).
    echo  See the read-me file for how to install and log in.
    goto :done
)
echo     claude ... OK
echo.
echo [Step 3] Reading the handwriting...
echo  Please keep this window OPEN.
echo  If it hits a usage limit, it will wait and retry automatically.
echo.
!PY! -X utf8 extract.py
if errorlevel 1 echo [ERROR] The program stopped with an error. See the messages above.

:done
echo.
echo ============================================
echo  Finished or stopped.
echo  Open the output folder and check results.html
echo  Press any key to close this window.
echo ============================================
pause >nul
