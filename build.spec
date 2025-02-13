# -*- mode: python ; coding: utf-8 -*-

# main.spec

import compileall
import os
import shutil
import hashlib
import re

os.environ["USE_GIT_VERSION"] = "0"

# Compile the files in the 'app' directory
compileall.compile_dir('app', force=True)

# Compile the files in the 'core' directory
compileall.compile_dir('core', force=True)

# Compile the files in the 'utils' directory
compileall.compile_dir('utils', force=True)

# Compile the files in the 'templates' directory
compileall.compile_dir('templates', force=True)

# Импортируем необходимый модуль Analysis, EXE, COLLECT
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Указываем путь к директории проекта
project_dir = os.getcwd()

# Сбор данных для ресурсы, например из папок `static` и `db`
datas = [
    (os.path.join(project_dir, 'static/*'), 'static'),
    (os.path.join(project_dir, 'templates/default/*'), 'templates/default'),
    (os.path.join(project_dir, 'config/*'), 'config'),
    (os.path.join(project_dir, 'db/*'), 'db'),
    (os.path.join(project_dir, 'app/qt'), 'app/qt'),
    (os.path.join(project_dir, 'core/'), 'core'),
    (os.path.join(project_dir, 'utils/'), 'utils'),
    (os.path.join(project_dir, 'libs/'), 'libs'),
    (os.path.join(project_dir, 'app/qt/__pycache__'), 'app/qt/__pycache__'),  # Add compiled .pyc files
    (os.path.join(project_dir, 'core/__pycache__'), 'core/__pycache__'),      # Add compiled .pyc files
    (os.path.join(project_dir, 'utils/__pycache__'), 'utils/__pycache__'),    # Add compiled .pyc files
	(os.path.join(project_dir, 'favicon.ico'), '.'),
	(os.path.join(project_dir, 'anime_player_app_roadmap.md'), '.'),
	(os.path.join(project_dir, 'LICENSE.md'), '.'),
	(os.path.join(project_dir, 'README.md'), '.'),
	(os.path.join(project_dir, 'sql_commands.md'), '.'),
	(os.path.join(project_dir, '.env'), '.')
]

packages = 'c:\\users\\cicada\\appdata\\local\\programs\\python\\python312\\lib\\site-packages'

a = Analysis(
    ['main.py'],
    pathex=[
        project_dir,
		packages,
    ],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pkg_resources',
        'pkg_resources.extern',
		'multiprocessing',
		'requests.compat',
		'cryptography',
		'PIL.Image',
		'numpy',  # Used conditionally in PIL
		'sqlalchemy.dialects.sqlite',
		'urllib3.contrib.socks',
        'uuid',
        'jinja2',
        'python-vlc',
		'sqlalchemy',
		'sqlalchemy.orm',
		'sqlalchemy.ext.declarative',
		'sqlalchemy.engine',
		'sqlalchemy.sql',
        'app.qt.app',
        'app.qt.app_helpers',
        'app.qt.layout_metadata',
        'app.qt.ui_manager',
        'app.qt.ui_generator',
        'app.qt.ui_s_generator',
        'core.database_manager',
        'core.get',
        'core.save',
        'core.process',
        'core.tables',
        'core.utils',
        'utils.api_client',
        'utils.config_manager',
        'utils.logging_handlers',
        'utils.playlist_manager',
        'utils.poster_manager',
        'utils.torrent_manager',
        'utils.library_loader',
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data,
    cipher=block_cipher)

exe = EXE(
	pyz,
	a.scripts,
	[],
	exclude_binaries=True,
	name='AnimePlayer',
	icon='favicon.ico',
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=True,
	upx_exclude=[],
	runtime_tmpdir=None,
	console=True,
	onefile=False,  # Important for imports to set to False to keep everything in the same folder
	)

coll = COLLECT(
	exe,
	a.binaries,
	a.zipfiles,
	a.datas,
	strip=False,
	upx=True,
	upx_exclude=[],
	name='AnimePlayer'
	)

# merge_utility.spec
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

binary_file = os.path.join(compiled_dir2, 'merge_utility.exe')
binary_file_path = os.path.join(compiled_dir1, 'merge_utility.exe')
sync_script = os.path.join(project_dir, 'sync.py')
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

# sync.spec
a = Analysis(
    ['sync.py'],
	pathex=[
	 project_dir,
	 'C:\\users\\cicada\\appdata\\local\\programs\\python\\python312\\lib\\site-packages'
	],
	binaries=[
	 ('C:\\users\\cicada\\appdata\\local\\programs\\python\\python312\\lib\\site-packages\\pyzbar\\libiconv.dll', '.'),
	 ('C:\\users\\cicada\\appdata\\local\\programs\\python\\python312\\lib\\site-packages\\pyzbar\\libzbar-64.dll', '.')
	],
    datas=[],
 	hiddenimports=[
                 'dotenv',
             ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='sync.exe',
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
               name='sync')

compiled_dir2 = os.path.join(dist_dir, 'sync')
binary_file1 = os.path.join(compiled_dir2, 'sync.exe')
binary_file_path1 = os.path.join(compiled_dir1, 'sync.exe')
binary_file2 = os.path.join(compiled_dir2, 'libiconv.dll')
binary_file_path2 = os.path.join(compiled_dir1, 'libiconv.dll')
binary_file3 = os.path.join(compiled_dir2, 'libzbar-64.dll')
binary_file_path3 = os.path.join(compiled_dir1, 'libzbar-64.dll')

shutil.copyfile(binary_file1, binary_file_path1)
shutil.copyfile(binary_file2, binary_file_path2)
shutil.copyfile(binary_file3, binary_file_path3)

folders_to_delete = [
    "importlib_metadata-8.0.0.dist-info",
    "MarkupSafe-3.0.2.dist-info",
    "cryptography-44.0.0.dist-info",
    "h2-3.2.0.dist-info"
]

for folder in folders_to_delete:
    folder_path = os.path.join(compiled_dir1, folder)
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        print(f"Deleted: {folder_path}")