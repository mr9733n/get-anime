import sys
import os
import subprocess


def restart_application():
    """Перезапускает приложение, учитывая, скрипт это или скомпилированный .exe/.app"""
    try:
        python_exec = sys.executable  # Путь к текущему исполняемому файлу

        if getattr(sys, 'frozen', False):  # Если приложение скомпилировано (PyInstaller)
            subprocess.Popen([python_exec] + sys.argv)  # Запускаем новый процесс
            os._exit(0)  # Завершаем текущий процесс
        else:  # Обычный Python-скрипт
            os.execl(python_exec, python_exec, *sys.argv)

    except Exception as e:
        print(f"Ошибка при перезапуске: {e}")