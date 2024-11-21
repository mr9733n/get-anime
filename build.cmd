@echo off
set TARGET_DIR=%1
set /a TOTAL_STEPS=16
set /a CURRENT_STEP=0

call :show_progress

rem Create target directory if it doesn't exist
if not exist %TARGET_DIR% (mkdir %TARGET_DIR%)
set /a CURRENT_STEP+=1
call :show_progress

rem delete dist folder
rmdir /s /q build
set /a CURRENT_STEP+=1
call :show_progress

cd dist
rmdir /s /q AnimePlayer
set /a CURRENT_STEP+=1
call :show_progress

cd ..
pyinstaller main.spec > %TARGET_DIR%\build_log.txt 2>&1
set /a CURRENT_STEP+=1
call :show_progress

cd dist\AnimePlayer
robocopy . %TARGET_DIR% *.* /NFL /NDL /NJH /NJS /NC /NS /NP >> %TARGET_DIR%\build_log.txt 2>&1
set /a CURRENT_STEP+=1
call :show_progress

rem Check and copy only if the directories exist
if exist charset_normalizer (robocopy charset_normalizer %TARGET_DIR%\charset_normalizer /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying charset_normalizer >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist PIL (robocopy PIL %TARGET_DIR%\PIL /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying PIL >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist PyQt5 (robocopy PyQt5 %TARGET_DIR%\PyQt5 /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying PyQt5 >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist sqlalchemy (robocopy sqlalchemy %TARGET_DIR%\sqlalchemy /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying sqlalchemy >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist config (robocopy config %TARGET_DIR%\config /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying config >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist db (robocopy db %TARGET_DIR%\db /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying db >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist certifi (robocopy certifi %TARGET_DIR%\certifi /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying certifi >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist static (robocopy static %TARGET_DIR%\static /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying static >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist templates\default (robocopy templates\default %TARGET_DIR%\templates\default /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying static >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist app\qt\__pycache__ (robocopy app\qt\__pycache__ %TARGET_DIR%\app\qt\__pycache__ /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying app\qt\__pycache__ >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist core\__pycache__ (robocopy core\__pycache__ %TARGET_DIR%\core\__pycache__ /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying core\__pycache__ >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

if exist utils\__pycache__ (robocopy utils\__pycache__ %TARGET_DIR%\utils\__pycache__ /E) >> %TARGET_DIR%\build_log.txt 2>&1
if %ERRORLEVEL% geq 1 echo Error copying utils\__pycache__ >> %TARGET_DIR%\build_log.txt
set /a CURRENT_STEP+=1
call :show_progress

type %TARGET_DIR%\build_log.txt

goto :eof

:show_progress
set /a PERCENT_DONE=(CURRENT_STEP*100)/TOTAL_STEPS
echo Progress: %PERCENT_DONE%%% done.