# save.py
import ast
import logging

from sqlalchemy import or_
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from core.tables import Title, Schedule, History, Rating, FranchiseRelease, Franchise, Poster, Torrent, \
    TitleGenreRelation, \
    Template, Genre, TeamMember, TitleTeamRelation, Episode, ProductionStudio


class SaveManager:
    def __init__(self, engine):
        self.logger = logging.getLogger(__name__)
        self.Session = sessionmaker(bind=engine)()

    def save_poster(self, title_id, poster_blob):
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

    def save_need_to_see(self, user_id, title_id, need_to_see=True):
        with self.Session as session:
            try:
                # Получение всех существующих записей для данного title_id
                existing_statuses = session.query(History).filter(
                    History.user_id == user_id,
                    History.title_id == title_id
                ).all()
                if existing_statuses:
                    # Обновление флага need_to_see для всех записей
                    for existing_status in existing_statuses:
                        existing_status.need_to_see = need_to_see
                        self.logger.debug(
                            f"Updated need_to_see for title_id: {title_id}, episode_id: {existing_status.episode_id} to {need_to_see}")
                else:
                    new_add = History(
                        user_id=user_id,
                        title_id=title_id,
                        need_to_see=1
                    )
                    session.add(new_add)
                # Фиксация изменений в базе данных
                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(
                    f"Error saving need_to_see for title_id {title_id}: {e}")
                raise

    def save_watch_all_episodes(self, user_id, title_id, is_watched=False, episode_ids=None):
        with self.Session as session:
            try:
                if episode_ids is None or not isinstance(episode_ids, list) or len(episode_ids) == 0:
                    self.logger.error("Invalid episode_ids provided for bulk update.")
                    raise ValueError("Episode IDs must be a non-empty list.")

                # Получение всех существующих записей для данных episode_ids
                existing_statuses = session.query(History).filter(
                    History.user_id == user_id,
                    History.title_id == title_id,
                    History.episode_id.in_(episode_ids)
                ).all()

                # Обновление существующих записей
                existing_episode_ids = set()
                for existing_status in existing_statuses:
                    existing_status.previous_watched_at = existing_status.last_watched_at
                    existing_status.is_watched = is_watched
                    existing_status.last_watched_at = datetime.utcnow()
                    existing_status.watch_change_count += 1
                    existing_episode_ids.add(existing_status.episode_id)

                    self.logger.debug(f"BULK Updated watch status for user_id: {user_id}, title_id: {title_id}, episode_id: {existing_status.episode_id} STATUS: {is_watched}")

                # Добавление новых записей для эпизодов, которых нет в базе данных
                new_episode_ids = set(episode_ids) - existing_episode_ids
                new_adds = []
                for episode_id in new_episode_ids:
                    new_add = History(
                        user_id=user_id,
                        title_id=title_id,
                        episode_id=episode_id,
                        is_watched=is_watched,
                        last_watched_at=datetime.utcnow() if is_watched else None,
                        watch_change_count=1 if is_watched else 0
                    )
                    new_adds.append(new_add)

                    self.logger.debug(f"BULK Added new watch status for user_id: {user_id}, title_id: {title_id}, episode_id: {episode_id}, STATUS: {is_watched}")

                # Добавляем новые записи в сессию
                session.bulk_save_objects(new_adds)

                # Фиксация изменений в базе данных
                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"BULK Error saving watch status for user_id {user_id}, title_id {title_id}, episode_ids {episode_ids}: {e}")
                raise

    def save_watch_status(self, user_id, title_id, episode_id=None, is_watched=False, torrent_id=None, is_download=False):
        with self.Session as session:
            try:
                # Single update for episode or torrent
                filters = {'user_id': user_id, 'title_id': title_id}
                if episode_id is not None:
                    filters['episode_id'] = episode_id
                elif torrent_id is not None:
                    filters['torrent_id'] = torrent_id
                else:
                    filters['episode_id'] = None
                    filters['torrent_id'] = None

                existing_status = session.query(History).filter_by(**filters).one_or_none()

                if existing_status:
                    # Update existing status
                    if episode_id is not None:
                        existing_status.previous_watched_at = existing_status.last_watched_at
                        existing_status.is_watched = is_watched
                        existing_status.last_watched_at = datetime.utcnow()
                        existing_status.watch_change_count += 1
                        self.logger.debug(
                            f"Updated watch status for user_id: {user_id}, title_id: {title_id}, episode_id: {episode_id} STATUS: {is_watched}")
                    elif torrent_id is not None:
                        existing_status.previous_download_at = existing_status.last_download_at
                        existing_status.is_download = is_download
                        existing_status.last_download_at = datetime.utcnow()
                        existing_status.download_change_count += 1
                        self.logger.debug(
                            f"Updated download status for user_id: {user_id}, title_id: {title_id}, torrent_id: {torrent_id} STATUS: {is_download}")
                    else:
                        existing_status.previous_watched_at = existing_status.last_watched_at
                        existing_status.is_watched = is_watched
                        existing_status.last_watched_at = datetime.utcnow()
                        existing_status.watch_change_count += 1
                        self.logger.debug(
                            f"Updated watch status for user_id: {user_id}, title_id: {title_id} STATUS: {is_watched}")
                else:
                    # Add a new status if none exists
                    new_add = History(
                        user_id=user_id,
                        title_id=title_id,
                        torrent_id=torrent_id if torrent_id is not None else None,
                        episode_id=episode_id if episode_id is not None else None,
                        is_download=is_download if torrent_id is not None else False,
                        is_watched=is_watched if episode_id is not None else False,
                        last_download_at=datetime.utcnow() if torrent_id is not None else None,
                        last_watched_at=datetime.utcnow() if episode_id is not None else None,
                        download_change_count=1 if torrent_id is not None else 0,
                        watch_change_count=1 if episode_id is not None else 0
                    )

                    session.add(new_add)
                    self.logger.debug(
                        f"Added new watch status for user_id: {user_id}, title_id: {title_id}, episode_id: {episode_id}, torrent_id: {torrent_id}")

                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(
                    f"Error saving watch status for user_id {user_id}, title_id {title_id}, episode_id {episode_id}: {e}")
                raise

    def save_ratings(self, title_id, rating_value, rating_name='CMERS'):
        """
        "Comprehensive Media Evaluation Rating System" or CMERS
        The CMERS system would operate as follows:
            - Title Appearance Frequency
            - Watched Episode Count
            - Individual Title Prominence
            - User-Provided Ratings
            - External Source Ratings
            :param title_id:
            :param rating_value:
            :type rating_name: object
        """
        with self.Session as session:
            try:
                existing_rating = session.query(Rating).filter_by(title_id=title_id).one_or_none()
                if existing_rating:
                    existing_rating.rating_value = rating_value
                    existing_rating.rating_name = rating_name
                    existing_rating.last_updated = datetime.utcnow()
                    self.logger.debug(f"Updated rating for title_id: {title_id}")
                else:
                    new_rating = Rating(title_id=title_id, rating_value=rating_value, rating_name=rating_name, last_updated=datetime.utcnow())
                    session.add(new_rating)
                    self.logger.debug(f"Added new rating for title_id: {title_id}")
                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Error saving rating for title_id {title_id}: {e}")
                raise

    def save_title(self, title_data):
        with self.Session as session:
            title_id = title_data['title_id']
            self.logger.info(f"save_title started for {title_id}")
            try:
                # Check if the title data is a dictionary
                if not isinstance(title_data, dict):
                    raise ValueError("The title data must be a dictionary.")

                # Check key field types
                if not isinstance(title_id, int):
                    raise ValueError("Invalid type for 'title_id'. Expected int.")

                # Convert timestamps if they exist
                if 'updated' in title_data:
                    title_data['updated'] = datetime.utcfromtimestamp(title_data['updated'])
                if 'last_change' in title_data:
                    title_data['last_change'] = datetime.utcfromtimestamp(title_data['last_change'])

                # Check for an existing title by title_id or code
                existing_title = session.query(Title).filter(
                    or_(
                        Title.title_id == title_id,
                        Title.code == title_data['code']
                    )
                ).first()

                if existing_title:
                    # Update existing title if data has changed
                    is_updated = False
                    for key, value in title_data.items():
                        if getattr(existing_title, key, None) != value:
                            setattr(existing_title, key, value)
                            is_updated = True

                    if is_updated:
                        session.commit()
                        self.logger.debug(f"Updated title_id: {title_id}")
                else:
                    # Add a new title
                    new_title = Title(**title_data)
                    session.add(new_title)
                    session.commit()
                    self.logger.debug(f"Successfully saved title_id: {title_id}")
            except Exception as e:
                session.rollback()
                self.logger.error(f"Error saving title to database: {e}")

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
                    existing_franchise.last_updated = datetime.utcnow()
                    franchise = existing_franchise
                else:
                    # Создание новой франшизы
                    new_franchise = Franchise(
                        title_id=title_id,
                        franchise_id=franchise_id,
                        franchise_name=franchise_name,
                        last_updated=datetime.utcnow()
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
                        existing_release.last_updated = datetime.utcnow()
                    else:
                        # Создание нового релиза франшизы
                        new_release = FranchiseRelease(
                            franchise_id=franchise.id,
                            title_id=release_title_id,
                            code=release_code,
                            ordinal=release_ordinal,
                            name_ru=release_names.get('ru'),
                            name_en=release_names.get('en'),
                            name_alternative=release_names.get('alternative'),
                            last_updated=datetime.utcnow()
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
                        new_genre = Genre(name=genre, last_updated=datetime.utcnow())
                        session.add(new_genre)
                        session.commit()  # Коммитим, чтобы получить genre_id для следующего этапа
                        genre_id = new_genre.genre_id
                    else:
                        genre_id = existing_genre.genre_id

                    # Добавляем связь в таблицу TitleGenreRelation
                    existing_relation = session.query(TitleGenreRelation).filter_by(title_id=title_id,
                                                                                    genre_id=genre_id).first()
                    if not existing_relation:
                        new_relation = TitleGenreRelation(title_id=title_id, genre_id=genre_id, last_updated=datetime.utcnow())
                        session.add(new_relation)

                session.commit()
                self.logger.debug(f"Successfully saved genres for title_id: {title_id}")

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении жанров для title_id {title_id}: {e}")

    def save_team_members(self, title_id, team_data):
        with self.Session as session:
            try:
                for role, members_str in team_data.items():
                    try:
                        # Convert the string representation of list into an actual list
                        members = ast.literal_eval(members_str)
                    except (SyntaxError, ValueError) as e:
                        self.logger.error(f"Failed to decode team data for role '{role}' in title_id {title_id}: {e}")
                        continue

                    for member_name in members:
                        # Проверяем, существует ли уже участник с таким именем и ролью
                        existing_member = session.query(TeamMember).filter_by(name=member_name, role=role).first()
                        if not existing_member:
                            # Создаем нового участника команды
                            new_member = TeamMember(name=member_name, role=role, last_updated=datetime.utcnow())
                            session.add(new_member)
                            session.flush()  # Получаем ID нового участника
                            team_member = new_member
                        else:
                            team_member = existing_member

                        # Добавляем связь с тайтлом
                        title_team_relation = TitleTeamRelation(title_id=title_id, team_member_id=team_member.id, last_updated=datetime.utcnow())
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

    def save_schedule(self, day_of_week, title_id, last_updated=None):
        with self.Session as session:
            try:
                # Check if the entry already exists
                existing_schedule = session.query(Schedule).filter_by(day_of_week=day_of_week,
                                                                      title_id=title_id).first()
                if existing_schedule:
                    # If it exists, update the last_updated field
                    existing_schedule.last_updated = last_updated or datetime.utcnow()
                    self.logger.debug(
                        f"Schedule entry for day {day_of_week} and title_id {title_id} already exists. Updating last_updated.")
                else:
                    # If it doesn't exist, create a new schedule entry
                    schedule_entry = Schedule(day_of_week=day_of_week, title_id=title_id, last_updated=last_updated)
                    session.add(schedule_entry)
                    self.logger.debug(f"Adding new schedule entry for day {day_of_week} and title_id {title_id}.")

                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении расписания: {e}")

    def save_torrent(self, torrent_data):
        with self.Session as session:

            # Создаем копию данных
            processed_data = torrent_data.copy()

            # Преобразуем timestamps если они есть в данных
            if 'uploaded_timestamp' in processed_data:
                processed_data['uploaded_timestamp'] = datetime.utcfromtimestamp(processed_data['uploaded_timestamp'])

            title_id = processed_data['title_id']
            torrent_id = processed_data['torrent_id']
            self.logger.debug(f"Saving torrent_id: {torrent_id} for title_id: {title_id}")
            try:
                # Проверяем, существует ли уже торрент с данным `torrent_id`
                existing_torrent = session.query(Torrent).filter_by(torrent_id=torrent_id).first()

                if existing_torrent:
                    is_updated = False

                    # Проверка на изменение данных
                    is_updated = any(
                        getattr(existing_torrent, key) != value
                        for key, value in processed_data.items()
                    )

                    if is_updated:
                        # Обновляем данные, если они изменились
                        session.merge(Torrent(**processed_data))
                        self.logger.debug(f"Updated torrent_id: {torrent_id} for title_id: {title_id}")
                else:
                    # Добавляем новый торрент, если его еще нет в базе
                    session.add(Torrent(**processed_data))
                    self.logger.debug(f"Successfully saved torrent_data for title_id: {title_id}")

                session.commit()
            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении торрента в базе данных: {e}")

    def remove_schedule_day(self, title_ids, day_of_week):
        with self.Session as session:
            try:
                # Преобразуем title_ids, если это множество
                if isinstance(title_ids, set):
                    title_ids = list(title_ids)

                # Проверяем корректность входных данных
                if not title_ids or not isinstance(title_ids, list):
                    raise ValueError(f"Invalid title_ids: {title_ids}")

                self.logger.debug(f"Querying schedules with title_ids: {title_ids} and day_of_week: {day_of_week}")

                # Проверяем, что находится в таблице
                all_schedules = session.query(Schedule).all()
                self.logger.debug(f"All schedules in table: {all_schedules}")

                # Выполняем фильтрацию
                schedules_to_update = (
                    session.query(Schedule)
                    .filter(Schedule.title_id.in_(title_ids), Schedule.day_of_week == day_of_week)
                )

                result = schedules_to_update.all()
                self.logger.debug(f"Filtered schedules: {result}")

                # Если записи найдены, удаляем их
                if result:
                    deleted_count = schedules_to_update.delete(synchronize_session='fetch')
                    session.commit()
                    self.logger.debug(
                        f"Removed {deleted_count} schedules for day {day_of_week} and titles {title_ids}"
                    )
                else:
                    self.logger.debug(f"No schedules found for day {day_of_week} and titles {title_ids}")
            except Exception as e:
                session.rollback()
                self.logger.error(
                    f"Error while removing schedules for title_ids {title_ids} and day {day_of_week}: {e}")

    def save_studio_to_db(self, title_ids, studio_name):
        """Функция для добавления новой студии в базу данных для нескольких тайтлов."""
        with self.Session as session:  # Исправлено: создание новой сессии
            try:
                # Проверка, что массив title_ids не пуст
                if not title_ids:
                    self.logger.error("Ошибка: Массив title_ids пуст.")
                    return

                # Проход по массиву title_ids
                for title_id in title_ids:
                    # Проверяем, существует ли title_id в таблице Title
                    existing_title = session.query(Title).filter_by(title_id=title_id).first()
                    if not existing_title:
                        self.logger.error(f"Ошибка: title_id '{title_id}' не найден в таблице Title.")
                        continue

                    # Проверяем, существует ли уже запись студии для этого title_id
                    existing_studio = session.query(ProductionStudio).filter_by(title_id=title_id).first()
                    if existing_studio:
                        self.logger.error(f"Ошибка: Студия для title_id '{title_id}' уже существует.")
                        continue

                    # Создаем новую студию и сохраняем в базу данных
                    new_studio = ProductionStudio(title_id=title_id, name=studio_name)
                    session.add(new_studio)
                    self.logger.debug(f"Новая студия добавлена: {studio_name} для title_id: {title_id}")

                # Коммитим все изменения
                session.commit()

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при добавлении студии в базу данных: {e}")


