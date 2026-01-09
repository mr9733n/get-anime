from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

from PyQt6.QtWidgets import QLabel, QSystemTrayIcon, QStyle
from PyQt6.QtCore import QTimer, Qt

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

Level = Literal["info", "success", "warning", "error"]

@dataclass
class NotifyStyle:
    bg_rgba: str
    tray_icon: QStyle.StandardPixmap
    tray_level: QSystemTrayIcon.MessageIcon

STYLES: dict[Level, NotifyStyle] = {
    "info":    NotifyStyle("rgba(60, 120, 255, 0.92)", QStyle.StandardPixmap.SP_MessageBoxInformation, QSystemTrayIcon.MessageIcon.Information),
    "success": NotifyStyle("rgba(0, 170, 90, 0.92)",   QStyle.StandardPixmap.SP_DialogApplyButton,     QSystemTrayIcon.MessageIcon.Information),
    "warning": NotifyStyle("rgba(255, 165, 0, 0.92)",  QStyle.StandardPixmap.SP_MessageBoxWarning,     QSystemTrayIcon.MessageIcon.Warning),
    "error":   NotifyStyle("rgba(255, 0, 0, 0.92)",    QStyle.StandardPixmap.SP_MessageBoxCritical,    QSystemTrayIcon.MessageIcon.Critical),
}

class Notifier:
    """Уведомления поверх UI + system tray. Не зависит от DisplayController."""
    def __init__(self, parent: QWidget):
        self._parent = parent
        self._label: QLabel | None = None
        self._tray = QSystemTrayIcon(self._parent)
        self._tray.show()

    def notify(self, level: Level, title: str, message: str, *, timeout_ms: int = 5000) -> None:
        style = STYLES[level]
        if self._label is not None:
            self._label.hide()
            self._label.deleteLater()
            self._label = None

        # label
        self._label = QLabel(message, self._parent)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(f"""
            QLabel {{
                background-color: {style.bg_rgba};
                color: white;
                font-size: 14px;
                padding: 6px;
                border-radius: 4px;
            }}
        """)
        self._label.setAlignment(Qt.AlignmentFlag.AlignJustify)
        self._label.setGeometry(50, 50, 500, 50)
        self._label.show()
        QTimer.singleShot(timeout_ms, self._label.hide)

        # tray
        self._tray = QSystemTrayIcon(self._parent)
        self._tray.setIcon(self._parent.style().standardIcon(style.tray_icon))
        self._tray.show()
        self._tray.showMessage(title, message, style.tray_level, timeout_ms)
        QTimer.singleShot(timeout_ms, self._tray.hide)

    # sugar
    def info(self, title: str, message: str) -> None: self.notify("info", title, message)
    def success(self, title: str, message: str) -> None: self.notify("success", title, message)
    def warning(self, title: str, message: str) -> None: self.notify("warning", title, message)
    def error(self, title: str, message: str) -> None: self.notify("error", title, message)
