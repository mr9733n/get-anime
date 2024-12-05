import hashlib
import os
import re

def calculate_sha256(file_path):
    """Вычисляет SHA-256 хэш файла."""
    hash_function = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_function.update(chunk)
    return hash_function.hexdigest()

def write_to_file(checksum, file_path):
    try:
        with open(file_path, "r+", encoding="utf-8") as f:
            content = f.read()
            updated_content = re.sub(
                r'expected_hash\s*=\s*".*?"',
                f'expected_hash = "{checksum}"',
                content
            )
            f.seek(0)
            f.write(updated_content)
            f.truncate()
        return True
    except OSError as e:
        raise IOError(f"Cannot update file: {file_path}: {e}")

project_dir = os.getcwd()

dist_dir = os.path.join(project_dir, 'dist')
compiled_dir = os.path.join(dist_dir, 'merge_utility')
binary_file = os.path.join(compiled_dir, 'merge_utility.exe')
sync_script = os.path.join(project_dir, "sync.py")

# Проверяем существование бинарного файла
if os.path.exists(binary_file):
    checksum = calculate_sha256(binary_file)
    status = write_to_file(checksum, sync_script)
    if status:
        print(f"{checksum} INJECT {status}")
else:
    print(f"Error: Target binary {binary_file} does not exist.")
