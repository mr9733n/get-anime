# utils.py
import hashlib
import json
import logging
import os

from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from core.types import POSTER_SIZES, POSTER_FIELDS
from core.tables import Poster, Template

class PlaceholderManager:
    def __init__(self, engine):
        self.logger = logging.getLogger(__name__)
        self.Session = sessionmaker(bind=engine)()

    @staticmethod
    def calc_hash(data: bytes) -> str:
        return hashlib.md5(data).hexdigest()

    def save_placeholders(self):
        placeholders = [
            {"title_id": 1, "file_name": "background.png", "size_key": "original"},
            {"title_id": 2, "file_name": "no_image.png", "size_key": "original"},
            {"title_id": 2, "file_name": "no_image_medium.png", "size_key": "medium"},
            {"title_id": 2, "file_name": "no_image_small.png", "size_key": "small"},
        ]

        with self.Session as session:
            for ph in placeholders:
                try:
                    title_id = ph["title_id"]
                    size_key: PosterSize = ph["size_key"]
                    fields = POSTER_FIELDS[size_key]

                    poster = session.query(Poster).filter_by(title_id=title_id).first()
                    if not poster:
                        poster = Poster(title_id=title_id)
                        session.add(poster)
                        session.flush()

                    with open(f'static/{ph["file_name"]}', "rb") as f:
                        blob = f.read()
                    hash_value = self.calc_hash(blob)
                    now = datetime.now(timezone.utc)

                    setattr(poster, fields.blob, blob)
                    setattr(poster, fields.hash, hash_value)
                    setattr(poster, fields.updated, now)

                    session.commit()
                    self.logger.info(f"Placeholder {ph['file_name']} saved for title_id={title_id} size={size_key}")

                except Exception as e:
                    session.rollback()
                    self.logger.error(f"Error initializing placeholder {ph}: {e}")

class TemplateManager:
    def __init__(self, engine):
        self.logger = logging.getLogger(__name__)
        self.Session = sessionmaker(bind=engine)()

    def save_template(self, template_name):
        """
        Saves templates, overwriting existing ones if files have changed.
        :type template_name: str
        :return:
        """
        template_files = {
            'one_title_html': 'one_title.html',
            'titles_html': 'titles.html',
            'text_list_html': 'text_list.html',
            'styles_css': 'styles.css'
        }

        with self.Session as session:
            try:
                # Проверяем, существует ли шаблон
                existing_template = session.query(Template).filter_by(name=template_name).first()

                # Чтение файлов шаблона
                one_title_html_content = self.read_static_file(template_name, template_files["one_title_html"])
                titles_html_content = self.read_static_file(template_name, template_files["titles_html"])
                text_list_html_content = self.read_static_file(template_name, template_files["text_list_html"])
                styles_content = self.read_static_file(template_name, template_files["styles_css"])

                if existing_template:
                    # Проверяем, изменилось ли содержимое файлов
                    if (existing_template.one_title_html != one_title_html_content or
                            existing_template.titles_html != titles_html_content or
                            existing_template.text_list_html != text_list_html_content or
                            existing_template.styles_css != styles_content):
                        # Обновляем существующий шаблон
                        existing_template.one_title_html = one_title_html_content
                        existing_template.titles_html = titles_html_content
                        existing_template.text_list_html = text_list_html_content
                        existing_template.styles_css = styles_content
                        session.commit()
                        self.logger.info(f"Template '{template_name}' updated successfully.")
                    else:
                        self.logger.info(f"Template '{template_name}' is already up-to-date.")
                else:
                    # Сохранение нового шаблона в базе данных
                    save_template = Template(
                        name=template_name,
                        one_title_html=one_title_html_content,
                        titles_html=titles_html_content,
                        text_list_html=text_list_html_content,
                        styles_css=styles_content
                    )
                    session.add(save_template)
                    session.commit()
                    self.logger.info(f"Template '{template_name}' saved successfully.")
            except Exception as e:
                session.rollback()
                self.logger.error(f"Error saving template: {e}")

    def read_static_file(self, template_name, file_name):
        """
        Used by save_template
        :param template_name:
        :param file_name:
        :return:
        """
        try:
            template_path = os.path.join('templates', template_name)
            with open(f'{template_path}/{file_name}', 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            self.logger.warning(f"Static file '{file_name}' not found.")
            return ""
        except Exception as e:
            self.logger.error(f"Error reading file '{file_name}': {e}")
            return ""

class StateManager:
    def __init__(self, engine):
        self.logger = logging.getLogger(__name__)
        self.Session = sessionmaker(bind=engine)()

    def save_app_state(self, state_items):
        """Сохраняет состояние приложения в БД"""
        with self.Session as session:
            try:
                session.execute(text("DELETE FROM app_state"))  # Очищаем перед записью
                for key, value in state_items:
                    # Если строка уже сериализована (обнаружены лишние кавычки), удаляем их
                    if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
                        stored_value = value.strip('"')  # Убираем кавычки
                    elif isinstance(value, str):
                        stored_value = value  # Обычная строка, сохраняем как есть
                    else:
                        stored_value = json.dumps(value, ensure_ascii=False)  # JSON

                    session.execute(
                        text("INSERT INTO app_state (key, value, created_at) VALUES (:key, :value, :created_at)"),
                        {"key": key, "value": stored_value, "created_at": datetime.now(timezone.utc)},
                    )
                session.commit()
                self.logger.info("Состояние приложения сохранено в БД")
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении состояния: {e}")

    def load_app_state(self):
        """Загружает состояние из базы данных"""
        with self.Session as session:
            try:
                result = session.execute(text("SELECT key, value, created_at FROM app_state")).fetchall()
                state = {}

                for row in result:
                    key, value, _ = row
                    try:
                        # Если строка содержит лишние кавычки, убираем их
                        if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
                            value = value.strip('"')

                        # Если значение — JSON, загружаем его, иначе оставляем строкой
                        if value.startswith("{") or value.startswith("["):
                            state[key] = json.loads(value)
                        else:
                            state[key] = value
                    except json.JSONDecodeError:
                        self.logger.error(f"Ошибка JSON при загрузке ключа {key}: {value}")
                        state[key] = value

                if result:
                    last_saved_at = result[0][2]  # Берём дату из первой записи
                    self.logger.info(f"Состояние загружено. Последнее сохранение: {last_saved_at}")

                return state
            except Exception as e:
                self.logger.error(f"Ошибка при загрузке состояния: {e}")
                return {}

    def clear_app_state(self):
        """Очищает сохраненное состояние в БД"""
        with self.Session as session:
            try:
                session.execute(text("DELETE FROM app_state"))
                session.commit()
                self.logger.info("Сохраненный state в БД сброшен")
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сбросе состояния: {e}")