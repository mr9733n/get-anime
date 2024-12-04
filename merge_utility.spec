# merge_utility.spec
block_cipher = None

a = Analysis(['merge_utility.py'],
             pathex=[
                 'F:\\9834758345hf7A\\Anime4.1\\get-anime',  # Путь к проекту
                 'C:\\users\\cicada\\appdata\\local\\programs\\python\\python312\\lib\\site-packages',  # Путь к site-packages
             ],
             binaries=[
                 ('C:\\users\\cicada\\appdata\\local\\programs\\python\\python312\\lib\\site-packages\\pyzbar\\libiconv.dll', '.'),
                 ('C:\\users\\cicada\\appdata\\local\\programs\\python\\python312\\lib\\site-packages\\pyzbar\\libzbar-64.dll', '.')
             ],
             datas=[
             ],
             hiddenimports=[
                 'dotenv', 'sqlalchemy', 'pyzbar.pyzbar', 'PIL.Image', 'aiohttp'
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
          exclude_binaries=False,
          name='merge_utility',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          onefile=True)

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='merge_utility')
