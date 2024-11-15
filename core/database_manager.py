import json
import logging
import os

import sqlalchemy

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, LargeBinary, ForeignKey, Text, or_, \
    and_
from sqlalchemy.orm import sessionmaker, declarative_base, session, relationship, validates, joinedload, load_only
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
                            title_id=-2,  # Используем отрицательный идентификатор для заглушки
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
            title_id = title_data['title_id']
            self.logger.info(f"save_title started for {title_id}")
            try:
                # Проверка на наличие и корректность данных
                if not isinstance(title_data, dict):
                    raise ValueError("Переданные данные для сохранения тайтла должны быть словарем")

                # Проверка типов ключевых полей
                if not isinstance(title_data.get('title_id'), int):
                    raise ValueError("Неверный тип для 'title_id'. Ожидался тип int.")

                # Преобразование списков и словарей в строки в формате JSON для хранения в базе данных

                existing_title = session.query(Title).filter_by(title_id=title_data['title_id']).first()


                # Преобразуем timestamps если они есть в данных
                if 'updated' in title_data:
                    title_data['updated'] = datetime.utcfromtimestamp(title_data['updated'])
                if 'last_change' in title_data:
                    title_data['last_change'] = datetime.utcfromtimestamp(title_data['last_change'])

                if existing_title:
                    # Update existing title if data has changed
                    is_updated = False

                    for key, value in title_data.items():
                        if getattr(existing_title, key, None) != value:
                            setattr(existing_title, key, value)
                            is_updated = True

                    # Если было установлено, что данные обновились, фиксируем изменения в базе данных
                    if is_updated:
                        session.commit()
                        self.logger.debug(f"Updated title_id: {title_id}")
                else:
                    # Add new title
                    new_title = Title(**title_data)
                    session.add(new_title)
                    session.commit()
                    self.logger.debug(f"Successfully saved title_id: {title_id}")
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении тайтла в базе данных: {e}")

    def save_franchise(self, franchise_data):
        with self.Session as session:
            try:
                title_id = franchise_data['title_id']
                franchise_id = franchise_data['franchise_id']
                franchise_name = franchise_data['franchise_name']
                self.logger.debug(f"Saving franchise_id: {franchise_id} for {title_id}, {franchise_name}")

                # Проверка существования франшизы в базе данных
                existing_franchise = session.query(Franchise).filter_by(title_id=title_id).first()

                if existing_franchise:
                    self.logger.debug(f"Franchise for title_id {title_id} already exists. Updating...")
                    # Обновление существующей франшизы
                    existing_franchise.franchise_id = franchise_id
                    existing_franchise.franchise_name = franchise_name
                    franchise = existing_franchise
                else:
                    # Создание новой франшизы
                    new_franchise = Franchise(
                        title_id=title_id,
                        franchise_id=franchise_id,
                        franchise_name=franchise_name
                    )
                    session.add(new_franchise)
                    session.flush()  # Получаем ID новой франшизы для использования в релизах
                    franchise = new_franchise

                # Обработка информации о релизах франшизы
                for release in franchise_data.get('releases', []):
                    release_title_id = release.get('id')
                    release_code = release.get('code')
                    release_ordinal = release.get('ordinal')
                    release_names = release.get('names', {})

                    # Проверка существования релиза франшизы в базе данных
                    existing_release = session.query(FranchiseRelease).filter_by(franchise_id=franchise.id,
                                                                                 title_id=release_title_id).first()
                    if existing_release:
                        self.logger.debug(
                            f"Franchise release for title_id {release_title_id} already exists. Updating...")
                        # Обновление существующего релиза
                        existing_release.code = release_code
                        existing_release.ordinal = release_ordinal
                        existing_release.name_ru = release_names.get('ru')
                        existing_release.name_en = release_names.get('en')
                        existing_release.name_alternative = release_names.get('alternative')
                    else:
                        # Создание нового релиза франшизы
                        new_release = FranchiseRelease(
                            franchise_id=franchise.id,
                            title_id=release_title_id,
                            code=release_code,
                            ordinal=release_ordinal,
                            name_ru=release_names.get('ru'),
                            name_en=release_names.get('en'),
                            name_alternative=release_names.get('alternative')
                        )
                        session.add(new_release)

                session.commit()
                self.logger.debug(f"Successfully saved franchise for title_id: {title_id}")

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении франшизы в базе данных: {e}")
                return False

    def save_genre(self, title_id, genres):
        with self.Session as session:
            try:
                for genre in genres:
                    # Проверяем, существует ли жанр в таблице Genre
                    existing_genre = session.query(Genre).filter_by(name=genre).first()

                    # Если жанр не существует, добавляем его
                    if not existing_genre:
                        new_genre = Genre(name=genre)
                        session.add(new_genre)
                        session.commit()  # Коммитим, чтобы получить genre_id для следующего этапа
                        genre_id = new_genre.genre_id
                    else:
                        genre_id = existing_genre.genre_id

                    # Добавляем связь в таблицу TitleGenreRelation
                    existing_relation = session.query(TitleGenreRelation).filter_by(title_id=title_id,
                                                                                    genre_id=genre_id).first()
                    if not existing_relation:
                        new_relation = TitleGenreRelation(title_id=title_id, genre_id=genre_id)
                        session.add(new_relation)

                session.commit()
                self.logger.debug(f"Successfully saved genres for title_id: {title_id}")

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении жанров для title_id {title_id}: {e}")

    def save_team_members(self, title_id, team_data):
        with self.Session as session:
            try:
                for role, members in team_data.items():
                    for member_name in members:
                        # Проверяем, существует ли уже участник с таким именем и ролью
                        existing_member = session.query(TeamMember).filter_by(name=member_name, role=role).first()
                        if not existing_member:
                            # Создаем нового участника команды
                            new_member = TeamMember(name=member_name, role=role)
                            session.add(new_member)
                            session.flush()  # Получаем ID нового участника
                            team_member = new_member
                        else:
                            team_member = existing_member

                        # Добавляем связь с тайтлом
                        title_team_relation = TitleTeamRelation(title_id=title_id, team_member_id=team_member.id)
                        session.add(title_team_relation)

                session.commit()
                self.logger.debug(f"Successfully saved team members for title_id: {title_id}")

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении участников команды в базе данных: {e}")
                return False

    def save_episode(self, episode_data):
        with self.Session as session:
            title_id = episode_data['title_id']
            episode_uuid = episode_data['uuid']
            try:
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
                self.logger.debug(f"Successfully saved episode: {episode_uuid}  for title_id: {title_id}")

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
                        self.logger.debug(f"Successfully updated episode: {episode_uuid} for title_id: {title_id}")
                else:
                        if 'created_timestamp' not in episode_data:
                            episode_data['created_timestamp'] = datetime.utcnow()
                        new_episode = Episode(**episode_data)
                        session.add(new_episode)
                        session.commit()
                        self.logger.debug(f"Added episode: {episode_uuid}  for title_id: {title_id}")

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

    def save_torrent(self, torrent_data):
        with self.Session as session:
            title_id = torrent_data['title_id']
            torrent_id = torrent_data['torrent_id']
            self.logger.debug(f"Saving torrent_id: {torrent_id} for title_id: {title_id}")
            try:
                # Проверяем, существует ли уже торрент с данным `torrent_id`
                existing_torrent = session.query(Torrent).filter_by(torrent_id=torrent_id).first()

                if existing_torrent:
                    is_updated = False

                    # Проверка на изменение данных
                    is_updated = any(
                        getattr(existing_torrent, key) != value
                        for key, value in torrent_data.items()
                    )

                    if is_updated:
                        # Обновляем данные, если они изменились
                        session.merge(Torrent(**torrent_data))
                        self.logger.debug(f"Updated torrent_id: {torrent_id} for title_id: {title_id}")
                else:
                    # Добавляем новый торрент, если его еще нет в базе
                    session.add(Torrent(**torrent_data))
                    self.logger.debug(f"Successfully saved torrent_data for title_id: {title_id}")

                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении торрента в базе данных: {e}")

    def process_titles(self, title_data):
        title = title_data
        # Сохранение данных в базу данных через DatabaseManager
        if isinstance(title, dict):
            try:
                title_data = {
                    'title_id': title.get('id', None),
                    'code': title.get('code', ''),
                    'name_ru': title.get('names', {}).get('ru', ''),
                    'name_en': title.get('names', {}).get('en', ''),
                    'alternative_name': title.get('names', {}).get('alternative', ''),
                    'announce': title.get('announce', ''),
                    'status_string': title.get('status', {}).get('string', ''),
                    'status_code': title.get('status', {}).get('code', None),
                    'poster_path_small': title.get('posters', {}).get('small', {}).get('url', ''),
                    'poster_path_medium': title.get('posters', {}).get('medium', {}).get('url', ''),
                    'poster_path_original': title.get('posters', {}).get('original', {}).get('url', ''),
                    'updated': title.get('updated', 0) if title.get('updated') is not None else 0,
                    'last_change': title.get('last_change', 0) if title.get('last_change') is not None else 0,
                    'type_full_string': title.get('type', {}).get('full_string', ''),
                    'type_code': title.get('type', {}).get('code', None),
                    'type_string': title.get('type', {}).get('string', ''),
                    'type_episodes': title.get('type', {}).get('episodes', None),
                    'type_length': title.get('type', {}).get('length', ''),
                    'team_voice': json.dumps(title.get('team', {}).get('voice', [])),
                    'team_translator': json.dumps(title.get('team', {}).get('translator', [])),
                    'team_timing': json.dumps(title.get('team', {}).get('timing', [])),
                    'season_string': title.get('season', {}).get('string', ''),
                    'season_code': title.get('season', {}).get('code', None),
                    'season_year': title.get('season', {}).get('year', None),
                    'season_week_day': title.get('season', {}).get('week_day', None),
                    'description': title.get('description', ''),
                    'in_favorites': title.get('in_favorites', 0),
                    'blocked_copyrights': title.get('blocked', {}).get('copyrights', False),
                    'blocked_geoip': title.get('blocked', {}).get('geoip', False),
                    'blocked_geoip_list': json.dumps(title.get('blocked', {}).get('geoip_list', [])),
                    'last_updated': datetime.utcnow()  # Использование метода utcnow()
                }
                self.save_title(title_data)

                title_id = title_data['title_id']

                # Сохранение данных в связанные таблицы
                franchises = title.get('franchises', [])
                if franchises:
                    for franchise in franchises:
                        franchise_data = {
                            'title_id': title_id,
                            'franchise_id': franchise.get('franchise', {}).get('id'),
                            'franchise_name': franchise.get('franchise', {}).get('name'),
                            'releases': franchise.get('releases', [])
                        }
                        self.logger.debug(f"franchises found for title_id: {title_id} : {franchise_data}")
                        self.save_franchise(franchise_data)

                genres = title.get('genres', [])
                self.logger.debug(f"GENRES: {title_id}:{genres}")
                self.save_genre(title_id, genres)

                # Извлечение данных команды напрямую
                team_data = {
                    'voice': title.get('team', {}).get('voice', []),
                    'translator': title.get('team', {}).get('translator', []),
                    'timing': title.get('team', {}).get('timing', []),
                }
                self.logger.debug(f"TEAM DATA: {title_id}:{team_data}")

                # Проверяем, что данные команды существуют и сохраняем их
                if team_data:
                    self.save_team_members(title_id, team_data)

            except Exception as e:
                self.logger.error(f"Failed to save title to database: {e}")
        return True

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

                    self.save_episode(episode_data)

                except Exception as e:
                    self.logger.error(f"Failed to save episode to database: {e}")
        return True

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

                        self.save_torrent(torrent_data)
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
                    self.logger.debug(f"Poster image was saved to database. title_id: {title_id}")
                else:
                    # Обновляем существующий постер
                    existing_poster.poster_blob = poster_blob
                    existing_poster.last_updated = datetime.utcnow()
                    self.logger.debug(f"Poster image was existed in database. title_id: {title_id}")
                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении постера в базу данных: {e}")

    def get_statistics_from_db(self):
        """Получает статистику из базы данных."""
        with self.Session as session:
            try:
                # Список запросов для разных статистик
                queries = {
                    'titles_count': "SELECT COUNT(DISTINCT title_id) FROM titles",
                    'franchises_count': """
                        SELECT COUNT(DISTINCT f.id)
                        FROM titles t
                        LEFT JOIN franchise_releases fr ON t.title_id = fr.title_id
                        LEFT JOIN franchises f ON fr.franchise_id = f.id
                    """,
                    'episodes_count': "SELECT COUNT(DISTINCT episode_id) FROM episodes",
                    'posters_count': "SELECT COUNT(DISTINCT poster_id) FROM posters",
                    'unique_translators_count': """
                        SELECT COUNT(DISTINCT tm.id)
                        FROM team_members tm
                        LEFT JOIN title_team_relation ttr ON tm.id = ttr.team_member_id
                        WHERE tm.role = 'translator'
                    """,
                    'unique_teams_count': """
                        SELECT COUNT(DISTINCT tm.id)
                        FROM team_members tm
                        LEFT JOIN title_team_relation ttr ON tm.id = ttr.team_member_id
                        WHERE tm.role = 'voice'
                    """,
                    'blocked_titles_count': """
                        SELECT COUNT(DISTINCT title_id)
                        FROM titles
                        WHERE blocked_geoip = 1 OR blocked_copyrights = 1
                    """,
                    'blocked_titles': """
                        SELECT GROUP_CONCAT(DISTINCT title_id || ' (' || name_en || ')')
                        FROM titles
                        WHERE blocked_geoip = 1 OR blocked_copyrights = 1;
                    """,
                    'schedules_count': "SELECT COUNT(DISTINCT schedule_id) FROM schedule",
                    'watch_history_count': "SELECT COUNT(DISTINCT id) FROM watch_history",
                    'torrents_count': "SELECT COUNT(DISTINCT torrent_id) FROM torrents",
                    'genres_count': """
                        SELECT COUNT(DISTINCT g.genre_id)
                        FROM genres g
                        LEFT JOIN title_genre_relation tgr ON g.genre_id = tgr.genre_id
                    """
                }

                # Выполняем каждый запрос и сохраняем результаты
                statistics = {}
                for key, query in queries.items():
                    result = session.execute(sqlalchemy.text(query)).scalar()
                    statistics[key] = result

                return statistics

            except Exception as e:
                self.logger.error(f"Ошибка при получении статистики из базы данных: {e}")
                return {}

    def get_franchises_from_db(self, show_all=False, batch_size=None, offset=0, title_id=None):
        """Получает все тайтлы вместе с информацией о франшизах."""
        with self.Session as session:
            try:
                # Начинаем формирование базового запроса
                if title_id:
                    # Если указан title_id, находим все связанные тайтлы
                    franchise_subquery = session.query(FranchiseRelease.franchise_id).filter(
                        FranchiseRelease.title_id == title_id
                    ).scalar_subquery()

                    query = session.query(Title).join(FranchiseRelease).join(Franchise).filter(
                        FranchiseRelease.franchise_id == franchise_subquery,
                        FranchiseRelease.franchise_id.isnot(None)
                    )
                else:
                    # Если show_all=True, получить все тайтлы, у которых есть франшизы
                    query = session.query(Title).join(FranchiseRelease).join(Franchise).filter(
                        FranchiseRelease.franchise_id.isnot(None)
                    )
                # Если указан batch_size, применяем лимит и смещение
                if show_all:
                    if batch_size:
                        query = query.offset(offset).limit(batch_size)

                # Получаем результат запроса
                titles = query.options(joinedload(Title.franchises).joinedload(FranchiseRelease.franchise)).all()

                return titles

            except Exception as e:
                self.logger.error(f"Ошибка при получении тайтлов с франшизами: {e}")
                return []

    def get_poster_link(self, title_id):
        with self.Session as session:
            try:
                self.logger.debug(f"Processing poster link for title_id: {title_id}")

                # Запрос для получения poster_path_small для конкретного title_id
                poster_link = session.query(Title.poster_path_small).filter(Title.title_id == title_id).scalar()

                if poster_link:
                    self.logger.debug(f"Poster link found for title_id: {title_id}, link: {poster_link}")
                    return poster_link

                self.logger.warning(f"No poster link found for title_id: {title_id}")
                return None

            except Exception as e:
                self.logger.error(f"Error fetching poster from database: {e}")
                return None

    def check_poster_exists(self, title_id):
        """
        Checks if a poster exists in the database for a given title_id.
        """
        with self.Session as session:
            try:
                return session.query(Poster.title_id).filter_by(title_id=title_id).scalar() is not None
            except Exception as e:
                self.logger.error(f"Error checking poster existence in database: {e}")
                return False

    def get_poster_blob(self, title_id):
        """
        Retrieves the poster blob for a given title_id.
        If check_exists_only is True, returns a boolean indicating whether the poster exists.
        """
        with self.Session as session:
            try:
                poster = session.query(Poster).filter_by(title_id=title_id).first()
                if poster:
                    self.logger.debug(f"Poster image was found in database. title_id: {title_id}")
                    return poster.poster_blob, False  # Это реальный постер

                # Используем placeholder, если постер не найден
                placeholder_poster = session.query(Poster).filter_by(title_id=2).first()
                if placeholder_poster:
                    self.logger.debug(
                        f"Poster image was not found in database for title_id: {title_id}. Using placeholder.")
                    return placeholder_poster.poster_blob, True  # Это плейсхолдер

                self.logger.warning(f"No poster found for title_id: {title_id} and no placeholder available.")
                return None, False

            except Exception as e:
                self.logger.error(f"Error fetching poster from database: {e}")
                return None, False

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

    def get_genres_from_db(self, title_id):
        with self.Session as session:
            try:
                # Получаем все жанры, связанные с данным title_id через таблицу TitleGenreRelation
                relations = session.query(TitleGenreRelation).filter_by(title_id=title_id).all()
                genres = [relation.genre.name for relation in relations]
                if genres:
                    self.logger.debug(f"Genres were found in database for title_id: {title_id}")
                    return genres
            except Exception as e:
                self.logger.error(f"Ошибка при загрузке Genres из базы данных: {e}")
                return None

    def get_titles_by_keywords(self, search_string):
        """Searches for titles by keywords in code, name_ru, name_en, alternative_name, or by title_id, and returns a list of title_ids."""
        keywords = search_string.split(',')
        keywords = [kw.strip() for kw in keywords]
        if not keywords:
            return []
        self.logger.debug(f"keyword for processing: {keywords}")
        with self.Session as session:
            try:
                # Check if the keywords contain only title_ids
                if all(kw.isdigit() for kw in keywords):
                    title_ids = [int(kw) for kw in keywords]
                    query = session.query(Title).filter(Title.title_id.in_(title_ids))
                    titles = query.all()
                else:
                    # Build dynamic filter using SQLAlchemy's 'or_' to match any keyword in any column
                    filters = [
                        and_(
                            Title.code.ilike(f"%{keyword}%"),
                            Title.name_ru.ilike(f"%{keyword}%"),
                            Title.name_en.ilike(f"%{keyword}%"),
                            Title.alternative_name.ilike(f"%{keyword}%")
                        )
                        for keyword in keywords
                    ]
                    # Combine filters using 'and_' so that all keywords must match (across any field)
                    query = session.query(Title).filter(*filters)
                    titles = query.all()

                # Extract and return only the title_ids from the matched titles
                title_ids = [title.title_id for title in titles]
                return title_ids
            except Exception as e:
                self.logger.error(f"Error during title search: {e}")
                return []

    def get_titles_from_db(self, day_of_week=None, show_all=False, batch_size=None, offset=0, title_id=None, title_ids=None, system=False):
        """Получает список тайтлов из базы данных через DatabaseManager."""
        """
        Returns a SQLAlchemy query for fetching titles based on given conditions.
        :param day_of_week: Specific day of the week to filter by.
        :param show_all: If true, returns all titles.
        :param title_id: If specified, returns a title with the given title_id.
        :return: SQLAlchemy Query object
        """
        with self.Session as session:
            try:
                # Используем `joinedload` для предварительной загрузки жанров и эпизодов
                query = session.query(Title).options(
                    joinedload(Title.genres).joinedload(TitleGenreRelation.genre),
                    joinedload(Title.episodes)
                )

                if title_id:
                    query = query.filter(Title.title_id == title_id)
                elif title_ids:
                    query = query.filter(Title.title_id.in_(title_ids))
                elif system:
                    query = session.query(Title) \
                        .outerjoin(FranchiseRelease) \
                        .outerjoin(Franchise) \
                        .options(
                        joinedload(Title.franchises).joinedload(FranchiseRelease.franchise),
                        joinedload(Title.episodes),  # Загрузить связанные эпизоды
                        joinedload(Title.poster)  # Загрузить связанные постеры, если есть связь poster
                    )
                elif not show_all:
                    query = query.join(Schedule).filter(Schedule.day_of_week == day_of_week)
                if batch_size:
                    query = query.offset(offset).limit(batch_size)

                titles = query.all()

                # Создаем список жанров в виде строк для каждого тайтла и добавляем их в новое поле `genre_names`
                for title in titles:
                    title.genre_names = [relation.genre.name for relation in title.genres if relation.genre]

                # self.logger.debug(f"Titles were found in database. QUERY: {str(query)}")
                # self.logger.debug(f"Titles were found in database. titles: {titles}")
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

    franchises = relationship("FranchiseRelease", back_populates="title", cascade="all, delete-orphan")
    #releases = relationship("FranchiseRelease", back_populates="title", cascade="all, delete-orphan")
    genres = relationship("TitleGenreRelation", back_populates="title")
    team_members = relationship("TitleTeamRelation", back_populates="title")
    episodes = relationship("Episode", back_populates="title")
    torrents = relationship("Torrent", back_populates="title")
    posters = relationship("Poster", back_populates="title")
    schedules = relationship("Schedule", back_populates="title")

# Таблица связей между Title и Franchise
class FranchiseRelease(Base):
    __tablename__ = 'franchise_releases'

    id = Column(Integer, primary_key=True, autoincrement=True)
    franchise_id = Column(Integer, ForeignKey('franchises.id'), nullable=False)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    code = Column(String, nullable=False)
    ordinal = Column(Integer, nullable=True)
    name_ru = Column(String, nullable=True)
    name_en = Column(String, nullable=True)
    name_alternative = Column(String, nullable=True)

    franchise = relationship("Franchise", back_populates="releases")
    title = relationship("Title", back_populates="franchises")

class Franchise(Base):
    __tablename__ = 'franchises'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    franchise_id = Column(String, nullable=False)  # Добавим идентификатор франшизы как отдельное поле
    franchise_name = Column(String, nullable=False)  # Название франшизы

    releases = relationship("FranchiseRelease", back_populates="franchise", cascade="all, delete-orphan")

class Genre(Base):
    __tablename__ = 'genres'
    genre_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)

    titles = relationship("TitleGenreRelation", back_populates="genre")

# Таблица связей между Title и Genre
class TitleGenreRelation(Base):
    __tablename__ = 'title_genre_relation'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    genre_id = Column(Integer, ForeignKey('genres.genre_id'), nullable=False)

    title = relationship("Title", back_populates="genres")
    genre = relationship("Genre", back_populates="titles")

class TeamMember(Base):
    __tablename__ = 'team_members'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)  # Имя участника команды
    role = Column(String, nullable=False)  # Роль участника: voice, translator, timing

    titles = relationship("TitleTeamRelation", back_populates="team_member")

# Таблица связей между Title и TeamMember
class TitleTeamRelation(Base):
    __tablename__ = 'title_team_relation'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    team_member_id = Column(Integer, ForeignKey('team_members.id'), nullable=False)

    title = relationship("Title", back_populates="team_members")
    team_member = relationship("TeamMember", back_populates="titles")

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

