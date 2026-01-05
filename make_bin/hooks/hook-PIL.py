# make_bin/hooks/hook-PIL.py
"""
PyInstaller hook для PIL/Pillow.

Собирает:
- Все Python плагины
- Нативные библиотеки (webp, jpeg, png, etc.)
"""
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

# Собираем все подмодули PIL
hiddenimports = collect_submodules('PIL')

# Собираем нативные библиотеки (.dll/.so/.dylib)
# Это включает libwebp, libjpeg, libpng, etc.
binaries = collect_dynamic_libs('PIL')

# Дополнительные data files (если есть)
datas = []

print(f"[hook-PIL] Collected {len(hiddenimports)} submodules")
print(f"[hook-PIL] Collected {len(binaries)} binary libraries")