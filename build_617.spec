# -*- mode: python ; coding: utf-8 -*-
# For python version 3.12.x

import os
import platform
import re
import site
import sys
import uuid
import glob
import shutil
import hashlib
import tempfile
import compileall
import playwright

from datetime import datetime
from pathlib import Path
from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs, collect_data_files
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct

APP_DIR = "app"
APP_DIR_NAME = "qt"
APP_DIR_NAME1 = "tinker_v1"
BUILD_FILE = "main.py"
BUILD_FILE1 = "vlc_player.py"
BUILD_FILE2 = "app.py"

# Compatibility shim: PyInstaller 6.x removed 'Version'. Build VSVersionInfo from simple kwargs.
def Version(*, file_version, product_version, company_name, file_description, internal_name, legal_copyright, original_filename, product_name):
    def _tuple4(v):
        parts = [int(p) for p in str(v).split('.') if p.isdigit()]
        parts = (parts + [0,0,0,0])[:4]
        return tuple(parts)
    filevers = _tuple4(file_version)
    prodvers = _tuple4(product_version)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=filevers,
            prodvers=prodvers,
            mask=0x3f,
            flags=0x0,
            OS=0x4,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo([
                StringTable('040904B0', [
                    StringStruct('CompanyName', company_name),
                    StringStruct('FileDescription', file_description),
                    StringStruct('FileVersion', str(file_version)),
                    StringStruct('InternalName', internal_name),
                    StringStruct('LegalCopyright', legal_copyright),
                    StringStruct('OriginalFilename', original_filename),
                    StringStruct('ProductName', product_name),
                    StringStruct('ProductVersion', str(product_version)),
                ])
            ]),
            VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
        ]
    )

# ---
# main.spec

def calculate_sha256(file_path):
    hash_function = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_function.update(chunk)
    return hash_function.hexdigest()

def current_platform():
    cur_pl = platform.system()
    return cur_pl

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

# Config.ini
config_path = os.path.join(project_dir, "config", "config.ini")
temp_config_dir = Path(tempfile.mkdtemp(prefix="build_config_"))
build_config_path = temp_config_dir / 'config.ini'

replacements = {
    "USE_GIT_VERSION": "0",
}

if config_path:
    shutil.copy(config_path, build_config_path)
    with open(build_config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    with open(build_config_path, 'w', encoding='utf-8') as f:
        for line in lines:
            replaced = False
            for key, new_value in replacements.items():
                if line.startswith(key + "="):
                    f.write(f"{key}={new_value}")
                    replaced = True
                    break
            if not replaced:
                f.write(line)

        prod_key = str(uuid.uuid4())
        f.write(f"PROD_KEY={prod_key}\n")
        os.environ["PROD_KEY"] = prod_key
    print(f"✅ Temporary config.ini file created and modified: {build_config_path}")

# Compile the files in the 'app' directory
compileall.compile_dir('app', force=True)

# Compile the files in the 'core' directory
compileall.compile_dir('core', force=True)

# Compile the files in the 'utils' directory
compileall.compile_dir('utils', force=True)

# Compile the files in the 'templates' directory
compileall.compile_dir('templates', force=True)

datas = [
    (os.path.join(project_dir, 'static/*'), 'static'),
    (os.path.join(project_dir, 'templates/'), 'templates'),
    (os.path.join(project_dir, 'config/logging.conf'), 'config'),
    (os.path.join(project_dir, 'db/*'), 'db'),
    #(os.path.join(project_dir, 'app/qt'), 'app/qt'),
    #(os.path.join(project_dir, 'core/'), 'core'),
    #(os.path.join(project_dir, 'utils/'), 'utils'),
    #(os.path.join(project_dir, 'utils/animedia/'), 'utils/animedia'),
    (os.path.join(project_dir, 'libs/'), 'libs'),
    (os.path.join(project_dir, 'app/qt/__pycache__'), 'app/qt/__pycache__'),  # Add compiled .pyc files
    (os.path.join(project_dir, 'core/__pycache__'), 'core/__pycache__'),      # Add compiled .pyc files
    (os.path.join(project_dir, 'utils/__pycache__'), 'utils/__pycache__'),    # Add compiled .pyc files
	(os.path.join(project_dir, 'favicon.ico'), '.'),
	(os.path.join(project_dir, 'anime_player_app_roadmap.md'), '.'),
	(os.path.join(project_dir, 'LICENSE.md'), '.'),
	(os.path.join(project_dir, 'README.md'), '.'),
	(os.path.join(project_dir, 'sql_commands.md'), '.'),
	(str(build_config_path), 'config/.')
]

# ---
# vlc_player.spec

print("\n--- Building VLC Player ---")
block_cipher = None
project_dir = os.getcwd()
vlc_player_name = "AnimePlayerVlc"

# Analyze VLC player script
v = Analysis(
    [f'{APP_DIR}/{APP_DIR_NAME}/{BUILD_FILE1}'],
    pathex=[
        project_dir,
        PACKAGES_FOLDER,
    ],
    binaries=[],
    datas=[
        (os.path.join(project_dir, 'config/logging.conf'), 'config'),
        (os.path.join(project_dir, 'static/icon.png'), 'static'),
    ],
    hiddenimports=[
        'logging.config',
        'ctypes',
        'vlc',
        're',
        'json',
        'base64',
        'time',
        'argparse',
        'utils.runtime_manager',
        'setproctitle',
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

pyz_vlc = PYZ(v.pure, v.zipped_data, cipher=block_cipher)

block = {
    "FileVersion": "0.3.8.32",
    "ProductVersion": "0.3.8",
    "CompanyName": "666s.dev",
    "FileDescription": "AnimePlayerVlc",
    "InternalName": "AnimePlayerVlc",
    "LegalCopyright": "© 2025 666s.dev",
    "OriginalFilename": "AnimePlayerVlc.exe",
    "ProductName": "AnimePlayerVlc",
}

version_resource = Version(
    file_version=block["FileVersion"],
    product_version=block["ProductVersion"],
    company_name=block["CompanyName"],
    file_description=block["FileDescription"],
    internal_name=block["InternalName"],
    legal_copyright=block["LegalCopyright"],
    original_filename=block["OriginalFilename"],
    product_name=block["ProductName"],
)

exe_vlc = EXE(
    pyz_vlc,
    v.scripts,
    [],
    exclude_binaries=True,
    name=vlc_player_name,
    icon='favicon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=False,
    version=version_resource,
    onefile=False,
)

coll_vlc = COLLECT(
    exe_vlc,
    v.binaries,
    v.zipfiles,
    v.datas,
    strip=False,
    name=vlc_player_name
)

# Copy VLC player to the main application directory and calculate its hash
dist_dir = os.path.join(project_dir, 'dist')
compiled_dir1 = os.path.join(dist_dir, 'AnimePlayer')
vlc_player_compiled_dir = os.path.join(dist_dir, vlc_player_name)

# Source and destination paths
# TODO: add for MacOS & Linux platforms
current_platform = current_platform()
if current_platform == "Windows":
    vlc_player_name = vlc_player_name + '.exe'
vlc_binary_source = os.path.join(vlc_player_compiled_dir, vlc_player_name)

vlc_hash = calculate_sha256(vlc_binary_source)
app_path = os.path.join(project_dir, 'app', 'qt', 'app.py')

try:
    with open(app_path, "r+", encoding="utf-8") as f:
        content = f.read()
        # Check if VLC_PLAYER_HASH constant exists, otherwise add it
        if "VLC_PLAYER_HASH" in content:
            updated_content = re.sub(
                r'VLC_PLAYER_HASH\s*=\s*".*?"',
                f'VLC_PLAYER_HASH = "{vlc_hash}"',
                content
            )
        else:
            # Find a good place to insert the constant - after imports but before class definition
            import_section_end = content.find("class AnimePlayerAppVer3")
            if import_section_end > 0:
                updated_content = (
                        content[:import_section_end] +
                        f"\n# Hash of compiled VLC player executable\nVLC_PLAYER_HASH = \"{vlc_hash}\"\n\n" +
                        content[import_section_end:]
                )
            else:
                # If can't find class definition, add at the top
                updated_content = f"# Hash of compiled VLC player executable\nVLC_PLAYER_HASH = \"{vlc_hash}\"\n\n" + content

        f.seek(0)
        f.write(updated_content)
        f.truncate()
    print(f"✅ Updated app.py with VLC player hash: {vlc_hash}")
except Exception as e:
    print(f"❌ Error updating app.py with VLC player hash: {e}")

# ---
# AnimePlayer Main

block = {
    "FileVersion": "0.3.8.32",
    "ProductVersion": "0.3.8",
    "CompanyName": "666s.dev",
    "FileDescription": "AnimePlayer",
    "InternalName": "AnimePlayer",
    "LegalCopyright": "© 2025 666s.dev",
    "OriginalFilename": "AnimePlayer.exe",
    "ProductName": "AnimePlayer",
}

version_resource = Version(
    file_version=block["FileVersion"],
    product_version=block["ProductVersion"],
    company_name=block["CompanyName"],
    file_description=block["FileDescription"],
    internal_name=block["InternalName"],
    legal_copyright=block["LegalCopyright"],
    original_filename=block["OriginalFilename"],
    product_name=block["ProductName"],
)

a = Analysis(
    [BUILD_FILE],
    pathex=[
        project_dir,
		PACKAGES_FOLDER,
    ],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pkg_resources',
        'vlc',
        'pkg_resources.extern',
		'multiprocessing',
		'requests.compat', # ???
		'cryptography',
		'PIL.Image',
		'numpy',  # Used conditionally in PIL
		'sqlalchemy.dialects.sqlite',
		'urllib3.contrib.socks', # ???
        'httpx',
        'uuid',
        'jinja2',
        'beautifulsoup4',
        'python-vlc',
		'sqlalchemy',
		'sqlalchemy.orm',
		'sqlalchemy.ext.declarative',
		'sqlalchemy.engine',
		'sqlalchemy.sql',
        'app.qt.app',
        'app.qt.app_handlers',
        'app.qt.app_helpers',
        'static.layout_metadata',
        'app.qt.app_state_manager',
        'app.qt.ui_manager',
        'app.qt.ui_generator',
        'app.qt.ui_s_generator',
        'core.database_manager',
        'core.get',
        'core.save',
        'core.process',
        'core.tables',
        'core.utils',
        'utils.anilibria.api_adapter',
        'utils.anilibria.api_client',
        'utils.animedia.animedia_adapter',
        'utils.animedia.animedia_client',
        'utils.animedia.animedia_utils',
        'utils.animedia.qt_async_worker',
        'utils.config_manager',
        'utils.library_loader',
        'utils.logging_handlers',
        'utils.playlist_manager',
        'utils.poster_manager',
        'utils.runtime_manager',
        'utils.torrent_manager',
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
	console=False,
    version=version_resource,
	onefile=False,  # Important for imports to set to False to keep everything in the same folder
	)

coll = COLLECT(
	exe,
	a.binaries,
	a.zipfiles,
	a.datas,
	strip=False,
	name='AnimePlayer'
	)


# ---
# anime_player_lite.spec

block_cipher = None
project_dir = os.getcwd()

block = {
    "FileVersion": "0.1.10.0",
    "ProductVersion": "0.1.10",
    "CompanyName": "666s.dev",
    "FileDescription": "AnimePlayerLite",
    "InternalName": "AnimePlayerLite",
    "LegalCopyright": "© 2025 666s.dev",
    "OriginalFilename": "AnimePlayerLite.exe",
    "ProductName": "AnimePlayerLite",
}

version_resource = Version(
    file_version=block["FileVersion"],
    product_version=block["ProductVersion"],
    company_name=block["CompanyName"],
    file_description=block["FileDescription"],
    internal_name=block["InternalName"],
    legal_copyright=block["LegalCopyright"],
    original_filename=block["OriginalFilename"],
    product_name=block["ProductName"],
)

a = Analysis(
    [f'{APP_DIR}/{APP_DIR_NAME1}/{BUILD_FILE2}'],
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
	console=True,
    version=version_resource,
	onefile=False,  # Important for imports to set to False to keep everything in the same folder
)

coll = COLLECT(
    exe,
	a.binaries,
	a.zipfiles,
	a.datas,
	strip=False,
	name='AnimePlayerLite'
)

# Source and destination paths
vlc_binary_source = os.path.join(vlc_player_compiled_dir, vlc_player_name)
vlc_binary_dest = os.path.join(compiled_dir1, vlc_player_name)

# Copy the VLC player executable to the main app directory
if os.path.exists(vlc_binary_source):
    shutil.copyfile(vlc_binary_source, vlc_binary_dest)
    print(f"✅ Copied VLC player executable to main application directory")
else:
    print(f"❌ Error: VLC player executable not found at {vlc_binary_source}")

# ---
dist_dir = os.path.join(project_dir, 'dist')
compiled_dir1 = os.path.join(dist_dir, 'AnimePlayer', '_internal')
compiled_dir3 = os.path.join(dist_dir, 'AnimePlayerLite', '_internal')


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

target_folders = []
files_to_delete = []
target_folders += os.path.join(compiled_dir1, "PIL")
files_to_delete += [
    "_imagingtk.cp312-win_amd64.pyd", # security vendor flagged this file as malicious by VirusTotal
    "_webp.cp312-win_amd64.pyd", # security vendor flagged this file as malicious by VirusTotal
]

for target_folder in target_folders:
    delete_files(target_folder, files_to_delete)

dest_dir1 = os.path.join(dist_dir, 'AnimePlayer')
dest_dir3 = os.path.join(dist_dir, 'AnimePlayerLite')

folders_mapping = {
    compiled_dir1: (
        dest_dir1,
        [
            "app",
            "config",
            "core",
            "db",
            "libs",
            "static",
            "templates",
            "utils",
        ],
    ),
    compiled_dir3: (
        dest_dir3,
        [
            "config",
        ],
    ),
}

def move_folders(mapping: dict[str, tuple[str, list[str]]]):
    """
    mapping: { source_root: (dest_root, [ "app", "config", ... ]) }
    """
    for src_root, (dest_root, patterns) in mapping.items():
        for name in patterns:
            src_path = os.path.join(src_root, name)
            dst_path = os.path.join(dest_root, name)

            if not os.path.exists(src_path):
                print(f"⚠️ Skip (no such source): {src_path}")
                continue

            # убеждаемся, что целевая папка существует
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

            print(f"➡️ move {src_path} → {dst_path}")
            shutil.move(src_path, dst_path)

        print(f"✅ Done for {src_root} → {dest_root}")

move_folders(folders_mapping)

def copy_file(src: str, dst_dir: str):
    src_path = Path(src)
    if not src_path.exists() or not src_path.is_file():
        print(f"⚠ Skip copy: source file not found → {src_path}")
        return

    dst_dir_path = Path(dst_dir)
    dst_dir_path.mkdir(parents=True, exist_ok=True)
    dst_path = dst_dir_path / src_path.name
    compiled_dir4 = os.path.join(dist_dir, 'AnimePlayer', 'static', 'rus')
    shutil.copy2(src_path, dst_path)
    print(f"📄 Copied file: {src_path} → {dst_path}")

files_to_copy = {
    "files": [
        os.path.join(compiled_dir1, "anime_player_app_roadmap.md"),
        os.path.join(compiled_dir1, "LICENSE.md"),
        os.path.join(compiled_dir1, "sql_commands.md"),
        os.path.join(compiled_dir1, "README.md"),
    ],
}

for file in files_to_copy["files"]:
    copy_file(file, dest_dir1)

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

def restore_database(src, dst):
    """Restores the database from a backup."""
    try:
        shutil.copy2(src, dst)
        print(f"\n✅ The database has been successfully restored from:\n   {src} ➝ {dst}")
    except Exception as e:
        print(f"\n❌ Failed to restore database: {e}")

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
    print(f"\n🔹 DB after build: {post_build_db}")
    print(f"   - Size: {post_size} byte")
    print(f"   - Last modified: {post_time}")
else:
    print("\n❌ The database is missing after assembly.")

if pre_size and post_size:
    restore_needed = False

    if pre_time > post_time:
        print("\n⚠️ **ATTENTION: The backup is newer than the database after the build!**")
        restore_needed = True
    elif pre_time < post_time:
        if post_size < pre_size:
            print("\n⚠️ **WARNING: The new database is smaller than the backup! Data loss is possible!**")
            restore_needed = True
        else:
            print("\n✅ **The database after the build is newer than the backup.**")
    else:
        if pre_size != post_size:
            print("\n⚠️ **ATTENTION: The databases were modified at the same time, but the sizes are different!**")
            restore_needed = True
        else:
            print("\n✅ **Databases match. No changes found.**")

    if restore_needed:
        user_input = input("\n🔥️ WARNING: The databases are different.\nDo you want to restore the database from the last backup? (y/N): ").strip().lower()
        if user_input == 'y':
            restore_database(pre_build_db, post_build_db)
        else:
            print("\n❌ Database restoration canceled.")