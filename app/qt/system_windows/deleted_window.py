from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget,
    QLineEdit, QLabel, QMessageBox, QInputDialog
)

class DeletedWindow(QWidget):
    def __init__(self, system_controller, button_style: str = "", line_edit_style: str = "", theme: str = "default"):

        super().__init__()
        self.system = system_controller
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
        if not hasattr(self.system, "get_deleted_titles"):
            self.lst.addItem("db_manager.get_deleted_titles not implemented")
            return

        titles = self.system.get_deleted_titles(batch_size=300, offset=0) or []
        if not titles:
            self.lst.addItem("(empty) no deleted titles")
            return

        for t in titles:
            # поддержка dict и объектов
            title_id = getattr(t, "title_id", None) if not isinstance(t, dict) else t.get("title_id")
            name_ru = getattr(t, "name_ru", "") if not isinstance(t, dict) else t.get("name_ru", "")
            deleted_at = getattr(t, "deleted_at", None) if not isinstance(t, dict) else t.get("deleted_at")
            self.lst.addItem(f"{title_id} | {name_ru} | deleted_at={deleted_at}")

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if not hasattr(self.system, "restore_titles"):
            QMessageBox.warning(self, "Restore", "db_manager.restore_titles не реализован.")
            return

        self.system.restore_titles(ids)
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

        if not hasattr(self.system, "purge_titles"):
            QMessageBox.warning(self, "Purge", "db_manager.purge_titles не реализован.")
            return

        result = self.system.purge_titles(self.input_ids.text().strip())
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
                color: #111;
            }}
            QLabel {{
                color: #111;
            }}
            QLineEdit {{
                color: #111;
                background: rgba(255,255,255,0.95);
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                padding: 4px 6px;
            }}
            QListWidget {{
                background: rgba(255,255,255,0.95);
                color: #111;
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                font-size: 12px;
            }}
            QListWidget::item {{
                color: #111;
                padding: 2px 4px;
            }}
            QListWidget::item:selected {{
                background: rgba(0, 120, 215, 0.25);
            }}
        """)
