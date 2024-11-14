#!/bin/bash

TARGET_DIR=$1
TOTAL_STEPS=16
CURRENT_STEP=0

show_progress() {
    PERCENT_DONE=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    clear
    echo "Progress: $PERCENT_DONE% done."
}

# Create target directory if it doesn't exist
mkdir -p "$TARGET_DIR"
((CURRENT_STEP++))
show_progress

# Delete dist folder
rm -rf build
((CURRENT_STEP++))
show_progress

cd dist || exit
rm -rf AnimePlayer
((CURRENT_STEP++))
show_progress

cd ..
pyinstaller main.spec > "$TARGET_DIR/build_log.txt" 2>&1
((CURRENT_STEP++))
show_progress

cd dist/AnimePlayer || exit
rsync -av --progress . "$TARGET_DIR" --exclude "*/" >> "$TARGET_DIR/build_log.txt" 2>&1
((CURRENT_STEP++))
show_progress

# Check and copy only if the directories exist
if [ -d "charset_normalizer" ]; then
    rsync -av charset_normalizer "$TARGET_DIR/charset_normalizer" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "PIL" ]; then
    rsync -av PIL "$TARGET_DIR/PIL" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "PyQt5" ]; then
    rsync -av PyQt5 "$TARGET_DIR/PyQt5" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "sqlalchemy" ]; then
    rsync -av sqlalchemy "$TARGET_DIR/sqlalchemy" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "config" ]; then
    rsync -av config "$TARGET_DIR/config" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "db" ]; then
    rsync -av db "$TARGET_DIR/db" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "certifi" ]; then
    rsync -av certifi "$TARGET_DIR/certifi" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "static" ]; then
    rsync -av static "$TARGET_DIR/static" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "app/qt/__pycache__" ]; then
    rsync -av app/qt/__pycache__ "$TARGET_DIR/app/qt/__pycache__" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "core/__pycache__" ]; then
    rsync -av core/__pycache__ "$TARGET_DIR/core/__pycache__" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

if [ -d "utils/__pycache__" ]; then
    rsync -av utils/__pycache__ "$TARGET_DIR/utils/__pycache__" >> "$TARGET_DIR/build_log.txt" 2>&1
    ((CURRENT_STEP++))
    show_progress
fi

cat "$TARGET_DIR/build_log.txt"
