@echo off
REM make_new.bat — Build system for the new stack
REM   Kotlin Compose Desktop UI + Python HTTP backend + Python launcher
REM
REM Usage:
REM   make_new all        - Build all components and assemble dist/AnimePlayerNew/
REM   make_new build      - Build all components (backend + ui + launcher)
REM   make_new backend    - Build backend_http only  (PyInstaller)
REM   make_new ui         - Build Compose Desktop UI only  (Gradle)
REM   make_new launcher   - Build launcher only  (PyInstaller)
REM   make_new dist       - Assemble dist/AnimePlayerNew/ from built components
REM   make_new sign       - Code-sign all EXEs in dist/AnimePlayerNew/
REM   make_new clean      - Remove dist/AnimePlayerNew/ and build artefacts
REM   make_new zip        - Assemble + sign + create AnimePlayerNew-<date>.zip
REM
REM Code signing (optional):
REM   Set CODESIGN_PFX  to the path of your .pfx certificate file
REM   Set CODESIGN_PASS to the certificate password  (or leave blank for prompt)
REM   Set CODESIGN_TS   to a timestamp server URL    (default: DigiCert RFC3161)
REM   Example:
REM     set CODESIGN_PFX=C:\certs\mycert.pfx
REM     set CODESIGN_PASS=secret
REM     make_new sign

setlocal enabledelayedexpansion

set PYTHON=python
set PYINSTALLER=pyinstaller
set PROJECT_DIR=%~dp0

REM Gradle wrapper inside the ui/ sub-project
set GRADLEW=%PROJECT_DIR%ui\gradlew.bat

REM PyInstaller spec paths
set BACKEND_SPEC=%PROJECT_DIR%make_bin\specs\backend_http.spec
set LAUNCHER_SPEC=%PROJECT_DIR%make_bin_new\specs\launcher.spec

REM Code-signing defaults
if not defined CODESIGN_TS set CODESIGN_TS=http://timestamp.digicert.com

REM ── Parse command ─────────────────────────────────────────────────────────
if "%1"==""         goto help
if "%1"=="help"     goto help
if "%1"=="all"      goto all
if "%1"=="build"    goto build
if "%1"=="backend"  goto backend
if "%1"=="ui"       goto ui
if "%1"=="launcher" goto launcher
if "%1"=="dist"     goto dist
if "%1"=="sign"     goto sign
if "%1"=="clean"    goto clean
if "%1"=="zip"      goto zip

echo Unknown command: %1
goto help

REM ── Help ──────────────────────────────────────────────────────────────────
:help
echo.
echo ============================================
echo   AnimePlayer (New Stack) Build System
echo ============================================
echo.
echo Usage: make_new [command]
echo.
echo Commands:
echo   all       Build all components and assemble dist/AnimePlayerNew/
echo   build     Build all components (backend + ui + launcher)
echo   backend   Build backend_http binary only
echo   ui        Build Compose Desktop UI only
echo   launcher  Build launcher binary only
echo   dist      Assemble dist/AnimePlayerNew/ from built artefacts
echo   sign      Code-sign all EXEs in dist/AnimePlayerNew/
echo   clean     Remove dist/AnimePlayerNew/ and PyInstaller cache
echo   zip       Assemble + sign (if cert set) + zip
echo.
echo Components produced:
echo   dist\backend_http\backend_http.exe    (from :backend)
echo   ui\composeApp\build\compose\...       (from :ui)
echo   dist\AnimePlayerNew.exe               (from :launcher)
echo   dist\AnimePlayerNew\                  (assembled by :dist)
echo.
echo Code signing (optional):
echo   set CODESIGN_PFX=C:\path\to\cert.pfx
echo   set CODESIGN_PASS=password
echo   make_new sign
echo.
goto end

REM ── Check deps ────────────────────────────────────────────────────────────
:check-deps
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    exit /b 1
)
%PYTHON% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller not installed!  Run: pip install pyinstaller
    exit /b 1
)
if not exist "%GRADLEW%" (
    echo [ERROR] Gradle wrapper not found: %GRADLEW%
    exit /b 1
)
goto :eof

REM ── Find signtool.exe ─────────────────────────────────────────────────────
:find-signtool
REM Try common SDK locations newest-first
set SIGNTOOL=
for /d %%v in (
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64"
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64"
    "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64"
    "C:\Program Files (x86)\Windows Kits\10\bin\x64"
    "C:\Program Files\Windows Kits\10\bin\x64"
) do (
    if exist "%%~v\signtool.exe" (
        set SIGNTOOL=%%~v\signtool.exe
        goto :signtool-found
    )
)
REM Fall back to PATH
signtool.exe /? >nul 2>&1
if not errorlevel 1 (
    set SIGNTOOL=signtool.exe
    goto :signtool-found
)
echo [ERROR] signtool.exe not found.
echo         Install Windows SDK or add signtool to PATH.
exit /b 1
:signtool-found
echo     signtool: %SIGNTOOL%
goto :eof

REM ── Sign a single file ────────────────────────────────────────────────────
REM   call :sign-file "path\to\file.exe"
:sign-file
if not defined CODESIGN_PFX (
    echo [SKIP] CODESIGN_PFX not set — skipping signing of %~1
    goto :eof
)
if not defined CODESIGN_PASS (
    "%SIGNTOOL%" sign /f "%CODESIGN_PFX%" /tr "%CODESIGN_TS%" /td sha256 /fd sha256 "%~1"
) else (
    "%SIGNTOOL%" sign /f "%CODESIGN_PFX%" /p "%CODESIGN_PASS%" /tr "%CODESIGN_TS%" /td sha256 /fd sha256 "%~1"
)
if errorlevel 1 (
    echo [WARN] Signing failed for %~1
) else (
    echo     Signed: %~1
)
goto :eof

REM ── Backend ───────────────────────────────────────────────────────────────
:backend
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Building backend_http...
%PYINSTALLER% --noconfirm --clean "%BACKEND_SPEC%"
if errorlevel 1 (
    echo [ERROR] backend_http build failed!
    exit /b 1
)
echo [OK] backend_http built ^> dist\backend_http\
goto end

REM ── UI (Gradle) ───────────────────────────────────────────────────────────
:ui
if not exist "%GRADLEW%" (
    echo [ERROR] Gradle wrapper not found: %GRADLEW%
    goto end
)
echo.
echo [*] Building Compose Desktop UI (createDistributable)...
pushd "%PROJECT_DIR%ui"
call gradlew.bat :composeApp:createDistributable
if errorlevel 1 (
    echo [ERROR] Gradle UI build failed!
    popd
    exit /b 1
)
popd
echo [OK] UI built ^> ui\composeApp\build\compose\binaries\main\app\AnimePlayer\
goto end

REM ── Launcher ──────────────────────────────────────────────────────────────
:launcher
call :check-deps
if errorlevel 1 goto end
echo.
echo [*] Building launcher (one-file)...
%PYINSTALLER% --noconfirm --clean "%LAUNCHER_SPEC%"
if errorlevel 1 (
    echo [ERROR] Launcher build failed!
    exit /b 1
)
echo [OK] Launcher built ^> dist\AnimePlayerNew.exe
goto end

REM ── Build all components ──────────────────────────────────────────────────
:build
echo.
echo ============================================
echo   Building all components
echo ============================================
call :check-deps
if errorlevel 1 goto end

call :backend
if errorlevel 1 goto end

call :ui
if errorlevel 1 goto end

call :launcher
if errorlevel 1 goto end

echo.
echo [OK] All components built.
goto end

REM ── Assemble dist ────────────────────────────────────────────────────────
:dist
echo.
echo [*] Assembling dist\AnimePlayerNew\...
%PYTHON% -m make_bin_new.post_build
if errorlevel 1 (
    echo [ERROR] Assembly failed!
    exit /b 1
)
goto end

REM ── Code sign ────────────────────────────────────────────────────────────
:sign
if not defined CODESIGN_PFX (
    echo [SKIP] CODESIGN_PFX not set — nothing to sign.
    echo        Set CODESIGN_PFX=C:\path\to\cert.pfx and re-run.
    goto end
)
if not exist "%PROJECT_DIR%dist\AnimePlayerNew" (
    echo [ERROR] dist\AnimePlayerNew\ not found. Run: make_new dist first.
    goto end
)
echo.
echo [*] Code signing EXEs in dist\AnimePlayerNew\...
call :find-signtool
if errorlevel 1 goto end

REM Sign the launcher (root)
if exist "%PROJECT_DIR%dist\AnimePlayerNew\AnimePlayerNew.exe" (
    call :sign-file "%PROJECT_DIR%dist\AnimePlayerNew\AnimePlayerNew.exe"
)

REM Sign the backend exe
if exist "%PROJECT_DIR%dist\AnimePlayerNew\backend_http\backend_http.exe" (
    call :sign-file "%PROJECT_DIR%dist\AnimePlayerNew\backend_http\backend_http.exe"
)

REM Sign the Compose Desktop UI exe
if exist "%PROJECT_DIR%dist\AnimePlayerNew\ui\AnimePlayer.exe" (
    call :sign-file "%PROJECT_DIR%dist\AnimePlayerNew\ui\AnimePlayer.exe"
)

echo [OK] Signing complete.
goto end

REM ── Build + assemble ─────────────────────────────────────────────────────
:all
echo.
echo ============================================
echo   Full build + assemble
echo ============================================
call :build
if errorlevel 1 goto end
echo.
call :dist
if errorlevel 1 goto end
call :sign
goto end

REM ── Clean ────────────────────────────────────────────────────────────────
:clean
echo.
echo [*] Cleaning AnimePlayerNew artefacts...
if exist "%PROJECT_DIR%dist\AnimePlayerNew" (
    rmdir /s /q "%PROJECT_DIR%dist\AnimePlayerNew"
    echo     Removed dist\AnimePlayerNew\
)
if exist "%PROJECT_DIR%dist\AnimePlayerNew.exe" (
    del /q "%PROJECT_DIR%dist\AnimePlayerNew.exe"
    echo     Removed dist\AnimePlayerNew.exe
)
if exist "%PROJECT_DIR%build" (
    for %%d in (AnimePlayerNew backend_http) do (
        if exist "%PROJECT_DIR%build\%%d" (
            rmdir /s /q "%PROJECT_DIR%build\%%d"
            echo     Removed build\%%d\
        )
    )
)
REM Clean Gradle distributable artefacts only (not the full build cache)
if exist "%PROJECT_DIR%ui\composeApp\build\compose" (
    rmdir /s /q "%PROJECT_DIR%ui\composeApp\build\compose"
    echo     Removed ui\composeApp\build\compose\
)
echo [OK] Clean completed
goto end

REM ── Zip ──────────────────────────────────────────────────────────────────
:zip
call :dist
if errorlevel 1 goto end
call :sign
echo.
echo [*] Creating distribution archive...
set DATESTAMP=%date:~-4%%date:~3,2%%date:~0,2%
pushd "%PROJECT_DIR%dist"
powershell -command "Compress-Archive -Path 'AnimePlayerNew' -DestinationPath 'AnimePlayerNew-%DATESTAMP%.zip' -Force"
if errorlevel 1 (
    echo [ERROR] Zip failed!
    popd
    goto end
)
popd
echo [OK] Archive: dist\AnimePlayerNew-%DATESTAMP%.zip
goto end

:end
endlocal
