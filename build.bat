@echo off
setlocal EnableExtensions

:: One-step Windows build. Run from the repo root.
:: Output: dist\TrackAttendance\ (TrackAttendance.exe + _internal\ + deploy.bat),
:: which is the folder to host on a share and run deploy.bat from.

cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo .venv not found. Create it first: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

for /f %%v in ('"%PY%" -c "from version import __version__; print(__version__)"') do set "VER=%%v"
echo Building TrackAttendance v%VER%...

"%PY%" -m PyInstaller TrackAttendance.spec --noconfirm
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

copy /y deploy.bat "dist\TrackAttendance\deploy.bat" >nul
echo.
echo Built TrackAttendance v%VER% -^> dist\TrackAttendance
echo Next: run dist\TrackAttendance\deploy.bat to install on this laptop, or copy the folder to your share.
