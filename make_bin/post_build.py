# make_bin/post_build.py
"""
Логика пост-обработки после сборки PyInstaller.
"""
import os
import shutil
from datetime import datetime

from make_bin.config import (
    PROJECT_DIR, DIST_DIR, EXE_EXT,
    AppNames, CompiledDirs
)
from make_bin.utils import (
    calculate_sha256,
    update_hash_in_file,
    delete_folders,
    delete_files,
    move_folders,
    copy_file,
    copy_executable,
    get_latest_backup,
    get_file_info,
)
from make_bin.datas import (
    get_folders_to_delete,
    get_files_to_delete,
    get_folders_to_move,
    get_files_to_copy,
)


def copy_player_and_update_hash(
        player_name: str,
        hash_const_name: str,
        app_py_path: str = None
) -> str | None:
    """
    Копирует плеер в основную директорию и обновляет хэш в app.py.

    Args:
        player_name: Имя плеера (например, 'AnimePlayerVlc')
        hash_const_name: Имя константы хэша (например, 'VLC_PLAYER_HASH')
        app_py_path: Путь к app.py (по умолчанию PROJECT_DIR/app/qt/app.py)

    Returns:
        Хэш плеера или None при ошибке
    """
    if app_py_path is None:
        app_py_path = os.path.join(PROJECT_DIR, 'app', 'qt', 'app.py')

    player_dir = CompiledDirs.get(player_name)
    main_dir = CompiledDirs.get(AppNames.MAIN)

    exe_name = player_name + EXE_EXT
    player_src = os.path.join(player_dir, exe_name)
    player_dst = os.path.join(main_dir, exe_name)

    # Вычисляем хэш
    if not os.path.exists(player_src):
        print(f"❌ Player not found: {player_src}")
        return None

    player_hash = calculate_sha256(player_src)

    # Обновляем хэш в app.py
    update_hash_in_file(app_py_path, hash_const_name, player_hash)

    return player_hash


def copy_all_players_to_main():
    """Копирует все плееры в основную директорию приложения."""
    main_dir = CompiledDirs.get(AppNames.MAIN)
    os.makedirs(main_dir, exist_ok=True)

    players = [
        (AppNames.VLC, 'VLC_PLAYER_HASH'),
        (AppNames.MPV, 'MPV_PLAYER_HASH'),
        (AppNames.BROWSER, 'MINI_BROWSER_HASH'),
    ]

    for player_name, hash_const in players:
        player_dir = CompiledDirs.get(player_name)
        if copy_executable(player_dir, player_name, main_dir):
            print(f"✅ {player_name} copied to main app directory")


def move_mpv_library():
    """Переносит libmpv-2.dll из libs в корень AnimePlayer."""
    print("\n--- Moving MPV Library ---")

    main_dir = CompiledDirs.get(AppNames.MAIN)

    # После reorganize_folders libs уже в корне AnimePlayer
    libs_in_dist = os.path.join(main_dir, 'libs', 'libmpv-2.dll')
    dest_path = os.path.join(main_dir, 'libmpv-2.dll')

    if os.path.exists(libs_in_dist):
        shutil.move(libs_in_dist, dest_path)
        print(f"✅ Moved libmpv-2.dll to {dest_path}")
        return True
    elif os.path.exists(dest_path):
        print(f"✅ libmpv-2.dll already in root")
        return True
    else:
        # Fallback: копируем из исходников
        libs_in_project = os.path.join(PROJECT_DIR, 'libs', 'libmpv-2.dll')
        if os.path.exists(libs_in_project):
            shutil.copy2(libs_in_project, dest_path)
            print(f"✅ Copied libmpv-2.dll from project to {dest_path}")
            return True
        else:
            print(f"⚠️ libmpv-2.dll not found")
            return False


def cleanup_dist():
    """Очищает dist от лишних файлов и папок."""
    print("\n--- Cleanup ---")

    # Удаляем папки
    folders = get_folders_to_delete()
    for rel_path, patterns in folders.items():
        target_dir = os.path.join(DIST_DIR, rel_path)
        if os.path.exists(target_dir):
            delete_folders(target_dir, patterns)

    # Удаляем файлы
    files = get_files_to_delete()
    for rel_path, patterns in files.items():
        target_dir = os.path.join(DIST_DIR, rel_path)
        if os.path.exists(target_dir):
            delete_files(target_dir, patterns)


def reorganize_folders():
    """Перемещает папки из _internal в корень приложения."""
    print("\n--- Reorganize Folders ---")

    folders = get_folders_to_move()

    # Преобразуем относительные пути в абсолютные
    mapping = {}
    for rel_src, (rel_dst, names) in folders.items():
        src_path = os.path.join(DIST_DIR, rel_src)
        dst_path = os.path.join(DIST_DIR, rel_dst)
        if os.path.exists(src_path):
            mapping[src_path] = (dst_path, names)

    move_folders(mapping)


def copy_additional_files():
    """Копирует дополнительные файлы в директории приложений."""
    print("\n--- Copy Additional Files ---")

    files = get_files_to_copy()

    for rel_dest, file_names in files.items():
        dest_dir = os.path.join(DIST_DIR, rel_dest)
        internal_dir = os.path.join(dest_dir, '_internal')

        for file_name in file_names:
            src_path = os.path.join(internal_dir, file_name)
            if os.path.exists(src_path):
                copy_file(src_path, dest_dir)


def compare_and_restore_database():
    """Сравнивает базы данных и предлагает восстановление при необходимости."""
    print("\n--- Database Comparison ---")

    backup_folder = os.path.join(os.path.expanduser("~"), "Desktop", "db")
    post_build_db = os.path.join(DIST_DIR, "AnimePlayer", "db", "anime_player.db")

    pre_build_db = get_latest_backup(backup_folder)
    pre_size, pre_time = get_file_info(pre_build_db)
    post_size, post_time = get_file_info(post_build_db)

    print("\n📂 **Database comparison**")

    if pre_build_db:
        print(f"🔹 Last backup before build: {pre_build_db}")
        print(f"   - Size: {pre_size} bytes")
        print(f"   - Last modified: {pre_time}")
    else:
        print("❌ Backup before build not found.")

    if post_size:
        print(f"\n🔹 DB after build: {post_build_db}")
        print(f"   - Size: {post_size} bytes")
        print(f"   - Last modified: {post_time}")
    else:
        print("\n❌ Database missing after build.")

    if pre_size and post_size and pre_time and post_time:
        restore_needed = False

        if pre_time > post_time:
            print("\n⚠️ **WARNING: Backup is newer than database after build!**")
            restore_needed = True
        elif pre_time < post_time:
            if post_size < pre_size:
                print("\n⚠️ **WARNING: New database is smaller! Data loss possible!**")
                restore_needed = True
            else:
                print("\n✅ **Database after build is newer than backup.**")
        else:
            if pre_size != post_size:
                print("\n⚠️ **WARNING: Same time but different sizes!**")
                restore_needed = True
            else:
                print("\n✅ **Databases match. No changes found.**")

        if restore_needed:
            user_input = input("\n🔥 Restore database from last backup? (y/N): ").strip().lower()
            if user_input == 'y':
                try:
                    shutil.copy2(pre_build_db, post_build_db)
                    print(f"\n✅ Database restored from:\n   {pre_build_db} → {post_build_db}")
                except Exception as e:
                    print(f"\n❌ Failed to restore database: {e}")
            else:
                print("\n❌ Database restoration canceled.")


def run_post_build():
    """Выполняет все пост-сборочные операции."""
    print("\n" + "=" * 50)
    print("POST-BUILD OPERATIONS")
    print("=" * 50)

    # 1. Копируем плееры в основную директорию
    copy_all_players_to_main()

    # 2. Очистка от лишних файлов
    cleanup_dist()

    # 3. Реорганизация папок (libs перемещается сюда)
    reorganize_folders()

    # 4. Переносим libmpv-2.dll из libs в корень (ПОСЛЕ reorganize!)
    move_mpv_library()

    # 5. Копирование дополнительных файлов
    copy_additional_files()

    # 6. Сравнение и восстановление БД
    compare_and_restore_database()

    print("\n" + "=" * 50)
    print("POST-BUILD COMPLETED")
    print("=" * 50)


if __name__ == '__main__':
    run_post_build()