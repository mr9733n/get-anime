# make_bin/utils.py
"""
Утилиты для сборки: хэширование, копирование, удаление
"""
import os
import re
import glob
import shutil
import hashlib
import tempfile
import compileall
from pathlib import Path
from datetime import datetime

from make_bin.config import PROJECT_DIR, DIST_DIR, EXE_EXT


def calculate_sha256(file_path: str) -> str:
    """Вычисляет SHA256 хэш файла."""
    hash_function = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_function.update(chunk)
    return hash_function.hexdigest()


def compile_directories(directories: list[str]):
    """Компилирует Python файлы в указанных директориях."""
    for directory in directories:
        path = os.path.join(PROJECT_DIR, directory)
        if os.path.exists(path):
            compileall.compile_dir(path, force=True)
            print(f"✅ Compiled: {directory}")
        else:
            print(f"⚠️ Directory not found: {directory}")


def ensure_logs_directory():
    """Создаёт директорию logs если её нет."""
    logs_dir = os.path.join(PROJECT_DIR, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        # Создаём .gitkeep чтобы папка была в git
        gitkeep = os.path.join(logs_dir, '.gitkeep')
        Path(gitkeep).touch()
        print(f"✅ Created logs directory: {logs_dir}")
    return logs_dir


def delete_folders(target_dir: str, folder_patterns: list[str]):
    """Удаляет папки по шаблонам."""
    for pattern in folder_patterns:
        full_pattern = os.path.join(target_dir, pattern)
        for folder_path in glob.glob(full_pattern):
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)
                print(f"✅ Deleted folder: {folder_path}")


def delete_files(target_dir: str, file_patterns: list[str]):
    """Удаляет файлы по шаблонам."""
    for pattern in file_patterns:
        full_pattern = os.path.join(target_dir, pattern)
        for file_path in glob.glob(full_pattern):
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    print(f"✅ Deleted file: {file_path}")
                except Exception as e:
                    print(f"❌ Error deleting {file_path}: {e}")


def move_folders(mapping: dict[str, tuple[str, list[str]]]):
    """
    Перемещает папки согласно маппингу.
    mapping: { source_root: (dest_root, ["app", "config", ...]) }
    """
    for src_root, (dest_root, patterns) in mapping.items():
        for name in patterns:
            src_path = os.path.join(src_root, name)
            dst_path = os.path.join(dest_root, name)

            if not os.path.exists(src_path):
                print(f"⚠️ Skip (no such source): {src_path}")
                continue

            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            print(f"➡️ Move {src_path} → {dst_path}")
            shutil.move(src_path, dst_path)

        print(f"✅ Done for {src_root} → {dest_root}")


def copy_file(src: str, dst_dir: str):
    """Копирует файл в указанную директорию."""
    src_path = Path(src)
    if not src_path.exists() or not src_path.is_file():
        print(f"⚠️ Skip copy: source file not found → {src_path}")
        return

    dst_dir_path = Path(dst_dir)
    dst_dir_path.mkdir(parents=True, exist_ok=True)
    dst_path = dst_dir_path / src_path.name
    shutil.copy2(src_path, dst_path)
    print(f"📄 Copied file: {src_path} → {dst_path}")


def copy_executable(src_dir: str, exe_name: str, dest_dir: str) -> bool:
    """Копирует исполняемый файл в целевую директорию."""
    exe_full_name = exe_name + EXE_EXT
    src_path = os.path.join(src_dir, exe_full_name)
    dst_path = os.path.join(dest_dir, exe_full_name)

    if os.path.exists(src_path):
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copyfile(src_path, dst_path)
        print(f"✅ Copied {exe_full_name} to {dest_dir}")
        return True
    else:
        print(f"❌ Error: {exe_full_name} not found at {src_path}")
        return False


def update_hash_in_file(file_path: str, const_name: str, hash_value: str,
                        class_marker: str = "class AnimePlayerAppVer3"):
    """Обновляет или добавляет константу хэша в файл."""
    try:
        with open(file_path, "r+", encoding="utf-8") as f:
            content = f.read()

            if const_name in content:
                updated_content = re.sub(
                    rf'{const_name}\s*=\s*".*?"',
                    f'{const_name} = "{hash_value}"',
                    content
                )
            else:
                import_section_end = content.find(class_marker)
                if import_section_end > 0:
                    updated_content = (
                            content[:import_section_end] +
                            f"\n# Hash of compiled executable\n{const_name} = \"{hash_value}\"\n\n" +
                            content[import_section_end:]
                    )
                else:
                    updated_content = f"# Hash of compiled executable\n{const_name} = \"{hash_value}\"\n\n" + content

            f.seek(0)
            f.write(updated_content)
            f.truncate()
        print(f"✅ Updated {file_path} with {const_name}: {hash_value[:16]}...")
        return True
    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")
        return False


def backup_database(source_db: str, backup_folder: str) -> str | None:
    """Создаёт резервную копию базы данных."""
    os.makedirs(backup_folder, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = f"anime_player_{timestamp}.db"
    backup_path = os.path.join(backup_folder, backup_file)

    try:
        if os.path.exists(source_db):
            shutil.copy2(source_db, backup_path)
            print(f"✅ Database backup saved: {backup_path}")
            return backup_path
        else:
            print(f"⚠️ Database file not found: {source_db}")
            return None
    except Exception as e:
        print(f"❌ Error copying DB: {e}")
        return None


def get_latest_backup(folder: str) -> str | None:
    """Находит последний созданный файл бэкапа в папке."""
    try:
        files = [f for f in os.listdir(folder) if f.endswith(".db")]
        if not files:
            return None
        latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(folder, f)))
        return os.path.join(folder, latest_file)
    except Exception as e:
        print(f"❌ Error searching for last backup: {e}")
        return None


def get_file_info(file_path: str) -> tuple[int | None, str | None]:
    """Возвращает размер и дату модификации файла."""
    if not file_path or not os.path.exists(file_path):
        return None, None
    size = os.path.getsize(file_path)
    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
    return size, modified_time


def create_temp_config(config_path: str, replacements: dict, prod_key: str = None) -> str:
    """Создаёт временный config.ini с заменами."""
    import uuid

    temp_config_dir = Path(tempfile.mkdtemp(prefix="build_config_"))
    build_config_path = temp_config_dir / 'config.ini'

    if config_path and os.path.exists(config_path):
        shutil.copy(config_path, build_config_path)

        with open(build_config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        with open(build_config_path, 'w', encoding='utf-8') as f:
            for line in lines:
                replaced = False
                for key, new_value in replacements.items():
                    if line.startswith(key + "="):
                        f.write(f"{key}={new_value}\n")
                        replaced = True
                        break
                if not replaced:
                    f.write(line)

            # Добавляем PROD_KEY
            if prod_key is None:
                prod_key = str(uuid.uuid4())
            f.write(f"PROD_KEY={prod_key}\n")
            os.environ["PROD_KEY"] = prod_key

        print(f"✅ Temporary config.ini created: {build_config_path}")

    return str(build_config_path)