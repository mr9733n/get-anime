# playerDBsync.spec
import glob
import os
import shutil
import site
import sys
import uuid
import tempfile
import av, pylibsrtp

from pathlib import Path
from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs, collect_data_files
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct


BUILD_ONEFILE = True
BUILD_USE_ENV = False

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
block_cipher = None

# Pre-build
# .env for future implementation send via inet
env_path = Path(project_dir) / '.env'
temp_env_dir = Path(tempfile.mkdtemp(prefix="build_env_"))
build_env_path = temp_env_dir / '.env'

if BUILD_USE_ENV:
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

# ----
# AnimePlayerDBSync_Full.spec
block = {
    "FileVersion": "0.0.0.1",
    "ProductVersion": "0.0.0.1",
    "CompanyName": "666s.dev",
    "FileDescription": "AnimePlayerDBSyncUtilityApp",
    "InternalName": "AnimePlayerDBSyncUtilityApp",
    "LegalCopyright": "© 2025 666s.dev",
    "OriginalFilename": "PlayerDBSync.exe",
    "ProductName": "AnimePlayerDBSyncUtilityApp",
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
hidden = []
datas = []
binaries = []

# ---- PyNaCl / cffi ----
hidden += collect_submodules("nacl")
hidden += ["_cffi_backend", "cffi", "cffi.backend_ctypes"]
binaries += collect_dynamic_libs("nacl")       # libsodium/*.pyd/*.dll если есть
binaries += collect_dynamic_libs("cffi")       # _cffi_backend.pyd подтянуть наверняка

# ---- zeroconf (иногда нужны data-файлы) ----
datas += collect_data_files("zeroconf", include_py_files=True)
hidden += collect_submodules("zeroconf")
binaries += collect_dynamic_libs("zeroconf")

# ---- Tkinter: TCL/TK data ----
# PyInstaller обычно сам кладёт, но если ошибка есть — добавляем явно:
tcl_base = os.path.join(sys.base_prefix, "tcl")
tcl86 = os.path.join(tcl_base, "tcl8.6")
tk86  = os.path.join(tcl_base, "tk8.6")
if os.path.isdir(tcl86) and os.path.isdir(tk86):
    datas += [(tcl86, "tcl/tcl8.6")]
    datas += [(tk86,  "tcl/tk8.6")]

datas +=[(str(Path(av.__file__).parent), "av")]
datas +=[(str(Path(pylibsrtp.__file__).parent), "pylibsrtp")]
datas += [(os.path.join(project_dir, "app", "sync"), "app")]
datas += [(os.path.join(project_dir, "favicon.ico"), ".")]
if BUILD_USE_ENV:
    datas += [(str(build_env_path), ".")]

icon_path = os.path.join(project_dir, "favicon.ico")

a = Analysis(['app/sync/db_sync_gui.py'],
             pathex=[
                 project_dir,
                 PACKAGES_FOLDER,
             ],
             binaries=binaries,
             datas=datas,
             hiddenimports=hidden + [
                 "zeroconf",
                 "nacl",
                 "aiortc",
                 "aioice",
                 'aiofiles',
                 "av",
                 "pyee",
                 "pylibsrtp",
                 "crc32c",
                 'tkinter',
                 'tkinter.ttk'
             ],
             hookspath=['.'],
             runtime_hooks=[],
             excludes=['PIL', 'numpy', 'psutils'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

if BUILD_ONEFILE:
    exe = EXE(
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='PlayerDBSync',
        icon=icon_path,
        console=False,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        version=version_resource,
        onefile=True
    )
else:
    exe = EXE(
        pyz,
        exclude_binaries=True,
        name='PlayerDBSync',
        icon=icon_path,
        console=False,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        version=version_resource,
        onefile=False
    )

    coll = COLLECT(
        exe,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='PlayerDBSync'
    )

# ----
# AnimePlayerDBSync Lite (only Local LAN)
block = {
    "FileVersion": "0.0.0.1",
    "ProductVersion": "0.0.0.1",
    "CompanyName": "666s.dev",
    "FileDescription": "AnimePlayerDBSyncLANUtilityApp",
    "InternalName": "AnimePlayerDBSyncLANUtilityApp",
    "LegalCopyright": "© 2025 666s.dev",
    "OriginalFilename": "PlayerDBSyncLAN.exe",
    "ProductName": "AnimePlayerDBSyncLANUtilityApp",
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
hidden = []
datas = []
binaries = []

# ---- PyNaCl / cffi ----
hidden += collect_submodules("nacl")
hidden += ["_cffi_backend", "cffi", "cffi.backend_ctypes"]
binaries += collect_dynamic_libs("nacl")       # libsodium/*.pyd/*.dll если есть
binaries += collect_dynamic_libs("cffi")       # _cffi_backend.pyd подтянуть наверняка

# ---- zeroconf (иногда нужны data-файлы) ----
datas += collect_data_files("zeroconf", include_py_files=True)
hidden += collect_submodules("zeroconf")
binaries += collect_dynamic_libs("zeroconf")

# ---- Tkinter: TCL/TK data ----
# PyInstaller обычно сам кладёт, но если ошибка есть — добавляем явно:
tcl_base = os.path.join(sys.base_prefix, "tcl")
tcl86 = os.path.join(tcl_base, "tcl8.6")
tk86  = os.path.join(tcl_base, "tk8.6")
if os.path.isdir(tcl86) and os.path.isdir(tk86):
    datas += [(tcl86, "tcl/tcl8.6")]
    datas += [(tk86,  "tcl/tk8.6")]

datas += [(os.path.join(project_dir, "app", "sync"), "app")]
datas += [(os.path.join(project_dir, "favicon.ico"), ".")]

icon_path = os.path.join(project_dir, "favicon.ico")

a = Analysis(['app/sync/db_sync_gui.py'],
             pathex=[
                 project_dir,
                 PACKAGES_FOLDER,
             ],
             binaries=binaries,
             datas=datas,
             hiddenimports=hidden + ['nacl', 'zeroconf', 'aiofiles', 'tkinter', 'tkinter.ttk'],
             hookspath=['.'],
             runtime_hooks=[],
             excludes=['PIL', 'numpy', 'psutils', 'av', 'pylibsrtp'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

if BUILD_ONEFILE:
    exe = EXE(pyz,
              a.scripts,
              a.binaries,
              a.zipfiles,
              a.datas,
              [],
              name='PlayerDBSyncLAN',
              icon=icon_path,
              console=False,
              debug=False,
              bootloader_ignore_signals=False,
              strip=False,
              upx=True,
              version=version_resource,
              onefile=True
              )
else:
    exe = EXE(
        pyz,

        exclude_binaries=True,
        name='PlayerDBSyncLAN',
        icon=icon_path,
        console=False,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        version=version_resource,
        onefile=False
    )

    coll = COLLECT(
        exe,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='PlayerDBSyncLAN'
    )

def delete_folders(target_dir: Path, folder_patterns):
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"⚠ Skip cleanup: target dir does not exist → {target_dir}")
        return

    for pattern in folder_patterns:
        full_pattern = target_dir / pattern
        for folder_path in glob.glob(str(full_pattern)):
            folder_path = Path(folder_path)
            if folder_path.is_dir():
                shutil.rmtree(folder_path)
                print(f"✅ Deleted: {folder_path}")
            else:
                print(f"⚠ Skip (not a dir): {folder_path}")

def copy_tree(src: Path, dst: Path):
    if not src.exists() or not src.is_dir():
        print(f"⚠ Skip copy: source folder not found → {src}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src, dst)
    print(f"📁 Copied folder: {src} → {dst}")

def copy_file(src: Path, dst: Path):
    if not src.exists() or not src.is_file():
        print(f"⚠ Skip copy: source file not found → {src}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"📄 Copied file: {src} → {dst}")

# Post Build
dist_dir = Path(project_dir) / "dist"
compiled_dir1 = dist_dir / "PlayerDBSync"  # onedir
onefile_exe = dist_dir / "PlayerDBSync.exe"
build_successful = compiled_dir1.exists() or onefile_exe.exists()

if not build_successful:
    print("⚠ Билд не найден, пропускаю post-processing (копирование/удаление).")

else:
    binary_dest_dir = dist_dir / "AnimePlayer"

    files_to_copy = {
        "folders": [
            Path(project_dir) / "app/sync/scripts",
        ],
        "files": [
            dist_dir / "PlayerDBSync.exe",
            dist_dir / "PlayerDBSyncLAN.exe",
        ],
    }

    if build_successful:
        for folder in files_to_copy["folders"]:
            dest = binary_dest_dir / folder.name
            copy_tree(folder, dest)

        for file_path in files_to_copy["files"]:
            dest = binary_dest_dir / file_path.name
            copy_file(file_path, dest)
    else:
        print("⚠ Build not successful, skip copying files/folders.")

    folders_to_delete = {
        compiled_dir1: [
            "importlib_metadata-*.dist-info",
            "MarkupSafe-*.dist-info",
            "numpy-*.dist-info",
            "h2-*.dist-info",
            "cryptography-*.dist-info",
            "attrs-*.dist-info",
            "cryptography",
            "charset_normalizer",
            "markupsafe",
            "typeguard-*.dist-info",
            "wheel-*.dist-info",
        ],
    }

    if build_successful and not BUILD_ONEFILE:
        for target_dir, patterns in folders_to_delete.items():
            delete_folders(target_dir, patterns)
