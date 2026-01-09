# app/qt/system_windows/settings_window.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QCheckBox, QSpinBox, QPushButton,
    QGroupBox, QFormLayout, QMessageBox
)

import logging
from typing import Callable


class SettingsWindow(QWidget):
    """Окно настроек приложения."""

    BUTTON_STYLE = """
        QPushButton {
            color: #fff;
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            background: rgba(74, 74, 74, 1.0);
        }
        QPushButton:hover { background-color: #5c5c5c; }
        QPushButton:pressed { background-color: #000; }
        QPushButton:disabled { background-color: #999; }
    """

    def __init__(
            self,
            config_manager,
            config_file: str,
            system_controller=None,
            theme: str = "default",
            on_close: Callable[[], None] | None = None,
            on_settings_changed: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.config_file = config_file
        self.system = system_controller

        # Callbacks вместо сигналов
        self._on_close = on_close
        self._on_settings_changed = on_settings_changed

        self.setWindowTitle("Settings")
        self.setGeometry(100, 300, 500, 400)
        self.setMinimumSize(450, 350)

        self._init_ui()
        self._load_current_settings()
        self._apply_theme(theme)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_network_tab(), "Network")
        self.tabs.addTab(self._create_player_tab(), "Player")
        self.tabs.addTab(self._create_ui_tab(), "UI")
        self.tabs.addTab(self._create_actions_tab(), "Actions")

        layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet(self.BUTTON_STYLE)
        self.save_btn.clicked.connect(self._save_settings)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(self.BUTTON_STYLE)
        self.cancel_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _create_network_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Proxy Settings")
        form = QFormLayout(group)

        self.proxy_enabled = QCheckBox()
        form.addRow("Proxy Enabled:", self.proxy_enabled)

        self.proxy_url = QLineEdit()
        self.proxy_url.setPlaceholderText("http://127.0.0.1:8080")
        form.addRow("Proxy URL:", self.proxy_url)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _create_player_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # VLC Group
        vlc_group = QGroupBox("VLC Player")
        vlc_form = QFormLayout(vlc_group)

        self.use_libvlc = QCheckBox()
        vlc_form.addRow("Use LibVLC:", self.use_libvlc)

        self.vlc_log_enabled = QCheckBox()
        vlc_form.addRow("Logging:", self.vlc_log_enabled)

        self.vlc_verbose = QSpinBox()
        self.vlc_verbose.setRange(0, 3)
        vlc_form.addRow("Verbose Level:", self.vlc_verbose)

        layout.addWidget(vlc_group)

        # MPV Group
        mpv_group = QGroupBox("MPV Player")
        mpv_form = QFormLayout(mpv_group)

        self.use_mpv = QCheckBox()
        mpv_form.addRow("Use MPV:", self.use_mpv)

        self.mpv_log_enabled = QCheckBox()
        mpv_form.addRow("Logging:", self.mpv_log_enabled)

        layout.addWidget(mpv_group)
        layout.addStretch()
        return widget

    def _create_ui_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Display Settings")
        form = QFormLayout(group)

        self.titles_batch_size = QSpinBox()
        self.titles_batch_size.setRange(4, 24)
        form.addRow("Titles per page:", self.titles_batch_size)

        self.titles_list_batch_size = QSpinBox()
        self.titles_list_batch_size.setRange(10, 100)
        form.addRow("List batch size:", self.titles_list_batch_size)

        self.current_offset = QSpinBox()
        self.current_offset.setRange(0, 10000)
        form.addRow("Current offset:", self.current_offset)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _create_actions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Database Actions
        db_group = QGroupBox("Database")
        db_layout = QVBoxLayout(db_group)

        self.optimize_btn = QPushButton("Optimize Database (VACUUM)")
        self.optimize_btn.setStyleSheet(self.BUTTON_STYLE)
        self.optimize_btn.clicked.connect(self._optimize_db)
        db_layout.addWidget(self.optimize_btn)

        self.db_status_label = QLabel("")
        db_layout.addWidget(self.db_status_label)

        layout.addWidget(db_group)

        # State Actions
        state_group = QGroupBox("Application State")
        state_layout = QVBoxLayout(state_group)

        self.clear_state_btn = QPushButton("Clear Saved State")
        self.clear_state_btn.setStyleSheet(self.BUTTON_STYLE)
        self.clear_state_btn.clicked.connect(self._clear_state)
        state_layout.addWidget(self.clear_state_btn)

        layout.addWidget(state_group)
        layout.addStretch()
        return widget

    def _load_current_settings(self):
        """Загружает текущие настройки в UI."""
        cfg = self.config_manager

        # Network
        self.proxy_enabled.setChecked(cfg.network.proxy_enabled)
        self.proxy_url.setText(cfg.network.proxy_url or "")

        # Player
        self.use_libvlc.setChecked(
            str(cfg.get_setting('Settings', 'use_libvlc', 'false')).lower() == 'true'
        )
        self.vlc_log_enabled.setChecked(
            str(cfg.get_setting('VlcPlayer', 'log_enabled', 'false')).lower() == 'true'
        )
        self.vlc_verbose.setValue(
            int(cfg.get_setting('VlcPlayer', 'verbose_level', '2') or 2)
        )
        self.use_mpv.setChecked(
            str(cfg.get_setting('Settings', 'use_mpv_player', 'false')).lower() == 'true'
        )
        self.mpv_log_enabled.setChecked(
            str(cfg.get_setting('MpvPlayer', 'log_enabled', 'false')).lower() == 'true'
        )

        # UI
        self.titles_batch_size.setValue(
            int(cfg.get_setting('Settings', 'titles_batch_size', '12') or 12)
        )
        self.titles_list_batch_size.setValue(
            int(cfg.get_setting('Settings', 'titles_list_batch_size', '50') or 50)
        )
        self.current_offset.setValue(
            int(cfg.get_setting('Settings', 'current_offset', '0') or 0)
        )

    def _save_settings(self):
        """Сохраняет настройки в файл."""
        cfg = self.config_manager

        # Network
        cfg.set_setting('Network', 'proxy_enabled', str(self.proxy_enabled.isChecked()).lower())
        cfg.set_setting('Network', 'proxy_url', self.proxy_url.text())

        # Player
        cfg.set_setting('Settings', 'use_libvlc', str(self.use_libvlc.isChecked()).lower())
        cfg.set_setting('VlcPlayer', 'log_enabled', str(self.vlc_log_enabled.isChecked()).lower())
        cfg.set_setting('VlcPlayer', 'verbose_level', str(self.vlc_verbose.value()))
        cfg.set_setting('Settings', 'use_mpv_player', str(self.use_mpv.isChecked()).lower())
        cfg.set_setting('MpvPlayer', 'log_enabled', str(self.mpv_log_enabled.isChecked()).lower())

        # UI
        cfg.set_setting('Settings', 'titles_batch_size', str(self.titles_batch_size.value()))
        cfg.set_setting('Settings', 'titles_list_batch_size', str(self.titles_list_batch_size.value()))
        cfg.set_setting('Settings', 'current_offset', str(self.current_offset.value()))

        cfg.save_config(self.config_file)

        QMessageBox.information(self, "Settings", "Settings saved. Restart app to apply changes.")

        # Callback вместо сигнала
        if self._on_settings_changed:
            self._on_settings_changed()

        self.close()

    def _optimize_db(self):
        """Оптимизирует базу данных."""
        if not self.system:
            self.db_status_label.setText("DB manager not available")
            return

        self.optimize_btn.setEnabled(False)
        self.db_status_label.setText("Optimizing...")

        try:
            result = self.system.optimize_db()

            if result["status"] == "ok":
                before_mb = result["size_before"] / (1024 * 1024)
                after_mb = result["size_after"] / (1024 * 1024)
                saved_kb = (result["size_before"] - result["size_after"]) / 1024
                self.db_status_label.setText(
                    f"Done! {before_mb:.2f}MB → {after_mb:.2f}MB (saved {saved_kb:.1f}KB)"
                )
            else:
                self.db_status_label.setText(f"Error: {result.get('error', 'unknown')}")
        except Exception as e:
            self.db_status_label.setText(f"Error: {e}")
        finally:
            self.optimize_btn.setEnabled(True)

    def _clear_state(self):
        """Очищает сохранённое состояние."""
        if not self.system:
            return

        reply = QMessageBox.question(
            self, "Clear State",
            "Clear all saved application state?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.system.state_manager.clear_app_state()
                QMessageBox.information(self, "State", "State cleared successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to clear state: {e}")

    def _apply_theme(self, theme: str):
        """Применяет тему."""
        # базовые фоны
        styles = {
            "default": ("rgba(240, 240, 240, 1.0)", "#000"),
            "no_background_night": ("rgba(40, 40, 40, 1.0)", "#eee"),
            "no_background": ("rgba(220, 220, 220, 1.0)", "#000"),
        }

        bg, fg = styles.get(theme, styles["default"])

        # ВАЖНО: задаём индикатор чекбокса явно
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg};
                color: {fg};
            }}

            QGroupBox {{
                border: 1px solid rgba(120, 120, 120, 0.8);
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }}

            QLineEdit, QSpinBox {{
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(120, 120, 120, 0.8);
                border-radius: 6px;
                padding: 4px 6px;
            }}

            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid rgba(160, 160, 160, 0.9);
                border-radius: 4px;
                background: rgba(0, 0, 0, 0.15);
            }}
            QCheckBox::indicator:checked {{
                background: rgba(90, 170, 255, 0.9);
                border: 1px solid rgba(90, 170, 255, 1.0);
            }}
            QCheckBox::indicator:checked:hover {{
                background: rgba(110, 190, 255, 0.95);
            }}
        """)

    def closeEvent(self, event):
        # Callback вместо сигнала
        if self._on_close:
            self._on_close()
        event.accept()