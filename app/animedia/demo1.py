# в файле, где объявлен класс AnimePlayerAppVer3
from PyQt5.QtWidgets import QMessageBox, QWidget
from app.animedia.qt_async_worker import AsyncWorker
from app.animedia.animedia_adapter import AnimediaAdapter

class AnimePlayerAppVer3(QWidget):
    # … ваш существующий код …

    def start_animedia_search(self, title: str):
        """
        Вызывается, например, из обработчика кнопки «Найти».
        Запускает асинхронный парсер в отдельном потоке.
        """
        adapter = AnimediaAdapter(self.base_url)   # base_url берём из конфига

        # создаём поток‑рабочий
        self._animedia_thread = AsyncWorker(
            adapter.get_by_title, title, max_titles=5
        )
        self._animedia_thread.finished.connect(self._on_animedia_result)
        self._animedia_thread.error.connect(self._on_animedia_error)
        self._animedia_thread.start()

    # -----------------------------------------------------------------
    # Слоты, получающие результат
    # -----------------------------------------------------------------
    def _on_animedia_result(self, data: list):
        """
        `data` – список словарей, который вернул `get_by_title`.
        Здесь можно сохранить в БД, отобразить в UI и т.п.
        """
        self.logger.info(f"Получено {len(data)} записей от Animedia")
        # пример: добавить в базу
        for record in data:
            self.db_manager.save_anime_record(record)   # ваш метод
        # обновить UI, если нужно
        self.display_titles(start=True)

    def _on_animedia_error(self, msg: str):
        self.logger.error(f"Ошибка парсинга Animedia: {msg}")
        # показать пользователю
        QMessageBox.critical(self, "Ошибка", f"Не удалось получить данные:\n{msg}")


    def get_title(self):
        # Внутри AnimePlayerAppVer3, после init_ui()
        self.search_button.clicked.connect(
            lambda: self.start_animedia_search(self.title_search_entry.text())
        )