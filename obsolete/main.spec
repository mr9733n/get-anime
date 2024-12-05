# main.spec
# -*- mode: python ; coding: utf-8 -*-

import compileall
import os
import shutil

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
import os

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
    (os.path.join(project_dir, 'app/qt/__pycache__'), 'app/qt/__pycache__'),  # Add compiled .pyc files
    (os.path.join(project_dir, 'core/__pycache__'), 'core/__pycache__'),      # Add compiled .pyc files
    (os.path.join(project_dir, 'utils/__pycache__'), 'utils/__pycache__'),    # Add compiled .pyc files
	(os.path.join(project_dir, 'favicon.ico'), '.')
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

dist_dir = os.path.join(project_dir, 'dist')
compiled_dir = os.path.join(dist_dir, 'AnimePlayer')

for_delete2 = compiled_dir = os.path.join(compiled_dir, 'importlib_metadata-8.0.0.dist-info')
for_delete3 = compiled_dir = os.path.join(compiled_dir, 'MarkupSafe-3.0.2.dist-info')

for path in [for_delete2, for_delete3]:
    if os.path.exists(path):
        shutil.rmtree(path)
        print(f"Deleted: {path}")