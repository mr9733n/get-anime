# ui_manager.py
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QGridLayout, QWidget, QScrollArea, QHBoxLayout, QComboBox, \
    QLabel, QLineEdit, QPushButton

class UIManager:
    def __init__(self, parent):

        self.parent = parent
        self.parent_widgets = {}
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

    def create_widgets_from_metadata(self, metadata_list, layout, callbacks):
        for metadata in metadata_list:
            widget_type = metadata.get("type")

            if widget_type == "button":
                self._create_button(metadata, layout, callbacks)
            elif widget_type == "input_field":
                self._create_input_field(metadata, layout)
            elif widget_type == "dropdown":
                self._create_dropdown(metadata, layout, callbacks)

    def _create_button(self, metadata, layout, callbacks):
        text = metadata.get("text", "Button")
        color_index = metadata.get("color_index", 0)
        callback_key = metadata.get("callback_key", None)

        button = QPushButton(text, self.parent)
        button_style = self.button_style_template.format(
            background_color=self.button_colors[color_index][0],
            hover_color=self.button_colors[color_index][1],
            pressed_color=self.button_colors[color_index][2]
        )
        button.setStyleSheet(button_style)

        if callback_key and callback_key in callbacks:
            button.clicked.connect(callbacks[callback_key])

        layout.addWidget(button)
        self.apply_shadow_effects([button])

    def _create_input_field(self, metadata, layout):
        placeholder = metadata.get("placeholder", "")
        min_width = metadata.get("min_width", 100)
        max_width = metadata.get("max_width", 200)

        input_field = QLineEdit(self.parent)
        input_field.setPlaceholderText(placeholder)
        input_field.setMinimumWidth(min_width)
        input_field.setMaximumWidth(max_width)

        input_field.setStyleSheet("""
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
        """)

        # Сохраняем ссылку на input в словарь с уникальным ключом
        widget_key = metadata.get("widget_key", "input_field")
        self.parent_widgets[widget_key] = input_field
        layout.addWidget(input_field)
        self.apply_shadow_effects([input_field])

    def _create_dropdown(self, metadata, layout, callbacks):
        items = metadata.get("items", [])
        callback_name = metadata.get("callback_key", None)

        dropdown = QComboBox(self.parent)
        dropdown.addItems(items)
        dropdown.setStyleSheet("""
            QComboBox {
                background-color: #f7f7f7;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 6px;
                font-size: 14px;
                color: #333;
            }
            QComboBox:drop-down {
                border-left: 1px solid #ccc;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #aaa;
                selection-background-color: #0078d4;
                selection-color: #fff;
            }
        """)

        if callback_name and callback_name in callbacks:
            callback = callbacks[callback_name]
            dropdown.currentIndexChanged.connect(callback)

        # Сохраняем ссылку на dropdown в словарь с уникальным ключом
        widget_key = metadata.get("widget_key", "dropdown")
        self.parent_widgets[widget_key] = dropdown
        layout.addWidget(dropdown)
        self.apply_shadow_effects([dropdown])

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
        self.parent.poster_container.setStyleSheet("""
            QWidget {
                background-image: url('static/background.png');
                background-position: center;
                background-attachment: fixed;
                background-color: rgba(240, 240, 240, 0.5);
            }
        """)
        self.parent.scroll_area.setWidget(self.parent.poster_container)

        # Добавляем скролл-область (основной контент)
        main_layout.addWidget(self.parent.scroll_area)

        # Добавляем нижний лейаут (дополнительные кнопки управления)
        main_layout.addLayout(bottom_layout)

    @staticmethod
    def apply_shadow_effects(widgets):
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(8)
        shadow_effect.setOffset(2, 2)
        for widget in widgets:
            widget.setGraphicsEffect(shadow_effect)