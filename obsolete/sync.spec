# -*- mode: python ; coding: utf-8 -*-

import os
import shutil

block_cipher = None
project_dir = os.getcwd()

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

dist_dir = os.path.join(project_dir, 'dist')
compiled_dir1 = os.path.join(dist_dir, 'AnimePlayer')
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