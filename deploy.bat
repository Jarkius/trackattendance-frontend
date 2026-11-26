@echo on
setlocal EnableExtensions

:: Run this script from inside the hosted release folder itself (e.g. a
:: network share or mapped drive containing TrackAttendance.exe, _internal\,
:: data\, media\, always-on-screen\, .env). The folder can be dist\TrackAttendance
:: or a prepared C:\TrackAttendance. It deploys "from wherever I am" to this
:: laptop -- nothing to configure per machine, no hardcoded server path.

:: Get path and strip the trailing backslash
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"

set "DEST=C:\TrackAttendance"
set "EXE=%DEST%\TrackAttendance.exe"

if not exist "%SRC%\TrackAttendance.exe" (
    echo TrackAttendance.exe not found next to this script.
    echo Run deploy.bat from inside the release folder ^(next to the .exe^), not the source repo.
    pause
    exit /b 1
)

:: Run from C:\TrackAttendance itself: nothing to copy, just (re)install keep-awake and
:: the shortcut below.
if /i "%SRC%"=="%DEST%" (
    echo Running from %DEST% itself -- skipping the copy.
    goto :after_copy
)

echo Deploying TrackAttendance from %SRC% to %DEST%...

:: Skip local runtime state, so the source can be a release folder OR a used install
:: (e.g. C:\TrackAttendance uploaded to a share): each laptop starts with its own fresh
:: database, logs and exports. exports\ holds backups of test scans with attendee data
:: and must never spread. This script IS copied, so an installed folder can be shared
:: onward with the current deploy.bat.
robocopy "%SRC%" "%DEST%" /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 ^
    /XF "database.db" "database.db-shm" "database.db-wal" "*.log" ^
    /XD "%SRC%\data\backups" "%SRC%\logs" "%SRC%\exports"
set "RC=%ERRORLEVEL%"

:: Robocopy exit codes < 8 are successful variations
if %RC% GEQ 8 (
    echo Copy failed. Exit code=%RC%
    pause
    exit /b %RC%
)

:after_copy

:: Each laptop needs its own station identity -- don't carry over a
:: leftover local database from a previous deploy attempt on this machine.
if exist "%DEST%\data\database.db" (
    echo Existing local database found at %DEST%\data\database.db -- leaving it in place.
    echo Delete it manually first if this laptop should start as a fresh station.
)

:: Keep-awake (always-on-screen): display stays on and the session never locks, without
:: sending keystrokes (scanner input is safe). Installed in this user's Startup folder so it
:: runs at every logon, and started now. The .vbs needs the .ps1 in the same folder.
:: It holds a single-instance mutex, so starting it again is harmless.
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%SRC%\always-on-screen\KeepAwake-Launcher.vbs" (
    copy /y "%SRC%\always-on-screen\KeepAwake-Launcher.vbs" "%STARTUP%\" >nul
    copy /y "%SRC%\always-on-screen\KeepAwake.ps1" "%STARTUP%\" >nul
    start "" wscript.exe "%STARTUP%\KeepAwake-Launcher.vbs"
    echo Keep-awake installed in Startup and started.
) else (
    echo always-on-screen not in this release - keep-awake not installed.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$target='%EXE%';" ^
    "$desktop=[Environment]::GetFolderPath('Desktop');" ^
    "$link=Join-Path $desktop 'TrackAttendance.lnk';" ^
    "$w=New-Object -ComObject WScript.Shell;" ^
    "$s=$w.CreateShortcut($link);" ^
    "$s.TargetPath=$target;" ^
    "$s.WorkingDirectory='%DEST%';" ^
    "$s.IconLocation=$target;" ^
    "$s.Save();"

echo Done! Desktop shortcut created. Run this as the account the kiosk logs on with:
echo the keep-awake Startup entry is per user.
echo First launch on this laptop will prompt for a station name -- give each laptop a unique one.
pause
