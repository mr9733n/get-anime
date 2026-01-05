# runtime_manager.py
import ctypes
import sys
import os
import subprocess

from PyQt6.QtCore import QObject, pyqtSignal, Qt, QRunnable, QThreadPool, QTimer, QFileSystemWatcher
# from PyQt6.QtWidgets import QVBoxLayout, QTextEdit, QPushButton, QLabel, QWidget


def test_exception():
    raise RuntimeError("Test exception on quit")

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

class LogWorkerSignals(QObject):
    """Сигналы для обновления UI из фонового потока."""
    logLoaded = pyqtSignal(str)  # Сигнал для передачи текста логов в UI

class LogWorker(QRunnable):
    """Фоновая задача для загрузки логов без зависания интерфейса."""
    def __init__(self, log_file):
        super().__init__()
        self.log_file = log_file
        self.signals = LogWorkerSignals()  # Создаем сигналы

    def run(self):
        """Читает лог-файл в фоне и отправляет результат в UI-поток через сигнал."""
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            reversed_logs = "".join(lines[::-1])  # Переворачиваем порядок строк
            self.signals.logLoaded.emit(reversed_logs)  # Отправляем текст в UI
        except Exception as e:
            self.signals.logLoaded.emit(f"Ошибка загрузки логов: {e}")

