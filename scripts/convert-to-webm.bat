@echo off
:: Convert a video (for example an MP4 with H.264/AAC, which the kiosk cannot play)
:: to WebM (VP9 video + Opus audio), which it can. Put the result in the media\ folder.
::
:: Usage:  scripts\convert-to-webm.bat input.mp4 [output.webm]
:: Needs ffmpeg on PATH (install once with:  winget install Gyan.FFmpeg).
setlocal
if "%~1"=="" (
    echo Usage: %~nx0 input-video [output.webm]
    exit /b 1
)
if not exist "%~1" (
    echo Input not found: %~1
    exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo ffmpeg not found. Install it with:  winget install Gyan.FFmpeg
    exit /b 1
)
set "OUT=%~2"
if "%OUT%"=="" set "OUT=%~dpn1.webm"
echo Converting "%~1" to "%OUT%" ...
ffmpeg -hide_banner -y -i "%~1" -c:v libvpx-vp9 -crf 32 -b:v 0 -row-mt 1 -deadline good -cpu-used 2 -c:a libopus -b:a 128k "%OUT%"
if errorlevel 1 (
    echo Conversion failed.
    exit /b 1
)
echo Done: "%OUT%"
echo Copy it into the media\ folder next to TrackAttendance.exe and restart the app.
