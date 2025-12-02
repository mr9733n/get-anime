# playerDBsync.spec
import glob
import os
import shutil
import site
import sys
import uuid
import tempfile

from pathlib import Path
from PyInstaller.building.api import PYZ, COLLECT, EXE
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs, collect_data_files
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct

# Compatibility shim: PyInstaller 5.x removed 'Version'. Build VSVersionInfo from simple kwargs.
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

# .env for future implementation send via inet

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
# ----

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

datas += [(os.path.join(project_dir, "app", "sync"), "app")]
datas += [(os.path.join(project_dir, "favicon.ico"), ".")]
datas += [(str(build_env_path), ".")]
datas += [(os.path.join(project_dir, "scripts", "allow_port_8765.cmd", "."))]
datas += [(os.path.join(project_dir, "scripts", "remove_port_8765.cmd", "."))]

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
             excludes=['PIL', 'numpy', 'psutils'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
#          exclude_binaries=True,
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

#coll = COLLECT(exe,
#               a.scripts,
#               a.binaries,
#               a.zipfiles,
#               a.datas,
#               strip=False,
#               upx=True,
#               upx_exclude=[],
#               name='PlayerDBSync')

dist_dir = os.path.join(project_dir, 'dist')
compiled_dir1 = os.path.join(dist_dir, 'PlayerDBSync')

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
        "typeguard-*.dist-info",
        "wheel-*.dist-info",

    ],
}

for target_dir, patterns in folders_to_delete.items():
    delete_folders(target_dir, patterns)