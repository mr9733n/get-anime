# merge_utility.spec

import hashlib
import os
import shutil
import re

block_cipher = None
project_dir = os.getcwd()

a = Analysis(['merge_utility.py'],
             pathex=[
                 project_dir,
                 'C:\\users\\cicada\\appdata\\local\\programs\\python\\python312\\lib\\site-packages',  # Путь к site-packages
             ],
             binaries=[
             ],
		 	 datas=[(os.path.join(project_dir, 'core/'), 'core'), (os.path.join(project_dir, '.env'), '.')],
             hiddenimports=[
                 'dotenv', 'sqlalchemy', 'pyzbar.pyzbar', 'PIL.Image', 'importlib.util', 'sqlite3', 'base64', 'qrcode'
             ],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='merge_utility',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True)

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='merge_utility')

dist_dir = os.path.join(project_dir, 'dist')
compiled_dir1 = os.path.join(dist_dir, 'AnimePlayer')
compiled_dir2 = os.path.join(dist_dir, 'merge_utility')

config_file = os.path.join(project_dir, '.env')
binary_file = os.path.join(compiled_dir2, 'merge_utility.exe')

config_file_path = os.path.join(compiled_dir1, '.env')
binary_file_path = os.path.join(compiled_dir1, 'merge_utility.exe')

sync_script = os.path.join(project_dir, 'sync.py')

shutil.copyfile(config_file, config_file_path)
shutil.copyfile(binary_file, binary_file_path)

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

if os.path.exists(binary_file_path):
    checksum = calculate_sha256(binary_file_path)
    status = write_to_file(checksum, sync_script)
    if status:
        print(f"{checksum} INJECT {status}")
else:
    print(f"Error: Target binary {binary_file_path} does not exist.")
