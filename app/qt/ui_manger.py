# ui_manager.py
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QGridLayout, QWidget, QScrollArea, QHBoxLayout, QComboBox, \
    QLabel, QLineEdit, QPushButton


class UIManager:
    def __init__(self, parent):
        self.parent = parent
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
            ("#4a4a4a", "#5c5c5c", "#3b3b3b"),  # Dark gray for "FIND"
            ("#6e6e6e", "#7f7f7f", "#595959"),  # Light gray for "MON"
            ("#7a7a7a", "#8a8a8a", "#626262"),  # Medium gray for "TUE"
            ("#9a9a9a", "#ababab", "#7b7b7b"),  # Gray for "WED"
            ("#555555", "#666666", "#3e3e3e"),  # Dark for "THU"
            ("#8c8c8c", "#9e9e9e", "#767676"),  # Lighter for "FRI"
            ("#7e7e7e", "#8f8f8f", "#6a6a6a"),  # Saturated for "SAT"
            ("#6b6b6b", "#7c7c7c", "#525252"),  # Medium for "SUN"
            ("#5a5a5a", "#6c6c6c", "#474747")   # Dark for others
        ]

    def create_button(self, text, color_index, callback):
        button = QPushButton(text, self.parent)
        button_style = self.button_style_template.format(
            background_color=self.button_colors[color_index][0],
            hover_color=self.button_colors[color_index][1],
            pressed_color=self.button_colors[color_index][2]
        )
        button.setStyleSheet(button_style)
        button.clicked.connect(callback)
        return button

    def setup_controls_layout(self, layout):
        # Search Field
        self.parent.title_search_entry = QLineEdit(self.parent)
        self.parent.title_search_entry.setPlaceholderText('TITLE ID OR NAME')
        self.parent.title_search_entry.setMinimumWidth(180)
        self.parent.title_search_entry.setMaximumWidth(255)
        self.parent.title_search_entry.setStyleSheet("""
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
        layout.addWidget(self.parent.title_search_entry)

        # Find Button
        self.parent.display_button = self.create_button('FIND', 0, self.parent.get_search_by_title)
        layout.addWidget(self.parent.display_button)

        # Random Button
        self.parent.random_button = self.create_button('RANDOM', 5, self.parent.get_random_title)
        layout.addWidget(self.parent.random_button)

        # Day Buttons
        self.parent.day_buttons = []
        for i, day in enumerate(self.parent.days_of_week):
            button = self.create_button(day, i + 1, lambda checked, i=i: self.parent.display_titles_for_day(i))
            layout.addWidget(button)
            self.parent.day_buttons.append(button)

        # Refresh Button
        self.parent.refresh_button = self.create_button('RELOAD', 6, self.parent.reload_schedule)
        layout.addWidget(self.parent.refresh_button)

        # Quality Dropdown
        self.parent.quality_dropdown = QComboBox(self.parent)
        self.parent.quality_dropdown.addItems(['fhd', 'hd', 'sd'])
        self.parent.quality_dropdown.setStyleSheet("""
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
        layout.addWidget(self.parent.quality_dropdown)
        self.parent.quality_dropdown.currentIndexChanged.connect(self.parent.refresh_display)

    def setup_main_layout(self, main_layout):
        # Adding control layout
        controls_layout = QHBoxLayout()
        self.setup_controls_layout(controls_layout)
        main_layout.addLayout(controls_layout)

        # Adding scroll area for posters
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
        main_layout.addWidget(self.parent.scroll_area)

        # Создаем горизонтальный макет для кнопок
        button_layout = QHBoxLayout()

        # Load More Button
        self.parent.load_more_button = self.create_button('LOAD PREV', 0, self.parent.load_previous_titles)
        button_layout.addWidget(self.parent.load_more_button)
        # Load More Button
        self.parent.load_more_button = self.create_button('LOAD MORE', 0, self.parent.load_more_titles)
        button_layout.addWidget(self.parent.load_more_button)

        # Добавление кнопки для отображения всех тайтлов
        self.parent.display_titles_button = self.create_button('TITLES LIST', 0,
                                                               self.parent.display_titles_text_list)
        button_layout.addWidget(self.parent.display_titles_button)

        # Добавление кнопки для отображения всех тайтлов
        self.parent.display_titles_button = self.create_button('FRANCHISES', 0,
                                                               self.parent.display_franchises)
        button_layout.addWidget(self.parent.display_titles_button)

        # Добавление кнопки для отображения всех тайтлов
        self.parent.display_titles_button = self.create_button('SYSTEM', 0,
                                                               self.parent.display_system)
        button_layout.addWidget(self.parent.display_titles_button)

        # Save Playlist Button
        self.parent.save_playlist_button = self.create_button('SAVE', 7, self.parent.save_playlist_wrapper)
        button_layout.addWidget(self.parent.save_playlist_button)

        # Play Playlist Button
        self.parent.play_playlist_button = self.create_button('PLAY', 4, self.parent.play_playlist_wrapper)
        button_layout.addWidget(self.parent.play_playlist_button)


        # Добавляем горизонтальный макет в основной макет
        main_layout.addLayout(button_layout)

        # Apply shadow effects to buttons
        self.apply_shadow_effects([
            self.parent.display_button,
            self.parent.random_button,
            self.parent.load_more_button,
            self.parent.save_playlist_button,
            self.parent.play_playlist_button,
            self.parent.refresh_button,
            self.parent.quality_dropdown
        ])

    def apply_shadow_effects(self, widgets):
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(8)
        shadow_effect.setOffset(2, 2)
        for widget in widgets:
            widget.setGraphicsEffect(shadow_effect)
