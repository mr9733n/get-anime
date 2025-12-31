from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget,
    QLineEdit, QLabel, QMessageBox, QInputDialog
)

class DeletedWindow(QWidget):
    def __init__(self, db_manager, button_style: str = "", line_edit_style: str = "", theme: str = "default"):

        super().__init__()
        self.db_manager = db_manager
        self.button_style = button_style
        self.line_edit_style = line_edit_style

        self.setWindowTitle("Deleted titles")
        self.setGeometry(100, 300, 700, 360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Deleted titles (is_deleted=1):"))

        self.lst = QListWidget(self)
        layout.addWidget(self.lst)

        self.input_ids = QLineEdit(self)
        self.input_ids.setPlaceholderText("title_id(s) comma-separated (for restore/purge)")
        if self.line_edit_style:
            self.input_ids.setStyleSheet(self.line_edit_style)
        layout.addWidget(self.input_ids)

        btn_row = QHBoxLayout()

        self.btn_refresh = QPushButton("REFRESH", self)
        self.btn_restore = QPushButton("RESTORE", self)
        self.btn_purge = QPushButton("PURGE FOREVER", self)

        if self.button_style:
            self.btn_refresh.setStyleSheet(self.button_style)
            self.btn_restore.setStyleSheet(self.button_style)
            self.btn_purge.setStyleSheet(self.button_style)

        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_restore)
        btn_row.addWidget(self.btn_purge)
        layout.addLayout(btn_row)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_restore.clicked.connect(self.restore)
        self.btn_purge.clicked.connect(self.purge)

        self.refresh()
        self._apply_theme(theme)

    def refresh(self):
        self.lst.clear()
        if not hasattr(self.db_manager, "get_deleted_titles"):
            self.lst.addItem("db_manager.get_deleted_titles not implemented")
            return

        titles = self.db_manager.get_deleted_titles(batch_size=300, offset=0)
        for t in titles:
            self.lst.addItem(f"{t.title_id} | {t.name_ru} | deleted_at={t.deleted_at}")

    def _parse_ids(self):
        ids_str = self.input_ids.text().strip()
        if not ids_str:
            return []
        return [int(x.strip()) for x in ids_str.split(",") if x.strip().isdigit()]

    def restore(self):
        ids = self._parse_ids()
        if not ids:
            QMessageBox.information(self, "Restore", "Введите title_id(ы) для восстановления.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm restore",
            f"Восстановить: {ids} ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        if not hasattr(self.db_manager, "restore_titles"):
            QMessageBox.warning(self, "Restore", "db_manager.restore_titles не реализован.")
            return

        self.db_manager.restore_titles(ids)
        self.input_ids.clear()
        self.refresh()

    def purge(self):
        ids = self._parse_ids()
        if not ids:
            QMessageBox.information(self, "Purge", "Введите title_id(ы) для удаления навсегда.")
            return

        confirm_text, ok = QInputDialog.getText(
            self,
            "Confirm purge",
            f"Это УДАЛИТ НАВСЕГДА (каскадно) тайтлы: {ids}\n\nВведите PURGE чтобы подтвердить:",
        )
        if not ok or confirm_text.strip().upper() != "PURGE":
            QMessageBox.information(self, "Purge", "Отменено.")
            return

        if not hasattr(self.db_manager, "purge_titles"):
            QMessageBox.warning(self, "Purge", "db_manager.purge_titles не реализован.")
            return

        result = self.db_manager.purge_titles(self.input_ids.text().strip())
        if not isinstance(result, dict):
            QMessageBox.warning(self, "Purge", f"Unexpected result from purge: {result}")
            return

        deleted = result.get("deleted", [])
        not_found = result.get("not_found", [])

        QMessageBox.information(
            self,
            "Purge result",
            f"Удалены навсегда: {deleted}\nНе найдены/не в корзине: {not_found}",
        )
        self.input_ids.clear()
        self.refresh()

    def _apply_theme(self, theme: str):
        bg = {
            "default": "rgba(240, 240, 240, 1.0)",
            "no_background_night": "rgba(140, 140, 140, 1.0)",
            "no_background": "rgba(220, 220, 220, 1.0)",
        }.get(theme, "rgba(240, 240, 240, 1.0)")

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg};
            }}
            QListWidget {{
                background: rgba(255,255,255,0.95);
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                font-size: 12px;
            }}
        """)
