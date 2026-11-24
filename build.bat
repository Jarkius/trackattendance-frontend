@echo off
setlocal EnableExtensions

:: One-step Windows build + install. Run from the repo root.
::   1. Builds dist\TrackAttendance\ (onedir: TrackAttendance.exe + _internal\)
::   2. Copies deploy.bat next to the exe
::   3. Runs that deploy.bat, which copies the build to C:\TrackAttendance
::      (keeps the station's data\, database, logs and .env) and refreshes the
::      desktop shortcut.
:: Pass "nodeploy" to build only:  build.bat nodeploy

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

:: Event voice clips: a repo-root voices\ folder (.mp3/.wav) is shipped next to the
:: exe, where it replaces the bundled assets\voices.
if exist "voices\" (
    xcopy /e /i /y /q "voices" "dist\TrackAttendance\voices\" >nul
    echo Included event voices\ folder.
)
echo.
echo Built TrackAttendance v%VER% -^> dist\TrackAttendance

if /i "%~1"=="nodeploy" (
    echo Skipping install ^(nodeploy^).
    exit /b 0
)

:: A running copy locks C:\TrackAttendance\TrackAttendance.exe and _internal
tasklist /fi "imagename eq TrackAttendance.exe" 2>nul | find /i "TrackAttendance.exe" >nul
if not errorlevel 1 (
    echo.
    echo TrackAttendance.exe is running. Close it, then run: dist\TrackAttendance\deploy.bat
    exit /b 1
)

echo Installing to C:\TrackAttendance...
call "dist\TrackAttendance\deploy.bat"
exit /b %ERRORLEVEL%
