# -*- mode: python ; coding: utf-8 -*-
# For python version 3.12.x


# ---
# main.spec

import os
import re
import site
import sys
import uuid
import glob
import shutil
import hashlib
import tempfile
import compileall

from datetime import datetime
from pathlib import Path
from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.building.build_main import Analysis

if sys.platform == "win32":
    # Windows: using site.getsitepackages()
    python_root = site.getsitepackages()[0]
    PACKAGES_FOLDER = os.path.join(python_root, "Lib", "site-packages")
else:
    # macOS/Linux: at first using site.getsitepackages(), else sysconfig
    try:
        PACKAGES_FOLDER = site.getsitepackages()[0]
    except AttributeError:
        import sysconfig
        PACKAGES_FOLDER = sysconfig.get_paths()["purelib"]

print(f"📂 Site-packages folder: {PACKAGES_FOLDER}")

project_dir = os.getcwd()

source_db_path = os.path.join(project_dir, "dist", "AnimePlayer", "db", "anime_player.db")
backup_folder = os.path.join(os.path.expanduser("~"), "Desktop", "db")  # 📂 Backup folder

os.makedirs(backup_folder, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
backup_file_name = f"anime_player_{timestamp}.db"
backup_path = os.path.join(backup_folder, backup_file_name)

try:
    if os.path.exists(source_db_path):
        shutil.copy2(source_db_path, backup_path)
        print(f"✅ Database backup saved: {backup_path}")
    else:
        print(f"⚠️ Database file not found: {source_db_path}")
except Exception as e:
    print(f"❌ Error copying DB: {e}")


env_path = Path(project_dir) / '.env'
temp_env_dir = Path(tempfile.mkdtemp(prefix="build_env_"))
build_env_path = temp_env_dir / '.env'

your_postmark_api_key = "your_postmark_api_key_value"
your_email = "your_email@example.com"

replacements = {
    "POSTMARK_API_KEY": your_postmark_api_key,
    "FROM_EMAIL": your_email,
    "TO_EMAIL": your_email,
}

if env_path.exists():
    shutil.copy(env_path, build_env_path)
    with open(build_env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    with open(build_env_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith("USE_GIT_VERSION="):
                continue

            replaced = False
            for key, new_value in replacements.items():
                if line.startswith(key + "="):
                    f.write(f"{key}={new_value}\n")
                    replaced = True
                    break
            if not replaced:
                f.write(line)

        prod_key = str(uuid.uuid4())
        f.write(f"PROD_KEY={prod_key}\n")
        os.environ["PROD_KEY"] = prod_key
    print(f"✅ Temporary .env file created and modified: {build_env_path}")

# Compile the files in the 'app' directory
compileall.compile_dir('app', force=True)

# Compile the files in the 'core' directory
compileall.compile_dir('core', force=True)

# Compile the files in the 'utils' directory
compileall.compile_dir('utils', force=True)

# Compile the files in the 'templates' directory
compileall.compile_dir('templates', force=True)

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

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
	(str(build_env_path), '.')
]

a = Analysis(
    ['main.py'],
    pathex=[
        project_dir,
		PACKAGES_FOLDER,
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
	console=False,
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


# ---
# anime_player_lite.spec

block_cipher = None
project_dir = os.getcwd()

a = Analysis(
    ['app/tinker_v1/app.py'],
    pathex=['.'],
    binaries=[],
    datas=[('config/config.ini', 'config'), (os.path.join(project_dir, 'favicon.ico'), '.'),],
    hiddenimports=['PIL', 'tkinter', 'tkinter.ttk', 'requests', 'configparser'],
    hookspath=[],
    runtime_hooks=[],
    excludes=["cryptography", "numpy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
	a.scripts,
	[],
	exclude_binaries=True,
    name='AnimePlayerLite',
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
	name='AnimePlayerLite'
)


# ---
# merge_utility.spec

merge_utility_path = os.path.join(os.getcwd(), "merge_utility.py")

with open('merge_utility.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_content = re.sub(
    r'^DB_FOLDER\s*=.*$',
    'DB_FOLDER = "db"',
    content,
    flags=re.MULTILINE
)

with open('merge_utility.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"✅ File {merge_utility_path} updated successfully.")

a = Analysis(['merge_utility.py'],
             pathex=[
                 project_dir,
                 PACKAGES_FOLDER,
             ],
             binaries=[
             ],
		 	 datas=[(os.path.join(project_dir, 'core/'), 'core'), (os.path.join(project_dir, '.env'), '.')],
             hiddenimports=[
                 'dotenv', 'sqlalchemy', 'pyzbar.pyzbar', 'PIL.Image', 'importlib.util', 'sqlite3', 'base64', 'qrcode', 'pyzipper'
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
        print(f"✅ {checksum} INJECT {status}")
else:
    print(f"❌ Error: Target binary {binary_file_path} does not exist.")


# ---
# sync.spec

pyzbar_libs_path = os.path.join(PACKAGES_FOLDER, 'pyzbar')
pyzbar_lib_path1 = os.path.join(pyzbar_libs_path, 'libiconv.dll')
pyzbar_lib_path2 = os.path.join(pyzbar_libs_path, 'libzbar-64.dll')

if not os.path.exists(pyzbar_lib_path1):
    print(f"⚠️ File not found: {pyzbar_lib_path1}")
if not os.path.exists(pyzbar_lib_path2):
    print(f"⚠️ File not found: {pyzbar_lib_path2}")

a = Analysis(
    ['sync.py'],
	pathex=[
	 project_dir,
	PACKAGES_FOLDER
	],
	binaries=[
        (pyzbar_lib_path1, '.'),
        (pyzbar_lib_path2, '.')
	],
    datas=[],
 	hiddenimports=[
                 'dotenv', 'pyzipper',
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
compiled_dir3 = os.path.join(dist_dir, 'AnimePlayerLite')
binary_file1 = os.path.join(compiled_dir2, 'sync.exe')
binary_file_path1 = os.path.join(compiled_dir1, 'sync.exe')
binary_file2 = os.path.join(compiled_dir2, 'libiconv.dll')
binary_file_path2 = os.path.join(compiled_dir1, 'libiconv.dll')
binary_file3 = os.path.join(compiled_dir2, 'libzbar-64.dll')
binary_file_path3 = os.path.join(compiled_dir1, 'libzbar-64.dll')

shutil.copyfile(binary_file1, binary_file_path1)
shutil.copyfile(binary_file2, binary_file_path2)
shutil.copyfile(binary_file3, binary_file_path3)

def delete_folders(target_dir, folder_patterns):
    for pattern in folder_patterns:
        full_pattern = os.path.join(target_dir, pattern)
        for folder_path in glob.glob(full_pattern):
            if os.path.isdir(folder_path):
                shutil.rmtree(folder_path)
                print(f"✅ Deleted: {folder_path}")

folders_to_delete = {
    compiled_dir1: [
        "importlib_metadata-*.dist-info",
        "MarkupSafe-*.dist-info",
        "numpy-*.dist-info",
        "h2-*.dist-info",
        "cryptography-*.dist-info",
        "attrs-*.dist-info",
        "cryptography",  # security vendor flagged this file as malicious by VirusTotal
        "charset_normalizer",  # security vendor flagged this file as malicious by VirusTotal
        "markupsafe",  # security vendor flagged this file as malicious by VirusTotal
    ],
    compiled_dir3: [
        "h2-*.dist-info",
        "charset_normalizer"  # security vendor flagged this file as malicious by VirusTotal
    ]
}

for target_dir, patterns in folders_to_delete.items():
    delete_folders(target_dir, patterns)

def delete_files(target_dir, file_patterns):
    for pattern in file_patterns:
        full_pattern = os.path.join(target_dir, pattern)
        for file_path in glob.glob(full_pattern):
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    print(f"✅ Deleted file: {file_path}")
                except Exception as e:
                    print(f"❌ Error deleting {file_path}: {e}")
            else:
                print(f"⚠️ Skipping non-file: {file_path}")


target_folder = os.path.join(compiled_dir1, "PIL")
files_to_delete = [
    "_imagingtk.cp312-win_amd64.pyd", # security vendor flagged this file as malicious by VirusTotal
    "_webp.cp312-win_amd64.pyd", # security vendor flagged this file as malicious by VirusTotal
]

delete_files(target_folder, files_to_delete)

backup_folder = os.path.join(os.path.expanduser("~"), "Desktop", "db")
post_build_db = os.path.join(os.getcwd(), "dist", "AnimePlayer", "db", "anime_player.db")

def get_latest_backup(folder):
    """Finds the last created file in a folder."""
    try:
        files = [f for f in os.listdir(folder) if f.endswith(".db")]
        if not files:
            return None
        latest_file = max(files, key=lambda f: os.path.getmtime(os.path.join(folder, f)))
        return os.path.join(folder, latest_file)
    except Exception as e:
        print(f"❌ Error searching for last backup: {e}")
        return None

def get_file_info(file_path):
    """Returns the size and modification date of a file"""
    if not os.path.exists(file_path):
        return None, None
    size = os.path.getsize(file_path)
    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
    return size, modified_time

pre_build_db = get_latest_backup(backup_folder)

pre_size, pre_time = get_file_info(pre_build_db) if pre_build_db else (None, None)
post_size, post_time = get_file_info(post_build_db)

print("\n📂 **Database comparison**")

if pre_build_db:
    print(f"🔹 Last backup before build: {pre_build_db}")
    print(f"   - Size: {pre_size} byte")
    print(f"   - Last modified: {pre_time}")
else:
    print("❌ Backup before assembly not found.")

if post_size:
    print(f"\n🔹 DB after build {post_build_db}")
    print(f"   - Size: {post_size} byte")
    print(f"   - Last modified: {post_time}")
else:
    print("\n❌ The database is missing after assembly.")

if pre_size and post_size:
    if pre_time > post_time:
        print("\n⚠️ **ATTENTION: The backup is newer than the database after the build!**")
    elif pre_time == post_time:
        print("\n✅ **Databases match. No changes found.**")
    else:
        print("\n✅ **The database after the build is newer than the backup.**")