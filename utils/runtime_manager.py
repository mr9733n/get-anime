# runtime_manager.py
import ctypes
import sys
import os
import subprocess

from PyQt6.QtCore import QObject, pyqtSignal, Qt, QRunnable, QThreadPool, QTimer, QFileSystemWatcher
from PyQt6.QtWidgets import QVBoxLayout, QTextEdit, QPushButton, QLabel, QWidget


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

class LogWindow(QWidget):
    closed = pyqtSignal()

    def __init__(self, log_file, theme="default"):
        super().__init__()
        self.log_file = log_file
        self.thread_pool = QThreadPool.globalInstance()  # Создаем пул потоков
        self.setWindowTitle("Anime Player App Logs.")
        self.setGeometry(100, 100, 800, 600)

        # Основной layout
        layout = QVBoxLayout()

        # Текстовое поле для логов
        self.log_view = QTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setAlignment(Qt.AlignTop)  # Выравнивание текста сверху

        # Кнопка обновления логов
        self.refresh_button = QPushButton("UPDATE")
        self.refresh_button.clicked.connect(self.load_logs)

        # Информационная метка
        self.info_label = QLabel("⚡ Auto-updates every 60 seconds. 📜 Newest logs appear first.")
        self.info_label.setAlignment(Qt.AlignCenter)

        # Таймер для автообновления логов (каждые 60 секунд)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_logs)
        self.timer.start(60000)

        # Следим за изменением файла
        self.file_watcher = QFileSystemWatcher()
        self.file_watcher.addPath(self.log_file)
        self.file_watcher.fileChanged.connect(self.load_logs)

        # Применяем стили
        self.apply_theme(theme)

        # Загружаем логи при старте (асинхронно)
        self.load_logs()

        layout.addWidget(self.log_view)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.info_label)
        self.setLayout(layout)

    def load_logs(self):
        """Запускает фоновую загрузку логов."""
        worker = LogWorker(self.log_file)
        worker.signals.logLoaded.connect(self.update_log_view)  # Подключаем сигнал к UI-методу
        self.thread_pool.start(worker)

    def update_log_view(self, log_text):
        """Обновляет текстовое поле логов в UI-потоке."""
        self.log_view.setPlainText(log_text)
        self.log_view.verticalScrollBar().setValue(0)  # Прокрутка наверх

    def apply_theme(self, theme):
        """Применяет стили к окну логов в зависимости от шаблона"""
        if theme == "default":
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(240, 240, 240, 1.0);
                }
                QTextEdit {
                    background-color: white;
                    color: black;
                    font-family: Consolas, monospace;
                    font-size: 12px;
                }
                QPushButton {
                    background-color: #4a4a4a;
                    color: white;
                    border-radius: 6px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #5c5c5c;
                }
            """)
        elif theme == "no_background_night":
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(140, 140, 140, 1.0);
                }
                QTextEdit {
                    background-color: black;
                    color: lime;
                    font-family: Consolas, monospace;
                    font-size: 12px;
                    border: 1px solid gray;
                }
                QPushButton {
                    background-color: #2a2a2a;
                    color: white;
                    border-radius: 6px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #3a3a3a;
                }
            """)
        elif theme == "no_background":
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(220, 220, 220, 1.0);
                }
                QTextEdit {
                    background-color: white;
                    color: black;
                    font-family: Consolas, monospace;
                    font-size: 12px;
                }
                QPushButton {
                    background-color: #6a6a6a;
                    color: white;
                    border-radius: 6px;
                    padding: 8px;
                }
                QPushButton:hover {
                    background-color: #7a7a7a;
                }
            """)

    def set_theme(self, new_theme):
        """Позволяет менять тему во время работы"""
        self.apply_theme(new_theme)

    def closeEvent(self, event):
        """Перехватываем закрытие окна и испускаем сигнал."""
        self.closed.emit()  # Отправляем сигнал, что окно закрылось
        event.accept()  # Закрываем окно