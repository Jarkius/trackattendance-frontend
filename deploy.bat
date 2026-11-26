@echo on
setlocal EnableExtensions

:: Run this script from inside the hosted release folder itself (e.g. a
:: network share or mapped drive containing TrackAttendance.exe, _internal\,
:: data\, exports\, logs\, .env). It deploys "from wherever I am" to this
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

echo Deploying TrackAttendance from %SRC% to %DEST%...

:: Exclude this script and any local runtime state that shouldn't be copied
:: from the shared release source onto the laptop -- each laptop gets its
:: own fresh database, exports, and logs, not whatever accumulated on the
:: share from testing/other laptops.
robocopy "%SRC%" "%DEST%" /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 ^
    /XF "deploy.bat" "database.db" "database.db-shm" "database.db-wal" "trackattendance.log" ^
    /XD "%SRC%\data\backups"
set "RC=%ERRORLEVEL%"

:: Robocopy exit codes < 8 are successful variations
if %RC% GEQ 8 (
    echo Copy failed. Exit code=%RC%
    pause
    exit /b %RC%
)

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
