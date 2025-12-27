@echo off
REM make.bat for AnimePlayer (Windows)
REM Usage:
REM   make build      - Build all applications
REM   make clean      - Clean build artifacts
REM   make rebuild    - Clean and rebuild
REM   make vlc        - Build only VLC player
REM   make mpv        - Build only MPV player
REM   make browser    - Build only Mini Browser
REM   make main       - Build only main app
REM   make lite       - Build only Lite version
REM   make post-build - Run post-build only

setlocal enabledelayedexpansion

REM Configuration
set PYTHON=python
set PYINSTALLER=pyinstaller
set PIP=pip

set PROJECT_DIR=%~dp0
set BUILD_DIR=%PROJECT_DIR%make_bin
set DIST_DIR=%PROJECT_DIR%dist
set SPEC_FILE=%BUILD_DIR%\main.spec

REM Parse command
if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="all" goto all
if "%1"=="build" goto build
if "%1"=="clean" goto clean
if "%1"=="rebuild" goto rebuild
if "%1"=="install-deps" goto install-deps
if "%1"=="check-deps" goto check-deps
if "%1"=="vlc" goto vlc
if "%1"=="mpv" goto mpv
if "%1"=="browser" goto browser
if "%1"=="main" goto main
if "%1"=="lite" goto lite
if "%1"=="sync" goto sync
if "%1"=="post-build" goto post-build
if "%1"=="dist" goto dist
if "%1"=="dev" goto dev

echo Unknown command: %1
goto help

:help
echo.
echo ===================================
echo   AnimePlayer Build System
echo ===================================
echo.
echo Usage: make [command]
echo.
echo Commands:
echo   all          - Build everything (main + sync)
echo   build        - Build main applications
echo   clean        - Clean build artifacts
echo   rebuild      - Clean and rebuild everything
echo   install-deps - Install Python dependencies
echo   check-deps   - Check if dependencies are installed
echo.
echo Individual builds:
echo   vlc          - Build VLC player only
echo   mpv          - Build MPV player only
echo   browser      - Build Mini Browser only
echo   main         - Build main AnimePlayer only
echo   lite         - Build AnimePlayer Lite only
echo   sync         - Build PlayerDBSync utilities
echo.
echo Other:
echo   post-build   - Run post-build operations
echo   dist         - Create distribution archive
echo   dev          - Development build with console
echo.
goto end

:check-deps
echo.
echo [*] Checking dependencies...
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    exit /b 1
)
%PYTHON% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller not installed!
    echo Run: make install-deps
    exit /b 1
)
echo [OK] All dependencies found
goto end

:install-deps
echo.
echo [*] Installing dependencies...
%PIP% install -r requirements.txt
%PIP% install pyinstaller
echo [OK] Dependencies installed
goto end

:build
call :check-deps
if errorlevel 1 goto end
echo.
echo ===================================
echo   Starting Full Build
echo ===================================
echo.
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
%PYINSTALLER% --noconfirm --clean "%SPEC_FILE%"
if errorlevel 1 (
    echo [ERROR] Build failed!
    exit /b 1
)
echo.
echo ===================================
echo   Build Completed Successfully!
echo ===================================
goto end

:clean
echo.
echo [*] Cleaning build artifacts...
if exist "%DIST_DIR%" (
    rmdir /s /q "%DIST_DIR%"
)
if exist "%PROJECT_DIR%build" (
    rmdir /s /q "%PROJECT_DIR%build"
)
for /d /r "%PROJECT_DIR%" %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)
for /r "%PROJECT_DIR%" %%f in (*.pyc *.pyo) do (
    if exist "%%f" del "%%f"
)
echo [OK] Clean completed
goto end

:rebuild
call :clean
call :build
goto end

:vlc
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Building VLC Player...
%PYINSTALLER% --noconfirm "%BUILD_DIR%\specs\vlc_player.spec"
echo [OK] VLC Player built
goto end

:mpv
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Building MPV Player...
%PYINSTALLER% --noconfirm "%BUILD_DIR%\specs\mpv_player.spec"
echo [OK] MPV Player built
goto end

:browser
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Building Mini Browser...
%PYINSTALLER% --noconfirm "%BUILD_DIR%\specs\mini_browser.spec"
echo [OK] Mini Browser built
goto end

:main
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Building Main AnimePlayer...
%PYINSTALLER% --noconfirm "%BUILD_DIR%\specs\main_app.spec"
echo [OK] Main AnimePlayer built
goto end

:lite
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Building AnimePlayer Lite...
%PYINSTALLER% --noconfirm "%BUILD_DIR%\specs\lite_app.spec"
echo [OK] AnimePlayer Lite built
goto end

:post-build
echo.
echo [*] Running post-build operations...
%PYTHON% -m make_bin.post_build
echo [OK] Post-build completed
goto end

:dist
call :build
if errorlevel 1 goto end
echo.
echo [*] Creating distribution archive...
set DATESTAMP=%date:~-4%%date:~3,2%%date:~0,2%
cd "%DIST_DIR%"
powershell -command "Compress-Archive -Path 'AnimePlayer' -DestinationPath 'AnimePlayer-%DATESTAMP%.zip' -Force"
echo [OK] Archive created: %DIST_DIR%\AnimePlayer-%DATESTAMP%.zip
goto end

:dev
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Development build (with console)...
%PYINSTALLER% --noconfirm --clean --console --name AnimePlayer-dev main.py
echo [OK] Dev build completed
goto end

:all
echo.
echo ===================================
echo   Building Everything
echo ===================================
call :build
if errorlevel 1 goto end
call :sync
goto end

:sync
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Building PlayerDBSync utilities...
%PYINSTALLER% --noconfirm "%BUILD_DIR%\specs\db_sync.spec"
if errorlevel 1 (
    echo [ERROR] PlayerDBSync build failed!
    exit /b 1
)
echo [OK] PlayerDBSync built
goto end

:end
endlocal