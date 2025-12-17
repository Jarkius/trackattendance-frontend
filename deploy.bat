@echo on
setlocal EnableExtensions

:: Get path and strip the trailing backslash
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"

set "DEST=C:\TrackAttendance"
set "EXE=%DEST%\TrackAttendance.exe"

echo Deploying TrackAttendance from %SRC%...

:: Using quotes safely now that trailing backslash is gone
robocopy "%SRC%" "%DEST%" /E /COPY:DAT /DCOPY:DAT /R:2 /W:2
set "RC=%ERRORLEVEL%"

:: Robocopy exit codes < 8 are successful variations
if %RC% GEQ 8 (
    echo Copy failed. Exit code=%RC%
    pause
    exit /b %RC%
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

echo Done!
pause
