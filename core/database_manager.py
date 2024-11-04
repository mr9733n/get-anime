import json
import logging

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, LargeBinary, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, session, relationship, validates, joinedload
from datetime import datetime, timezone
from sqlalchemy.ext.declarative import declarative_base


# Создаем базовый класс для всех моделей
Base = declarative_base()

# Настраиваем соединение с базой данных
engine = create_engine('sqlite:///anime_player.db', echo=True)
SessionLocal = sessionmaker(bind=engine)

class DatabaseManager:
    def __init__(self):
        self.current_poster_index = None
        self.logger = logging.getLogger(__name__)
        self.session = SessionLocal()

    def initialize_tables(self):
        # Создаем таблицы, если они еще не существуют
        Base.metadata.create_all(engine)

        # Добавляем заглушку изображения, если оно не добавлено
        session = SessionLocal()
        try:
            placeholder_poster = session.query(Poster).filter_by(title_id=-1).first()
            if not placeholder_poster:
                with open('static/no_image.png', 'rb') as image_file:
                    poster_blob = image_file.read()
                    placeholder_poster = Poster(
                        title_id=-1,  # Используем отрицательный идентификатор для заглушки
                        poster_blob=poster_blob,
                        last_updated=datetime.utcnow()
                    )
                    session.add(placeholder_poster)
                    session.commit()
                    self.logger.info("Placeholder image 'no_image.png' was added to posters table.")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error initializing placeholder image in posters table: {e}")
        finally:
            session.close()

    def save_title(self, title_data):
        try:
            self.logger.debug(f"Saving title data: {title_data}")

            # Проверка на наличие и корректность данных
            if not isinstance(title_data, dict):
                raise ValueError("Переданные данные для сохранения тайтла должны быть словарем")

            # Проверка типов ключевых полей
            if not isinstance(title_data.get('title_id'), int):
                raise ValueError("Неверный тип для 'title_id'. Ожидался тип int.")

            # Преобразование списков и словарей в строки в формате JSON для хранения в базе данных
            title_data['franchises'] = json.dumps(title_data.get('franchises', []))
            title_data['genres'] = json.dumps(title_data.get('genres', []))
            title_data['team_voice'] = json.dumps(title_data.get('team_voice', []))
            title_data['team_translator'] = json.dumps(title_data.get('team_translator', []))
            title_data['team_timing'] = json.dumps(title_data.get('team_timing', []))
            title_data['blocked_geoip_list'] = json.dumps(title_data.get('blocked_geoip_list', []))

            existing_title = self.session.query(Title).filter_by(title_id=title_data['title_id']).first()

            if existing_title:
                # Проверка на изменение данных и обновление
                is_updated = False
                for key, value in title_data.items():
                    if getattr(existing_title, key, None) != value:
                        setattr(existing_title, key, value)
                        is_updated = True

                if is_updated:
                    self.session.commit()  # Коммит только если есть изменения
            else:
                # Добавление нового тайтла, если он не существует
                new_title = Title(**title_data)
                self.session.add(new_title)
                self.session.commit()
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка при сохранении тайтла в базе данных: {e}")

    def save_episode(self, episode_data):
        try:
            self.logger.debug(f"Saving episode data: {episode_data}")

            if not isinstance(episode_data, dict):
                self.logger.error(f"Invalid episode data: {episode_data}")
                return

            # Создаем копию данных
            processed_data = episode_data.copy()

            # Преобразуем timestamps если они есть в данных
            if 'created_timestamp' in processed_data:
                processed_data['created_timestamp'] = datetime.utcfromtimestamp(processed_data['created_timestamp'])

            existing_episode = self.session.query(Episode).filter_by(
                uuid=processed_data['uuid'],
                title_id=processed_data['title_id']
            ).first()

            self.logger.debug(f"Existing episode: {existing_episode}")

            if existing_episode:
                is_updated = False
                protected_fields = {'episode_id', 'title_id', 'created_timestamp'}

                for key, value in processed_data.items():
                    if (
                            key not in protected_fields
                            and hasattr(existing_episode, key)
                            and getattr(existing_episode, key) != value
                    ):
                        setattr(existing_episode, key, value)
                        is_updated = True

                if is_updated:
                    existing_episode.last_updated = datetime.utcnow()
                    self.session.commit()
            else:
                # Для нового эпизода используем текущее время для timestamp'ов если они не предоставлены
                if 'created_timestamp' not in processed_data:
                    processed_data['created_timestamp'] = datetime.utcnow()

                new_episode = Episode(**processed_data)
                self.session.add(new_episode)
                self.session.commit()

        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка при сохранении эпизода в базе данных: {e}")

    def save_schedule(self, day_of_week, title_id):
        try:
            schedule_entry = Schedule(day_of_week=day_of_week, title_id=title_id)
            self.session.add(schedule_entry)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка при сохранении расписания: {e}")
        finally:
            self.session.close()

    def get_titles_for_day(self, day_of_week):
        """Загружает тайтлы для указанного дня недели из базы данных."""
        try:
            return self.session.query(Title).join(Schedule).filter(Schedule.day_of_week == day_of_week).all()
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка при получении тайтлов для дня недели: {e}")
        finally:
            self.session.close()

    def get_titles_query(self, day_of_week=None, show_all=False, title_id=None):
        """
        Returns a SQLAlchemy query for fetching titles based on given conditions.
        :param day_of_week: Specific day of the week to filter by.
        :param show_all: If true, returns all titles.
        :param title_id: If specified, returns a title with the given title_id.
        :return: SQLAlchemy Query object
        """
        query = self.session.query(Title).options(joinedload(Title.episodes))
        if title_id:
            query = query.filter(Title.title_id == title_id)
        elif not show_all:
            query = query.join(Schedule).filter(Schedule.day_of_week == day_of_week)

        return query

    def save_torrent(self, torrent_data):
        try:
            # Проверяем, существует ли уже торрент с данным `torrent_id`
            existing_torrent = self.session.query(Torrent).filter_by(torrent_id=torrent_data['torrent_id']).first()

            if existing_torrent:
                # Проверка на изменение данных
                is_updated = any(
                    getattr(existing_torrent, key) != value
                    for key, value in torrent_data.items()
                )

                if is_updated:
                    # Обновляем данные, если они изменились
                    self.session.merge(Torrent(**torrent_data))
            else:
                # Добавляем новый торрент, если его еще нет в базе
                self.session.add(Torrent(**torrent_data))

            self.session.commit()
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка при сохранении торрента в базе данных: {e}")
        finally:
            self.session.close()

    def save_poster_blob(self, title_id, poster_blob):
        try:
            # Проверяем, есть ли уже постер для данного тайтла, добавляем новый, если нет
            new_poster = Poster(
                title_id=title_id,
                poster_blob=poster_blob,
                last_updated=datetime.utcnow()
            )
            self.session.add(new_poster)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            self.logger.error(f"Ошибка при сохранении блоба постера в базе данных: {e}")

    def get_poster_blob(self, title_id):
        try:
            poster = self.session.query(Poster).filter_by(title_id=title_id).first()
            if poster:
                return poster.poster_blob
            return None
        except Exception as e:
            self.logger.error(f"Error fetching poster from database: {e}")
            return None

# Модели для таблиц
class Title(Base):
    __tablename__ = 'titles'
    title_id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)
    name_ru = Column(String, nullable=False)
    name_en = Column(String)
    alternative_name = Column(String)
    franchises = Column(String)  # Сохраняется как строка в формате JSON
    announce = Column(String)
    status_string = Column(String)
    status_code = Column(Integer)
    poster_path_small = Column(String)
    poster_path_medium = Column(String)
    poster_path_original = Column(String)
    updated = Column(Integer)
    last_change = Column(Integer)
    type_full_string = Column(String)
    type_code = Column(Integer)
    type_string = Column(String)
    type_episodes = Column(Integer)
    type_length = Column(String)
    genres = Column(String)  # Сохраняется как строка в формате JSON
    team_voice = Column(String)  # Сохраняется как строка в формате JSON
    team_translator = Column(String)  # Сохраняется как строка в формате JSON
    team_timing = Column(String)  # Сохраняется как строка в формате JSON
    season_string = Column(String)
    season_code = Column(Integer)
    season_year = Column(Integer)
    season_week_day = Column(Integer)
    description = Column(String)
    in_favorites = Column(Integer)
    blocked_copyrights = Column(Boolean)
    blocked_geoip = Column(Boolean)
    blocked_geoip_list = Column(String)  # Сохраняется как строка в формате JSON
    last_updated = Column(DateTime, default=datetime.utcnow)

    episodes = relationship("Episode", back_populates="title")
    torrents = relationship("Torrent", back_populates="title")
    posters = relationship("Poster", back_populates="title")
    schedules = relationship("Schedule", back_populates="title")

class Episode(Base):
    __tablename__ = 'episodes'
    episode_id = Column(Integer, primary_key=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'))
    episode_number = Column(Integer, nullable=False)
    name = Column(String)
    uuid = Column(String, unique=True)
    created_timestamp = Column(DateTime, default=datetime.utcnow)
    # last_updated = Column(DateTime, default=datetime.utcnow)
    hls_fhd = Column(String)
    hls_hd = Column(String)
    hls_sd = Column(String)
    preview_path = Column(String)
    skips_opening = Column(String)
    skips_ending = Column(String)

    title = relationship("Title", back_populates="episodes")

    @validates('created_timestamp', 'last_updated')
    def validate_timestamp(self, key, value):
        if isinstance(value, (int, float)):
            return datetime.utcfromtimestamp(value)
        return value

class WatchHistory(Base):
    __tablename__ = 'watch_history'
    id = Column(Integer, primary_key=True, autoincrement=True)  # Добавлен Primary Key для уникальности
    user_id = Column(Integer, nullable=False)  # Предполагается, что `user_id` будет использоваться для идентификации пользователя
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    episode_number = Column(Integer)
    is_watched = Column(Boolean, default=False)
    last_watched_at = Column(DateTime, default=datetime.utcnow)

class Torrent(Base):
    __tablename__ = 'torrents'
    torrent_id = Column(Integer, primary_key=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'))
    episodes_range = Column(String)
    quality = Column(String)
    quality_type = Column(String)
    resolution = Column(String)
    encoder = Column(String)
    leechers = Column(Integer)
    seeders = Column(Integer)
    downloads = Column(Integer)
    total_size = Column(Integer)
    size_string = Column(String)
    url = Column(String)
    magnet_link = Column(String)
    uploaded_timestamp = Column(Integer)
    hash = Column(String)
    torrent_metadata = Column(Text, nullable=True)  # Переименовано с `metadata` на `torrent_metadata`
    raw_base64_file = Column(Text, nullable=True)

    title = relationship("Title", back_populates="torrents")

class Poster(Base):
    __tablename__ = 'posters'
    poster_id = Column(Integer, primary_key=True, autoincrement=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    poster_blob = Column(LargeBinary, nullable=False)  # Поле для хранения бинарных данных изображения
    last_updated = Column(DateTime, default=datetime.utcnow)

    title = relationship("Title", back_populates="posters")

class Schedule(Base):
    __tablename__ = 'schedule'
    id = Column(Integer, primary_key=True, autoincrement=True)  # Primary Key уже есть
    day_of_week = Column(Integer, nullable=False)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)

    title = relationship("Title", back_populates="schedules")

