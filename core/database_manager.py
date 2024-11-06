import json
import logging
import os

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, LargeBinary, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, session, relationship, validates, joinedload
from datetime import datetime, timezone
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class DatabaseManager:
    def __init__(self, db_path):
        self.current_poster_index = None
        self.logger = logging.getLogger(__name__)
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)()


    def initialize_tables(self):
        # Создаем таблицы, если они еще не существуют
        Base.metadata.create_all(self.engine)

        # Добавляем заглушку изображения, если оно не добавлено
        with self.Session as session:
            try:
                placeholder_poster = session.query(Poster).filter_by(title_id=1).first()
                if not placeholder_poster:
                    with open('static/background.png', 'rb') as image_file:
                        poster_blob = image_file.read()
                        placeholder_poster = Poster(
                            title_id=1,  # Используем отрицательный идентификатор для заглушки
                            poster_blob=poster_blob,
                            last_updated=datetime.utcnow()
                        )
                        session.add(placeholder_poster)
                        session.commit()
                        self.logger.info("Placeholder image 'background.png' was added to posters table.")
            except Exception as e:
                session.rollback()
                self.logger.error(f"Error initializing placeholder image in posters table: {e}")

        # Добавляем заглушку изображения, если оно не добавлено
        with self.Session as session:
            try:
                placeholder_poster = session.query(Poster).filter_by(title_id=2).first()
                if not placeholder_poster:
                    with open('static/no_image.png', 'rb') as image_file:
                        poster_blob = image_file.read()
                        placeholder_poster = Poster(
                            title_id=2,  # Используем отрицательный идентификатор для заглушки
                            poster_blob=poster_blob,
                            last_updated=datetime.utcnow()
                        )
                        session.add(placeholder_poster)
                        session.commit()
                        self.logger.info("Placeholder image 'no_image.png' was added to posters table.")
            except Exception as e:
                session.rollback()
                self.logger.error(f"Error initializing placeholder image in posters table: {e}")

    def save_title(self, title_data):
        with self.Session as session:
            try:
                self.logger.debug(f"Saving title data: {len(title_data) if isinstance(title_data, dict) else 'not a dict'}")

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

                existing_title = session.query(Title).filter_by(title_id=title_data['title_id']).first()

                if existing_title:
                    # Update existing title if data has changed
                    is_updated = False
                    for key, value in title_data.items():
                        if getattr(existing_title, key, None) != value:
                            setattr(existing_title, key, value)
                            is_updated = True
                    if is_updated:
                        session.commit()

                    if is_updated:
                        session.commit()  # Коммит только если есть изменения
                else:
                    # Add new title
                    new_title = Title(**title_data)
                    session.add(new_title)
                    session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении тайтла в базе данных: {e}")

    def save_episode(self, episode_data):
        with self.Session as session:
            try:
                self.logger.debug(f"Saving episode data: {len(episode_data)} keys (type: {type(episode_data).__name__})")

                if not isinstance(episode_data, dict):
                    self.logger.error(f"Invalid episode data: {episode_data}")
                    return

                # Создаем копию данных
                processed_data = episode_data.copy()

                # Преобразуем timestamps если они есть в данных
                if 'created_timestamp' in processed_data:
                    processed_data['created_timestamp'] = datetime.utcfromtimestamp(processed_data['created_timestamp'])

                existing_episode = session.query(Episode).filter_by(
                    uuid=processed_data['uuid'],
                    title_id=processed_data['title_id']
                ).first()

                if existing_episode:
                    is_updated = False
                    protected_fields = {'episode_id', 'title_id', 'created_timestamp'}

                    for key, value in episode_data.items():
                        if key not in protected_fields and getattr(existing_episode, key) != value:
                            setattr(existing_episode, key, value)
                            self.logger.debug(f"Existing episode: {protected_fields}")
                            is_updated = True
                    if is_updated:
                        existing_episode.last_updated = datetime.utcnow()
                        session.commit()
                else:
                        if 'created_timestamp' not in episode_data:
                            episode_data['created_timestamp'] = datetime.utcnow()
                        new_episode = Episode(**episode_data)
                        session.add(new_episode)
                        session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении эпизода в базе данных: {e}")

    def save_schedule(self, day_of_week, title_id):
        with self.Session as session:
            try:
                schedule_entry = Schedule(day_of_week=day_of_week, title_id=title_id)
                session.add(schedule_entry)
                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении расписания: {e}")

    def get_titles_for_day(self, day_of_week):
        """Загружает тайтлы для указанного дня недели из базы данных."""
        with self.Session as session:
            try:
                return session.query(Title).join(Schedule).filter(Schedule.day_of_week == day_of_week).all()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при получении тайтлов для дня недели: {e}")

    def get_titles_query(self, day_of_week=None, show_all=False, title_id=None):
        """
        Returns a SQLAlchemy query for fetching titles based on given conditions.
        :param day_of_week: Specific day of the week to filter by.
        :param show_all: If true, returns all titles.
        :param title_id: If specified, returns a title with the given title_id.
        :return: SQLAlchemy Query object
        """
        with self.Session as session:
            query = session.query(Title).options(joinedload(Title.episodes))
            if title_id:
                query = query.filter(Title.title_id == title_id)
            elif not show_all:
                query = query.join(Schedule).filter(Schedule.day_of_week == day_of_week)

            return query

    def save_torrent(self, torrent_data):
        with self.Session as session:
            try:
                # Проверяем, существует ли уже торрент с данным `torrent_id`
                existing_torrent = session.query(Torrent).filter_by(torrent_id=torrent_data['torrent_id']).first()

                if existing_torrent:
                    # Проверка на изменение данных
                    is_updated = any(
                        getattr(existing_torrent, key) != value
                        for key, value in torrent_data.items()
                    )

                    if is_updated:
                        # Обновляем данные, если они изменились
                        session.merge(Torrent(**torrent_data))
                else:
                    # Добавляем новый торрент, если его еще нет в базе
                    session.add(Torrent(**torrent_data))

                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении торрента в базе данных: {e}")

    def process_titles(self, title_data):
        title = title_data
        # Сохранение данных в базу данных через DatabaseManager
        try:
            # Сохранение тайтла
            if isinstance(title, dict):
                title_data = {
                    'title_id': title.get('id'),
                    'code': title.get('code'),
                    'name_ru': title.get('names', {}).get('ru'),
                    'name_en': title.get('names', {}).get('en'),
                    'alternative_name': title.get('names', {}).get('alternative'),
                    'franchises': json.dumps(title.get('franchises', [])),
                    'announce': title.get('announce'),
                    'status_string': title.get('status', {}).get('string'),
                    'status_code': title.get('status', {}).get('code'),
                    'poster_path_small': title.get('posters', {}).get('small', {}).get('url'),
                    'poster_path_medium': title.get('posters', {}).get('medium', {}).get('url'),
                    'poster_path_original': title.get('posters', {}).get('original', {}).get('url'),
                    'updated': title.get('updated'),
                    'last_change': title.get('last_change'),
                    'type_full_string': title.get('type', {}).get('full_string'),
                    'type_code': title.get('type', {}).get('code'),
                    'type_string': title.get('type', {}).get('string'),
                    'type_episodes': title.get('type', {}).get('episodes'),
                    'type_length': title.get('type', {}).get('length'),
                    'genres': json.dumps(title.get('genres', [])),
                    'team_voice': json.dumps(title.get('team', {}).get('voice', [])),
                    'team_translator': json.dumps(title.get('team', {}).get('translator', [])),
                    'team_timing': json.dumps(title.get('team', {}).get('timing', [])),
                    'season_string': title.get('season', {}).get('string'),
                    'season_code': title.get('season', {}).get('code'),
                    'season_year': title.get('season', {}).get('year'),
                    'season_week_day': title.get('season', {}).get('week_day'),
                    'description': title.get('description'),
                    'in_favorites': title.get('in_favorites'),
                    'blocked_copyrights': title.get('blocked', {}).get('copyrights'),
                    'blocked_geoip': title.get('blocked', {}).get('geoip'),
                    'blocked_geoip_list': json.dumps(title.get('blocked', {}).get('geoip_list', [])),
                    'last_updated': datetime.utcnow()  # Использование метода utcnow()
                }

                title_id = title_data['title_id']
                if self.save_title(title_data):
                    self.logger.debug(f"Successfully saved title_id: {title_id}")
                else:
                    self.logger.warning(f"Failed to save title_id: {title_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save title to database: {e}")

    def process_episodes(self, title_data):
        for episode in title_data.get("player", {}).get("list", {}).values():
            if not isinstance(episode, dict):
                self.logger.error(f"Invalid type for episode. Expected dict, got {type(episode)}")
                continue

            if "hls" in episode:
                try:
                    episode_data = {
                        'episode_id': episode.get('id'),
                        'title_id': title_data.get('id'),
                        'episode_number': episode.get('episode'),
                        'name': episode.get('name', f'Серия {episode.get("episode")}'),
                        'uuid': episode.get('uuid'),
                        'created_timestamp': episode.get('created_timestamp'),
                        'hls_fhd': episode.get('hls', {}).get('fhd'),
                        'hls_hd': episode.get('hls', {}).get('hd'),
                        'hls_sd': episode.get('hls', {}).get('sd'),
                        'preview_path': episode.get('preview'),
                        'skips_opening': json.dumps(episode.get('skips', {}).get('opening', [])),
                        'skips_ending': json.dumps(episode.get('skips', {}).get('ending', []))
                    }
                    title_id = episode_data['title_id']
                    if self.save_episode(episode_data):
                        self.logger.debug(f"Successfully saved episode_data for title_id: {title_id}")
                    else:
                        self.logger.warning(f"Failed to save episode_data for title_id: {title_id}")
                    return True
                except Exception as e:
                    self.logger.error(f"Failed to save episode to database: {e}")

    def process_torrents(self, title_data):
        if "torrents" in title_data and "list" in title_data["torrents"]:
            for torrent in title_data["torrents"]["list"]:
                url = torrent.get("url")
                if url:
                    try:
                        torrent_data = {
                            'torrent_id': torrent.get('torrent_id'),
                            'title_id': title_data.get('id'),
                            'episodes_range': torrent.get('episodes', {}).get('string', 'Неизвестный диапазон'),
                            'quality': torrent.get('quality', {}).get('string', 'Качество не указано'),
                            'quality_type': torrent.get('quality', {}).get('type'),
                            'resolution': torrent.get('quality', {}).get('resolution'),
                            'encoder': torrent.get('quality', {}).get('encoder'),
                            'leechers': torrent.get('leechers'),
                            'seeders': torrent.get('seeders'),
                            'downloads': torrent.get('downloads'),
                            'total_size': torrent.get('total_size'),
                            'size_string': torrent.get('size_string'),
                            'url': torrent.get('url'),
                            'magnet_link': torrent.get('magnet'),
                            'uploaded_timestamp': torrent.get('uploaded_timestamp'),
                            'hash': torrent.get('hash'),
                            'torrent_metadata': torrent.get('metadata'),
                            'raw_base64_file': torrent.get('raw_base64_file')
                        }
                        title_id = torrent_data['title_id']
                        if self.save_torrent(torrent_data):
                            self.logger.debug(f"Successfully saved torrent_data for title_id: {title_id}")
                        else:
                            self.logger.warning(f"Failed to save torrent_data for title_id: {title_id}")
                    except Exception as e:
                        self.logger.error(f"Ошибка при сохранении торрента в базе данных: {e}")
        return True

    def save_poster_to_db(self, title_id, poster_blob):
        with self.Session as session:
            try:
                # Проверяем, существует ли уже постер для данного title_id
                existing_poster = session.query(Poster).filter_by(title_id=title_id).first()
                if not existing_poster:
                    # Создаем новый объект Poster и добавляем в базу
                    new_poster = Poster(title_id=title_id, poster_blob=poster_blob, last_updated=datetime.utcnow())

                    session.add(new_poster)
                else:
                    # Обновляем существующий постер
                    existing_poster.poster_blob = poster_blob
                    existing_poster.last_updated = datetime.utcnow()

                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении постера в базу данных: {e}")

    def get_poster_blob(self, title_id):
        with self.Session as session:
            try:
                poster = session.query(Poster).filter_by(title_id=title_id).first()
                if poster:
                    return poster.poster_blob
                return None
            except Exception as e:
                self.logger.error(f"Error fetching poster from database: {e}")
                return None

    def get_torrents_from_db(self, title_id):
        with self.Session as session:
            try:
                torrents = session.query(Torrent).filter_by(title_id=title_id).all()
                if torrents:
                    self.logger.debug(f"Torrent data was found in database.")
                    return torrents
                return None
            except Exception as e:
                self.logger.error(f"Error fetching torrent data from database: {e}")

    def get_titles_from_db(self, day_of_week=None, show_all=False, batch_size=None, offset=0, title_id=None):
        """Получает список тайтлов из базы данных через DatabaseManager."""
        try:
            query = self.get_titles_query(day_of_week, show_all, title_id)
            if batch_size:
                query = query.offset(offset).limit(batch_size)
            titles = query.all()
            return titles
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке тайтлов из базы данных: {e}")
            return []


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
    schedule_id = Column(Integer, primary_key=True, autoincrement=True)  # Primary Key уже есть
    day_of_week = Column(Integer, nullable=False)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)

    title = relationship("Title", back_populates="schedules")

