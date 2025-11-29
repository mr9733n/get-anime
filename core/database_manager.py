import logging
import os

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from core.save import SaveManager
from core.process import ProcessManager
from core.get import GetManager
from core.utils import PlaceholderManager, TemplateManager, StateManager
from core.tables import Base, DaysOfWeek, History
from app.qt.app_state_manager import AppStateManager

class DatabaseManager:
    def __init__(self, db_path):
        self.current_poster_index = None
        self.logger = logging.getLogger(__name__)
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)()

        self.app_state_manager = AppStateManager(self)
        # Инициализация менеджеров
        self.template_manager = TemplateManager(self.engine)
        self.placeholder_manager = PlaceholderManager(self.engine)
        self.save_manager = SaveManager(self.engine)
        self.process_manager = ProcessManager(self.save_manager)
        self.get_manager = GetManager(self.engine)
        self.state_manager = StateManager(self.engine)

    def initialize_tables(self):
        # Создаем таблицы, если они еще не существуют
        Base.metadata.create_all(self.engine)
        days = [
            {"day_of_week": 1, "day_name": "Monday"},
            {"day_of_week": 2, "day_name": "Tuesday"},
            {"day_of_week": 3, "day_name": "Wednesday"},
            {"day_of_week": 4, "day_name": "Thursday"},
            {"day_of_week": 5, "day_name": "Friday"},
            {"day_of_week": 6, "day_name": "Saturday"},
            {"day_of_week": 7, "day_name": "Sunday"},
        ]
        with self.Session as session:
                try:
                    if session.query(DaysOfWeek).count() == 0:
                        for day in days:
                            session.add(DaysOfWeek(day_of_week=day["day_of_week"], day_name=day["day_name"]))
                        session.commit()
                    # Add initial record to the history table if it doesn't exist
                    if session.query(History).count() == 0:
                        initial_history = History(user_id=42, title_id=1, is_watched=False, is_download=False)
                        session.add(initial_history)
                        session.commit()

                    session.close()
                except Exception as e:
                    session.rollback()
                    self.logger.error(f"Error initializing '{days}' image in posters table: {e}")

    def initialize_templates(self):
        """Автоматически загружает все папки из 'templates/' как шаблоны в БД, если их там ещё нет."""
        templates_dir = "templates"
        if not os.path.exists(templates_dir):
            self.logger.warning("Папка с шаблонами не найдена. Пропускаем загрузку шаблонов.")
            return

        available_templates = self.get_manager.get_available_templates()
        template_folders = [d for d in os.listdir(templates_dir) if os.path.isdir(os.path.join(templates_dir, d))]

        for template_name in template_folders:
            if template_name not in available_templates:
                self.logger.info(f"Добавление нового шаблона в БД: {template_name}")
                self.save_template(template_name)

    def save_placeholders(self):
        # Добавляем заглушки изображений, если они не добавлены
        return self.placeholder_manager.save_placeholders()

    def save_template(self, template_name):
        """
        Saves templates, overwriting existing ones if files have changed.
        :type template_name: str
        :return:
        """
        return self.template_manager.save_template(template_name)

    def remove_schedule_day(self, title_ids, day_of_week):
        return self.save_manager.remove_schedule_day(title_ids, day_of_week)

    def save_studio_to_db(self, title_id, studio_name):
        return self.save_manager.save_studio_to_db(title_id, studio_name)

    def save_title(self, title_data):
        return self.save_manager.save_title(title_data)

    def save_franchise(self, franchise_data):
        return self.save_manager.save_franchise(franchise_data)

    def save_genre(self, title_id, genres):
        return self.save_manager.save_genre(title_id, genres)

    def save_team_members(self, title_id, team_data):
        return self.save_manager.save_team_members(title_id, team_data)

    def save_episode(self, episode_data):
        return self.save_manager.save_episode(episode_data)

    def save_schedule(self, day_of_week, title_id, last_updated=None):
        return self.save_manager.save_schedule(day_of_week, title_id, last_updated)

    def save_torrent(self, torrent_data):
        return self.save_manager.save_torrent(torrent_data)

    def process_franchises(self, title_data):
        return self.process_manager.process_franchises(title_data)

    def process_titles(self, title_data):
        return self.process_manager.process_titles(title_data)

    def process_episodes(self, title_data):
        return self.process_manager.process_episodes(title_data)

    def process_torrents(self, title_data):
        return self.process_manager.process_torrents(title_data)

    def save_poster(self, title_id, poster_blob, hash_value):
        return self.save_manager.save_poster(title_id, poster_blob, hash_value)

    def save_need_to_see(self, user_id, title_id, need_to_see=True):
        return self.save_manager.save_need_to_see(user_id, title_id, need_to_see)

    def save_watch_all_episodes(self, user_id, title_id, is_watched=False, episode_ids=None):
        return self.save_manager.save_watch_all_episodes(user_id, title_id, is_watched, episode_ids)

    def save_watch_status(self, user_id, title_id, episode_id=None, is_watched=False, torrent_id=None, is_download=False):
        return self.save_manager.save_watch_status(user_id,title_id, episode_id, is_watched, torrent_id, is_download)

    def save_ratings(self, title_id: int, rating_name: str, rating_value: int, external_value: float):
        """
        "Comprehensive Media Evaluation Rating System" or CMERS
        The CMERS system would operate as follows:
            - Title Appearance Frequency
            - Watched Episode Count
            - Individual Title Prominence
            - User-Provided Ratings
            - External Source Ratings
        """
        return self.save_manager.save_ratings(title_id, rating_name, rating_value, external_value)

    def get_titles_for_day(self, day_of_week):
        """Загружает тайтлы для указанного дня недели из базы данных."""
        return self.get_manager.get_titles_for_day(day_of_week)

    def get_history_status(self, user_id, title_id, episode_id=None, torrent_id=None):
        return self.get_manager.get_history_status(user_id, title_id, episode_id, torrent_id)

    def get_need_to_see(self, user_id, title_id):
        return self.get_manager.get_need_to_see(user_id, title_id)

    def get_all_episodes_watched_status(self, user_id, title_id):
        return self.get_manager.get_all_episodes_watched_status(user_id, title_id)

    def get_rating_from_db(self, title_id):
        return self.get_manager.get_rating_from_db(title_id)

    def get_statistics_from_db(self):
        return self.get_manager.get_statistics_from_db()

    def get_franchises_from_db(self, batch_size=None, offset=0, title_id=None):
        return self.get_manager.get_franchises_from_db(batch_size, offset, title_id)

    def get_need_to_see_from_db(self, batch_size=None, offset=0, title_id=None):
        """Need to see Titles without episodes"""
        return self.get_manager.get_need_to_see_from_db(batch_size, offset, title_id)

    def get_poster_link(self, title_id):
        return self.get_manager.get_poster_link(title_id)

    def get_poster_last_updated(self, title_id):
        return self.get_manager.get_poster_last_updated(title_id)

    def get_poster_blob(self, title_id):
        """
        Retrieves the poster blob for a given title_id.
        If check_exists_only is True, returns a boolean indicating whether the poster exists.
        """
        return self.get_manager.get_poster_blob(title_id)

    def get_torrents_from_db(self, title_id):
        return self.get_manager.get_torrents_from_db(title_id)

    def get_genres_from_db(self, title_id):
        return self.get_manager.get_genres_from_db(title_id)

    def get_team_from_db(self, title_id):
        return self.get_manager.get_team_from_db(title_id)

    def get_titles_by_keywords(self, search_string):
        """Searches for titles by keywords in code, name_ru, name_en, alternative_name, or by title_id, and returns a list of title_ids."""
        return self.get_manager.get_titles_by_keywords(search_string)

    def get_template(self, name=None):
        """
        Загружает темплейт из базы данных по имени.
        """
        return self.get_manager.get_template(name)

    def get_available_templates(self):
        """
        Возвращает список доступных шаблонов из базы данных.
        """
        return self.get_manager.get_available_templates()

    def get_titles_from_db(self, show_all=False, day_of_week=None, batch_size=None, title_id=None, title_ids=None, offset=0):
        """Получает список тайтлов из базы данных через DatabaseManager."""
        """
        Returns a SQLAlchemy query for fetching titles based on given conditions.
        :param day_of_week: Specific day of the week to filter by.
        :param show_all: If true, returns all titles.
        :param title_id: If specified, returns a title with the given title_id.
        :return: SQLAlchemy Query object
        """
        return self.get_manager.get_titles_from_db(show_all, day_of_week, batch_size, title_id, title_ids, offset)

    def get_titles_list_from_db(self, title_ids=None, batch_size=None, offset=0):
        """Titles without episodes"""
        return self.get_manager.get_titles_list_from_db(title_ids, batch_size, offset)

    def get_titles_by_genre(self, genre_name):
        """Titles by genre"""
        return self.get_manager.get_titles_by_genre(genre_name)

    def get_titles_by_team_member(self, team_member):
        """Titles by genre"""
        return self.get_manager.get_titles_by_team_member(team_member)

    def get_titles_by_year(self, year):
        """Titles by year"""
        return self.get_manager.get_titles_by_year(year)

    def get_titles_by_status(self, status_code):
        """Titles by status"""
        return self.get_manager.get_titles_by_status(status_code)

    def get_ongoing_titles(self, batch_size=None, offset=0):
        """Titles by status ongoing"""
        return self.get_manager.get_ongoing_titles(batch_size, offset)

    def get_total_titles_count(self, show_mode=None):
        """Titles count"""
        return self.get_manager.get_total_titles_count(show_mode)