@echo off
:: Install Anime Player backend as a Windows Task Scheduler task
:: Run as Administrator
::
:: Usage:
::   install_windows.bat [install_dir] [db_path] [port]
::
:: Defaults:
::   install_dir = C:\AnimePlayer
::   port        = 8765

setlocal

set INSTALL_DIR=%~1
if "%INSTALL_DIR%"=="" set INSTALL_DIR=C:\AnimePlayer

set DB_PATH=%~2
if "%DB_PATH%"=="" set DB_PATH=%INSTALL_DIR%\db\anime_player.db

set PORT=%~3
if "%PORT%"=="" set PORT=8765

set TASK_NAME=AnimePlayerBackend
set VENV_PYTHON=%INSTALL_DIR%\venv\Scripts\python.exe

echo === Anime Player Backend - Windows Install ===
echo Install dir : %INSTALL_DIR%
echo DB path     : %DB_PATH%
echo Port        : %PORT%
echo.

:: Create directories
if not exist "%INSTALL_DIR%\db"        mkdir "%INSTALL_DIR%\db"
if not exist "%INSTALL_DIR%\playlists" mkdir "%INSTALL_DIR%\playlists"
if not exist "%INSTALL_DIR%\temp"      mkdir "%INSTALL_DIR%\temp"
if not exist "%INSTALL_DIR%\logs"      mkdir "%INSTALL_DIR%\logs"
if not exist "%INSTALL_DIR%\config"    mkdir "%INSTALL_DIR%\config"

:: Create virtual environment
if not exist "%INSTALL_DIR%\venv" (
    python -m venv "%INSTALL_DIR%\venv"
    "%INSTALL_DIR%\venv\Scripts\pip" install --upgrade pip
)

:: Install dependencies
"%INSTALL_DIR%\venv\Scripts\pip" install fastapi "uvicorn[standard]"

:: Remove old task if exists
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Create scheduled task that runs at startup
:: Using PowerShell to support long command lines
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Register-ScheduledTask -TaskName '%TASK_NAME%' -Force -Action (New-ScheduledTaskAction -Execute '%VENV_PYTHON%' -Argument '-m backend.transport.http.server --db \"%DB_PATH%\" --port %PORT% --host 0.0.0.0' -WorkingDirectory '%INSTALL_DIR%') -Trigger (New-ScheduledTaskTrigger -AtStartup) -Settings (New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)) -RunLevel Highest -User SYSTEM"

:: Start the task immediately
schtasks /run /tn "%TASK_NAME%"

echo.
echo === Done ===
echo Task    : %TASK_NAME% (runs at startup, as SYSTEM)
echo API     : http://localhost:%PORT%/api
echo Health  : http://localhost:%PORT%/health
echo Logs    : Event Viewer ^> Windows Logs ^> Application
echo.
echo To stop:  schtasks /end /tn "%TASK_NAME%"
echo To start: schtasks /run /tn "%TASK_NAME%"
pause
