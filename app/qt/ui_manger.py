# ui_manager.py
import pathlib

from PyQt5.QtCore import QEventLoop, Qt
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QGridLayout, QWidget, QScrollArea, QHBoxLayout, QComboBox, \
    QLabel, QLineEdit, QPushButton, QDialog, QVBoxLayout, QApplication, QToolButton, QMenu, QAction


class UIManager:
    def __init__(self, parent, qss_raw_styles=None):
        self.parent = parent
        self.loading_dialog = LoadingDialog(self.parent)
        self.parent_widgets = {}
        self.qss_raw = qss_raw_styles
        def block(name: str) -> str:
            """Возвращает часть QSS между {name} и следующим маркером {…}."""
            start = self.qss_raw.find(f'{{{name}}}')
            if start == -1:
                raise ValueError(f'Блок {name} не найден в styles.qss')
            start += len(f'{{{name}}}')
            next_marker = self.qss_raw.find('\n{', start)
            if next_marker == -1:
                end = len(self.qss_raw)
            else:
                end = next_marker

            return self.qss_raw[start:end].strip()
        # Uses in _make_style
        self.button_style_template      = block('button')
        self.tool_button_style_template = block('tool_button')
        self.menu_style_template        = block('menu')
        self.line_edit_style_template   = block('line_edit')
        self.combo_style_template       = block('combo')
        self.button_colors = [
            ("#4a4a4a", "#5c5c5c", "#000"),  # Dark gray : 0
            ("#6e6e6e", "#7f7f7f", "#000"),  # Light gray : 1
            ("#7a7a7a", "#8a8a8a", "#000"),  # Medium gray : 2
            ("#9a9a9a", "#ababab", "#000"),  # Gray : 3
            ("#555555", "#666666", "#000"),  # Dark : 4
            ("#8c8c8c", "#9e9e9e", "#000"),  # Lighter : 5
            ("#7e7e7e", "#8f8f8f", "#000"),  # Saturated : 6
            ("#6b6b6b", "#7c7c7c", "#000"),  # Medium : 7
            ("#5a5a5a", "#6c6c6c", "#000")   # Dark for others : 8
        ]

    def create_widgets_from_metadata(self, metadata_list, layout, callbacks):
        for md in metadata_list:
            t = md.get('type')
            if t == 'button':
                self._make_button(
                    QPushButton,
                    md.get('text', 'Button'),
                    md.get('color_index', 0),
                    md.get('callback_key'),
                    callbacks,
                    layout,
                )
            elif t == 'split_button':
                self._make_menu_button(
                    md.get('text', 'Button'),
                    md.get('color_index', 0),
                    md.get('callback_key'),
                    md.get('menu_items', []),
                    callbacks,
                    layout,
                )
            elif t == 'input_field':
                self._make_line_edit(
                    md.get('placeholder', ''),
                    md.get('min_width', 100),
                    md.get('max_width', 200),
                    md.get('widget_key', 'input_field'),
                    layout,
                )
            elif t == 'dropdown':
                self._make_combo_box(
                    md.get('items', []),
                    md.get('callback_key'),
                    callbacks,
                    md.get('widget_key', 'dropdown'),
                    layout,
                )

    def _make_style(self, template_name: str, color_index: int) -> str:
        bg, hover, pressed = self.button_colors[color_index]
        subs = {
            "bg": bg,
            "hover": hover,
            "pressed": pressed,
            "border": hover,
            "text": "#fff",
            "selected_bg": hover,
            "selected_text": "#fff",
        }
        tmpl = getattr(self, f"{template_name}_style_template", "")
        if not tmpl:
            return f"{template_name} {{ background-color: {bg}; color: {subs['text']}; }}"
        return tmpl.format(**subs)

    def _make_button(
            self,
            cls,
            text: str,
            color_index: int,
            callback_key: str | None,
            callbacks: dict,
            layout,
    ):
        btn = cls(text, self.parent) if cls is not QPushButton else cls(text, self.parent)
        btn.setStyleSheet(self._make_style('button', color_index))

        if callback_key and callback_key in callbacks:
            btn.clicked.connect(callbacks[callback_key])

        layout.addWidget(btn)
        self.apply_shadow_effects([btn])
        return btn

    def _make_menu_button(
            self,
            text: str,
            color_index: int,
            callback_key: str | None,
            menu_items: list[dict],
            callbacks: dict,
            layout,
    ):
        btn = QToolButton(self.parent)
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setAutoRaise(False)
        btn.setStyleSheet(self._make_style('tool_button', color_index))

        menu = QMenu(btn)
        menu.setObjectName("customMenu")
        menu.setStyleSheet(self._make_style('menu', color_index))

        for item in menu_items:
            act = QAction(item.get("text", "Item"), btn)
            cb_key = item.get("callback_key")
            if cb_key and cb_key in callbacks:
                act.triggered.connect(callbacks[cb_key])
            menu.addAction(act)

        btn.setMenu(menu)
        btn.setPopupMode(QToolButton.MenuButtonPopup)

        def sync_width():
            menu.setFixedWidth(btn.width())

        btn.showEvent = lambda e: (sync_width(), QToolButton.showEvent(btn, e))

        if callback_key and callback_key in callbacks:
            btn.clicked.connect(callbacks[callback_key])

        layout.addWidget(btn)
        self.apply_shadow_effects([btn])
        return btn

    def _make_line_edit(self, placeholder, min_w, max_w, widget_key, layout):
        le = QLineEdit(self.parent)
        le.setPlaceholderText(placeholder)
        le.setMinimumWidth(min_w)
        le.setMaximumWidth(max_w)
        le.setStyleSheet(self._make_style('line_edit', 0))   # 0 — любой индекс, цвета не нужны
        self.parent_widgets[widget_key] = le
        layout.addWidget(le)
        self.apply_shadow_effects([le])
        return le

    def _make_combo_box(self, items, callback_key, callbacks, widget_key, layout):
        cb = QComboBox(self.parent)
        cb.addItems(items)
        cb.setStyleSheet(self._make_style('combo', 0))
        if callback_key and callback_key in callbacks:
            cb.currentIndexChanged.connect(callbacks[callback_key])
        self.parent_widgets[widget_key] = cb
        layout.addWidget(cb)
        self.apply_shadow_effects([cb])
        return cb

    def setup_main_layout(self, main_layout, all_layout_metadata, callbacks):
        # Создаем два лейаута: верхний и нижний
        top_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        # Разделение метаданных и создание виджетов в соответствующих лейаутах
        for metadata in all_layout_metadata:
            if metadata["layout"] == "top":
                self.create_widgets_from_metadata([metadata], top_layout, callbacks)
            elif metadata["layout"] == "bottom":
                self.create_widgets_from_metadata([metadata], bottom_layout, callbacks)

        main_layout.addLayout(top_layout)

        self.parent.scroll_area = QScrollArea()
        self.parent.scroll_area.setWidgetResizable(True)
        self.parent.poster_container = QWidget()
        self.parent.posters_layout = QGridLayout()
        self.parent.poster_container.setLayout(self.parent.posters_layout)

        if self.parent.current_template == "default":
            self.parent.poster_container.setStyleSheet("""
                QWidget {
                    background-image: url('static/background.png');
                    background-position: center;
                    background-attachment: fixed;
                    background-color: rgba(240, 240, 240, 0.5);
                }
            """)
        elif self.parent.current_template == "no_background_night":
            self.parent.poster_container.setStyleSheet("""
                QWidget {
                    background-color: rgba(140, 140, 140, 0.5);
                }
            """)
        elif self.parent.current_template == "no_background":
            self.parent.poster_container.setStyleSheet("""
                    QWidget {
                        background-color: rgba(240, 240, 240, 1.0);
                    }
                """)

        self.parent.scroll_area.setWidget(self.parent.poster_container)

        main_layout.addWidget(self.parent.scroll_area)

        pagination_widget = QWidget()
        pagination_widget_layout = QHBoxLayout(pagination_widget)
        pagination_widget_layout.setAlignment(Qt.AlignCenter)

        prev_page_button = QPushButton("←", self.parent)
        prev_page_button.setFixedWidth(50)
        pagination_info = QLabel("0 .. 0", self.parent)
        pagination_info.setAlignment(Qt.AlignCenter)
        next_page_button = QPushButton("→", self.parent)
        next_page_button.setFixedWidth(50)

        button_style = """
            QPushButton {
                background-color: #4a4a4a;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5c5c5c;
            }
            QPushButton:pressed {
                background-color: #000;
            }
            QPushButton:disabled {
                background-color: #aaa;
                color: #ddd;
            }
        """
        prev_page_button.setStyleSheet(button_style)
        next_page_button.setStyleSheet(button_style)

        # Сохраняем ссылки на виджеты в словаре
        self.parent_widgets["pagination_prev"] = prev_page_button
        self.parent_widgets["pagination_info"] = pagination_info
        self.parent_widgets["pagination_next"] = next_page_button

        # Подключаем новые обработчики для пагинации фильтрованных результатов
        prev_page_button.clicked.connect(lambda: self.parent.navigate_pagination(go_forward=False))
        next_page_button.clicked.connect(lambda: self.parent.navigate_pagination(go_forward=True))

        # Добавляем виджеты в layout пагинации
        pagination_widget_layout.addWidget(prev_page_button)
        pagination_widget_layout.addWidget(pagination_info)
        pagination_widget_layout.addWidget(next_page_button)

        # Скрываем пагинацию по умолчанию
        pagination_widget.setVisible(False)

        # Добавляем нижний лейаут (дополнительные кнопки управления)
        main_layout.addLayout(bottom_layout)

        # Добавляем в основной layout
        main_layout.addWidget(pagination_widget)
        self.parent_widgets["pagination_widget"] = pagination_widget
        self.parent_widgets["pagination_layout"] = pagination_widget_layout


    @staticmethod
    def apply_shadow_effects(widgets):
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(8)
        shadow_effect.setOffset(2, 2)
        for widget in widgets:
            widget.setGraphicsEffect(shadow_effect)

    def show_loader(self, message="Loading..."):
        """Показывает анимированный лоадер"""
        self.loading_dialog.label.setText(message)
        self.loading_dialog.start()

    def hide_loader(self):
        """Скрывает лоадер"""
        self.loading_dialog.stop()

    def set_buttons_enabled(self, enabled):
        """Включает или выключает все кнопки в UI"""
        for widget in self.parent.findChildren(QPushButton):
            widget.setEnabled(enabled)

    def update_pagination_info(self, current_page, total_pages, total_items, show_mode):
        """Обновляет информацию о пагинации в UI."""
        try:
            # Обновляем информационный текст
            pagination_info = self.parent_widgets.get("pagination_info")
            if pagination_info:
                info_text = f"{show_mode} | Pages: {current_page} .. {total_pages} | Titles: {total_items}"
                pagination_info.setText(info_text)

            # Включаем/отключаем кнопки в зависимости от текущей страницы
            prev_button = self.parent_widgets.get("pagination_prev")
            next_button = self.parent_widgets.get("pagination_next")

            if prev_button:
                prev_button.setEnabled(current_page > 1)

            if next_button:
                next_button.setEnabled(current_page < total_pages)

            # Показываем/скрываем виджет пагинации
            pagination_widget = self.parent_widgets.get("pagination_widget")
            if pagination_widget:
                pagination_widget.setVisible(total_pages > 1)

        except Exception as e:
            self.parent.logger.error(f"Error updating pagination info: {e}")

class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load...")
        self.setModal(True)
        self.setFixedSize(160, 40)

        layout = QVBoxLayout()
        self.label = QLabel("Loading...", self)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def start(self):
        """Запускает лоадер"""
        self.show()
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)  # Обновляем UI

    def stop(self):
        """Останавливает лоадер"""
        self.hide()