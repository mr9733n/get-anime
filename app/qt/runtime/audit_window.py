import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QTextBrowser,
    QLineEdit, QLabel, QMessageBox
)

class AuditLogWindow(QWidget):
    """
    Окно аудита удалений: показывает строки из deleted_titles_log
    и позволяет посмотреть snapshot_json.
    """
    def __init__(self, db_manager, button_style: str = "", line_edit_style: str = "", theme: str = "default"):
        super().__init__()
        self.db_manager = db_manager

        self.button_style = button_style
        self.line_edit_style = line_edit_style

        self.setWindowTitle("Deleted titles audit log")
        self.setGeometry(100, 300, 950, 650)

        root = QVBoxLayout(self)

        root.addWidget(QLabel("Deleted titles log (newest first):"))

        self.list_widget = QListWidget(self)
        root.addWidget(self.list_widget)

        ctrl = QHBoxLayout()
        self.limit_input = QLineEdit(self)
        self.limit_input.setPlaceholderText("limit (default 300)")
        if self.line_edit_style:
            self.limit_input.setStyleSheet(self.line_edit_style)

        self.refresh_btn = QPushButton("REFRESH", self)
        self.view_btn = QPushButton("SNAPSHOT", self)

        if self.button_style:
            self.refresh_btn.setStyleSheet(self.button_style)
            self.view_btn.setStyleSheet(self.button_style)

        ctrl.addWidget(self.limit_input)
        ctrl.addWidget(self.refresh_btn)
        ctrl.addWidget(self.view_btn)
        root.addLayout(ctrl)

        root.addWidget(QLabel("Snapshot JSON:"))
        self.snapshot_view = QTextBrowser(self)
        root.addWidget(self.snapshot_view)

        self.refresh_btn.clicked.connect(self.refresh)
        self.view_btn.clicked.connect(self.view_selected_snapshot)
        self.list_widget.itemSelectionChanged.connect(self.view_selected_snapshot)

        self.refresh()
        self._apply_theme(theme)

    def refresh(self):
        self.list_widget.clear()
        self.snapshot_view.clear()

        if not hasattr(self.db_manager, "get_deleted_titles_log"):
            self.list_widget.addItem("db_manager.get_deleted_titles_log not implemented")
            return

        limit_str = (self.limit_input.text() or "").strip()
        limit = 300
        if limit_str.isdigit():
            limit = max(1, min(2000, int(limit_str)))

        rows = self.db_manager.get_deleted_titles_log(limit=limit, offset=0)

        for r in rows:
            if isinstance(r, dict):
                log_id = r.get("id")
                title_id = r.get("title_id")
                name = r.get("title_name_ru") or ""
                date = r.get("deleted_at")
                counts = r.get("counts_json") or "{}"
            else:
                log_id = getattr(r, "id", None)
                title_id = getattr(r, "title_id", None)
                name = getattr(r, "title_name_ru", None) or ""
                date = getattr(r, "deleted_at", None)
                counts = getattr(r, "counts_json", None) or "{}"

            self.list_widget.addItem(
                f"id={log_id} | title_id={title_id} | {name} | deleted_at={date} | counts={counts}"
            )

    def _selected_log_id(self):
        item = self.list_widget.currentItem()
        if not item:
            return None
        text = item.text()
        # вытаскиваем id=123
        try:
            prefix = text.split("|", 1)[0].strip()
            if prefix.startswith("id="):
                return int(prefix.replace("id=", "").strip())
        except Exception:
            return None
        return None

    def view_selected_snapshot(self):
        log_id = self._selected_log_id()
        if not log_id:
            return

        if not hasattr(self.db_manager, "get_deleted_titles_log_item"):
            self.snapshot_view.setText("db_manager.get_deleted_titles_log_item not implemented")
            return

        row = self.db_manager.get_deleted_titles_log_item(log_id)
        if row is None:
            self.snapshot_view.setText("Log item not found")
            return

        raw = getattr(row, "snapshot_json", "") or ""
        try:
            obj = json.loads(raw)
            pretty = json.dumps(obj, ensure_ascii=False, indent=2)
            self.snapshot_view.setText(pretty)
        except Exception:
            # если вдруг snapshot не JSON (не должен), покажем как есть
            self.snapshot_view.setText(raw)

    def _apply_theme(self, theme: str):
        bg = {
            "default": "rgba(240, 240, 240, 1.0)",
            "no_background_night": "rgba(140, 140, 140, 1.0)",
            "no_background": "rgba(220, 220, 220, 1.0)",
        }.get(theme, "rgba(240, 240, 240, 1.0)")

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg};
                color: #111;               /* <-- базовый цвет текста */
            }}
            QLabel {{
                color: #111;
            }}
            QListWidget {{
                background: rgba(255,255,255,0.95);
                color: #111;               /* <-- текст списка */
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                font-size: 12px;
            }}
            QListWidget::item {{
                color: #111;               /* <-- текст item */
                padding: 2px 4px;
            }}
            QListWidget::item:selected {{
                background: rgba(0, 120, 215, 0.25);
            }}
            QTextBrowser {{
                background: rgba(255,255,255,0.95);
                color: #111;               /* <-- текст JSON */
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                font-family: Consolas, monospace;
                font-size: 12px;
            }}
        """)
