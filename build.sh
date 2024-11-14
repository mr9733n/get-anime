#!/bin/bash

TARGET_DIR=$1
TOTAL_STEPS=16
CURRENT_STEP=0

show_progress() {
    PERCENT_DONE=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    clear
    echo "Progress: $PERCENT_DONE% done."
}

# Check if the target directory exists, delete if it does, otherwise create it
if [ -d "$TARGET_DIR" ]; then
    rm -rf "$TARGET_DIR"
else
    mkdir -p "$TARGET_DIR"
fi
((CURRENT_STEP++))
show_progress

# Delete dist folder
rm -rf build
((CURRENT_STEP++))
show_progress

rm -rf dist
((CURRENT_STEP++))
show_progress

pyinstaller main.spec > "$TARGET_DIR/build_log.txt" 2>&1
((CURRENT_STEP++))
show_progress

cd dist/AnimePlayer || exit
rsync -av --progress . "$TARGET_DIR" --exclude "*/" >> "$TARGET_DIR/build_log.txt" 2>&1
((CURRENT_STEP++))
show_progress

# Check and copy only if the directories exist
copy_if_exists() {
    local DIR=$1
    if [ -d "$DIR" ]; then
        rsync -av "$DIR" "$TARGET_DIR/$DIR" >> "$TARGET_DIR/build_log.txt" 2>&1
        ((CURRENT_STEP++))
        show_progress
    fi
}

copy_if_exists "charset_normalizer"
copy_if_exists "PIL"
copy_if_exists "PyQt5"
copy_if_exists "sqlalchemy"
copy_if_exists "config"
copy_if_exists "db"
copy_if_exists "certifi"
copy_if_exists "static"
copy_if_exists "app/qt/__pycache__"
copy_if_exists "core/__pycache__"
copy_if_exists "utils/__pycache__"

cat "$TARGET_DIR/build_log.txt"
