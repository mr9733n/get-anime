# ui_manager.py
import pathlib

from PyQt5.QtCore import QEventLoop, Qt
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QGridLayout, QWidget, QScrollArea, QHBoxLayout, QComboBox, \
    QLabel, QLineEdit, QPushButton, QDialog, QVBoxLayout, QApplication, QToolButton, QMenu, QAction


class UIManager:
    def __init__(self, parent):
        self.parent = parent
        self.loading_dialog = LoadingDialog(self.parent)
        self.parent_widgets = {}
        qss_path = pathlib.Path(__file__).with_name('styles.qss')
        if not qss_path.is_file():
            raise FileNotFoundError(f"Не найден файл стилей: {qss_path}")

        # Содержимое файла как одна строка
        self.qss_raw = qss_path.read_text(encoding='utf-8')
        self.button_style_template = """
            QPushButton {{
                background-color: {background_color};
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                border: 1px solid #888;
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
                border: 1px solid #555;
            }}
        """
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
        self.tool_button_style_template = """
            QToolButton {{
                background-color: {background_color};
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }}
            QToolButton:hover {{
                background-color: {hover_color};
                border: 1px solid #888;
            }}
            QToolButton:pressed {{
                background-color: {pressed_color};
                border: 1px solid #555;
            }}
        """
        self.menu_style_template = """
            QMenu#customMenu {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                padding: 4px;
                border-radius: 6px;
            }}
            QMenu#customMenu::item {{
                padding: 6px 12px;
                color: {text_color};
                background-color: transparent;   /* обычное состояние */
            }}
            QMenu#customMenu::item:selected {{
                background-color: {selected_bg};
                color: {selected_text};
            }}
        """
        self.line_edit_style_template = """
            QLineEdit {
                background-color: #f7f7f7;
                border: 1px solid #dcdcdc;
                border-radius: 6px;
                padding: 6px;
                font-size: 14px;
                color: #333;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
                background-color: #ffffff;
            }
        """
        self.combo_style_template = """
            QComboBox {
                background-color: #f7f7f7;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 6px;
                font-size: 14px;
                color: #333;
            }
            QComboBox:drop-down { border-left: 1px solid #ccc; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #aaa;
                selection-background-color: #0078d4;
                selection-color: #fff;
            }
        """

    def create_widgets_from_metadata(self, metadata_list, layout, callbacks):
        for metadata in metadata_list:
            widget_type = metadata.get("type")

            if widget_type == "button":
                self._create_button(metadata, layout, callbacks)
            elif widget_type == "input_field":
                self._create_input_field(metadata, layout)
            elif widget_type == "dropdown":
                self._create_dropdown(metadata, layout, callbacks)
            elif widget_type == "split_button":
                self._create_split_button(metadata, layout, callbacks)

    def _button_style(self, color_index: int) -> str:
        """Возвращает готовый stylesheet для любой кнопки."""
        bg, hover, pressed = self.button_colors[color_index]
        return self.button_style_template.format(
            background_color=bg,
            hover_color=hover,
            pressed_color=pressed,
        )

    def _tool_button_style(self, color_index: int) -> str:
        """Стиль для QToolButton – такой же, как у QPushButton."""
        bg, hover, pressed = self.button_colors[color_index]
        return self.tool_button_style_template.format(
            background_color=bg,
            hover_color=hover,
            pressed_color=pressed,
        )

    def _make_button(
            self,
            cls,  # QPushButton или QToolButton
            text: str,
            color_index: int,
            callback_key: str | None,
            callbacks: dict,
            layout,
    ):
        # ---------- 1️⃣ Создание виджета ----------
        if cls is QToolButton:  # QToolButton не принимает text
            btn = cls(self.parent)  # только родитель
            btn.setText(text)  # задаём подпись отдельно
        else:  # QPushButton (и потенциально другие, принимающие text)
            btn = cls(text, self.parent)

        # ---------- 2️⃣ Общий стиль ----------
        btn.setStyleSheet(self._button_style(color_index))

        # ---------- 3️⃣ Привязка колбека ----------
        if callback_key and callback_key in callbacks:
            btn.clicked.connect(callbacks[callback_key])

        # ---------- 4️⃣ Добавление в layout ----------
        layout.addWidget(btn)
        self.apply_shadow_effects([btn])
        return btn

    def _make_menu_button(
            self,
            text: str,
            color_index: int,
            menu_items: list[dict],
            callbacks: dict,
            layout,
    ):
        # ---------- 1️⃣ QToolButton ----------
        btn = QToolButton(self.parent)  # создаём без текста‑конструктора
        btn.setText(text)  # задаём подпись
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)  # только текст
        btn.setAutoRaise(False)  # отключаем «плоский» вид

        # применяем стиль, идентичный QPushButton
        btn.setStyleSheet(self._tool_button_style(color_index))

        # ---------- 2️⃣ Меню ----------
        menu = QMenu(btn)
        menu.setObjectName("customMenu")
        menu.setAttribute(Qt.WA_StyledBackground, True)

        # добавляем пункты
        for item in menu_items:
            label = item.get("text", "Item")
            cb_key = item.get("callback_key")
            act = QAction(label, btn)
            if cb_key and cb_key in callbacks:
                act.triggered.connect(callbacks[cb_key])
            menu.addAction(act)

        # стиль меню (оставляем ваш шаблон)
        menu.setStyleSheet(self._menu_style(color_index))

        # привязываем меню к кнопке
        btn.setMenu(menu)

        # ---------- 3️⃣ Popup‑mode (после стиля) ----------
        btn.setPopupMode(QToolButton.MenuButtonPopup)

        # ---------- 4️⃣ Действие по умолчанию ----------
        if menu_items:
            first_key = menu_items[0].get("callback_key")
            if first_key and first_key in callbacks:
                btn.clicked.connect(callbacks[first_key])

        # ---------- 5️⃣ Добавляем в layout и тень ----------
        layout.addWidget(btn)
        self.apply_shadow_effects([btn])
        return btn

    def _make_line_edit(self, placeholder, min_w, max_w, widget_key, layout):
        le = QLineEdit(self.parent)
        le.setPlaceholderText(placeholder)
        le.setMinimumWidth(min_w)
        le.setMaximumWidth(max_w)
        le.setStyleSheet(self._line_edit_style())
        self.parent_widgets[widget_key] = le
        layout.addWidget(le)
        self.apply_shadow_effects([le])
        return le

    def _line_edit_style(self) -> str:
        return self.line_edit_style_template

    def _make_combo_box(self, items, callback_key, callbacks, widget_key, layout):
        cb = QComboBox(self.parent)
        cb.addItems(items)
        cb.setStyleSheet(self._combo_style())
        if callback_key and callback_key in callbacks:
            cb.currentIndexChanged.connect(callbacks[callback_key])
        self.parent_widgets[widget_key] = cb
        layout.addWidget(cb)
        self.apply_shadow_effects([cb])
        return cb

    def _menu_style(self, color_index: int) -> str:
        bg, hover, pressed = self.button_colors[color_index]  # берём те же цвета, что и для кнопки
        return self.menu_style_template.format(
            bg_color=bg,
            border_color=hover,
            text_color="#fff",
            selected_bg=hover,
            selected_text="#fff",
        )

    def _combo_style(self) -> str:
        return self.combo_style_template

    def _create_button(self, metadata, layout, callbacks):
        self._make_button(
            QPushButton,
            metadata.get("text", "Button"),
            metadata.get("color_index", 0),
            metadata.get("callback_key"),
            callbacks,
            layout,
        )

    def _create_split_button(self, metadata, layout, callbacks):
        self._make_menu_button(
            text=metadata.get("text", "Button"),
            color_index=metadata.get("color_index", 0),
            menu_items=metadata.get("menu_items", []),
            callbacks=callbacks,
            layout=layout,
        )

    def _create_input_field(self, metadata, layout):
        self._make_line_edit(
            placeholder=metadata.get("placeholder", ""),
            min_w=metadata.get("min_width", 100),
            max_w=metadata.get("max_width", 200),
            widget_key=metadata.get("widget_key", "input_field"),
            layout=layout,
        )

    def _create_dropdown(self, metadata, layout, callbacks):
        self._make_combo_box(
            items=metadata.get("items", []),
            callback_key=metadata.get("callback_key"),
            callbacks=callbacks,
            widget_key=metadata.get("widget_key", "dropdown"),
            layout=layout,
        )

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

        # Добавляем верхний лейаут (с кнопками поиска, выбора качества, кнопками дней недели)
        main_layout.addLayout(top_layout)

        # Основной лейаут для отображения контента (скролл-область)
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

        # Добавляем скролл-область (основной контент)
        main_layout.addWidget(self.parent.scroll_area)

        # Добавляем лейаут пагинации под скролл-областью
        pagination_widget = QWidget()
        pagination_widget_layout = QHBoxLayout(pagination_widget)
        pagination_widget_layout.setAlignment(Qt.AlignCenter)

        # Создаем кнопки для пагинации с уникальными колбеками
        prev_page_button = QPushButton("←", self.parent)
        prev_page_button.setFixedWidth(50)
        pagination_info = QLabel("0 .. 0", self.parent)
        pagination_info.setAlignment(Qt.AlignCenter)
        next_page_button = QPushButton("→", self.parent)
        next_page_button.setFixedWidth(50)

        # Добавляем стиль кнопкам
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