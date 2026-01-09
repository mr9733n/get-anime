# make_bin/rthooks/rthook_pil_plugins.py
"""
Runtime hook для принудительной загрузки PIL плагинов.

Выполняется ДО запуска основного приложения.
"""
import sys


def _pil_imaging_init():
    """
    Инициализирует PIL плагины изображений при старте приложения.

    PIL использует lazy loading - плагины регистрируются только при первом
    обращении к формату. PyInstaller не видит эти динамические импорты,
    поэтому форсируем их загрузку здесь.
    """
    try:
        from PIL import Image

        # Явно импортируем нужные плагины
        # Это заставляет их зарегистрироваться в PIL.Image.MIME
        import PIL.JpegImagePlugin
        import PIL.PngImagePlugin
        import PIL.WebPImagePlugin  # ← Ключевой для WebP
        import PIL.GifImagePlugin
        import PIL.BmpImagePlugin
        import PIL.IcoImagePlugin

        # Дополнительно можно инициализировать плагины явно
        PIL.JpegImagePlugin._accept
        PIL.PngImagePlugin._accept
        PIL.WebPImagePlugin._accept
        PIL.GifImagePlugin._accept
        PIL.BmpImagePlugin._accept

        # Проверяем что плагины зарегистрированы
        registered_formats = list(Image.EXTENSION.keys())
        print(f"[PIL] Registered formats: {', '.join(registered_formats)}")

        if '.webp' not in registered_formats:
            print("[PIL] WARNING: WebP plugin not registered!")

    except ImportError as e:
        print(f"[PIL] Warning: Could not initialize PIL plugins: {e}")
        # Не фатально - основное приложение может работать
    except Exception as e:
        print(f"[PIL] Error during PIL initialization: {e}")


# Выполняем инициализацию при импорте хука
_pil_imaging_init()