import json
import html
import re

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
    def __init__(self, system_controller, button_style: str = "", line_edit_style: str = "", theme: str = "default"):
        super().__init__()
        self.system = system_controller

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

        if not hasattr(self.system, "get_deleted_titles_log"):
            self.list_widget.addItem("db_manager.get_deleted_titles_log not implemented")
            return

        limit_str = (self.limit_input.text() or "").strip()
        limit = 300
        if limit_str.isdigit():
            limit = max(1, min(2000, int(limit_str)))

        rows = self.system.get_deleted_titles_log(limit=limit, offset=0)

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

        if not hasattr(self.system, "get_deleted_titles_log_item"):
            self.snapshot_view.setText("db_manager.get_deleted_titles_log_item not implemented")
            return

        row = self.system.get_deleted_titles_log_item(log_id)
        if row is None:
            self.snapshot_view.setText("Log item not found")
            return

        raw = getattr(row, "snapshot_json", "") or ""
        try:
            obj = json.loads(raw)
            self._set_snapshot_html(obj)
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
            /* JSON highlight */
            .json-wrap {{
                padding: 6px;
            }}
            pre.jpre {{
                margin: 0;
                white-space: pre-wrap;      /* перенос длинных строк */
                word-break: break-word;
                font-family: Consolas, monospace;
                font-size: 12px;
                line-height: 1.35;
            }}
            .jk {{ font-weight: 700; }}       /* key */
            .js {{ }}                          /* string */
            .jn {{ font-weight: 700; }}       /* number */
            .jb {{ font-weight: 700; }}       /* bool/null */
            .jp {{ opacity: 0.65; }}          /* punctuation */

            /* Слегка различим цвета (без зависимости от темы можно оставить так) */
            .jk {{ color: #0b5394; }}         /* keys */
            .js {{ color: #38761d; }}         /* strings */
            .jn {{ color: #7f6000; }}         /* numbers */
            .jb {{ color: #741b47; }}         /* bool/null */

        """)

    def _json_to_highlighted_html(self, obj) -> str:
        """
        Возвращает HTML с подсветкой JSON.
        Работает через pretty-json + регулярки.
        """
        pretty = json.dumps(obj, ensure_ascii=False, indent=2)
        safe = html.escape(pretty)

        # Подсветка:
        # 1) ключи: "key":
        safe = re.sub(
            r'(&quot;.*?&quot;)(\s*):',
            r'<span class="jk">\1</span><span class="jp">\2</span>:',
            safe
        )

        # 2) строки (значения): "text"
        # (после ключей всё равно останутся строки-значения — подсветим их отдельно)
        safe = re.sub(
            r'(?<!class=&quot;jk&quot;)(?<!jk&quot;)(?<!jk\&quot;)(?<!jk)(?<!jk&gt;)'  # лёгкая защита от двойной подсветки
            r'(&quot;[^&quot;]*&quot;)',
            r'<span class="js">\1</span>',
            safe
        )

        # 3) числа
        safe = re.sub(r'(?<![\w])(-?\d+(?:\.\d+)?)(?![\w])', r'<span class="jn">\1</span>', safe)

        # 4) true/false/null
        safe = re.sub(r'(?<![\w])(true|false|null)(?![\w])', r'<span class="jb">\1</span>', safe)

        return f"<pre class='jpre'>{safe}</pre>"

    def _set_snapshot_html(self, obj) -> None:
        html_doc = (
            "<div class='json-wrap'>"
            + self._json_to_highlighted_html(obj)
            + "</div>"
        )
        self.snapshot_view.setHtml(html_doc)
