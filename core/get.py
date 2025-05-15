# get.py
import json
import logging
import sqlalchemy

from sqlalchemy import or_, and_
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import sessionmaker, joinedload
from core.tables import Title, Schedule, History, Rating, FranchiseRelease, Franchise, Poster, Torrent, \
    TitleGenreRelation, \
    Template, Genre, TitleTeamRelation, TeamMember


class GetManager:
    def __init__(self, engine):
        self.logger = logging.getLogger(__name__)
        self.Session = sessionmaker(bind=engine)()

    def get_titles_for_day(self, day_of_week):
        """Загружает тайтлы для указанного дня недели из базы данных."""
        with self.Session as session:
            try:
                return session.query(Title).join(Schedule).filter(Schedule.day_of_week == day_of_week).all()

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при получении тайтлов для дня недели: {e}")
                return None

    def get_history_status(self, user_id, title_id, episode_id=None, torrent_id=None):
        with self.Session as session:
            try:
                history_status = session.query(History).filter_by(user_id=user_id, title_id=title_id, episode_id=episode_id, torrent_id=torrent_id).one_or_none()
                if history_status:
                    self.logger.debug(f"user_id: {user_id} Watch status: {history_status.is_watched} for title_id: {title_id}, episode_id: {episode_id}, torrent_id: {torrent_id}")
                    # days_ago = (datetime.utcnow() - history_status.last_watched_at).days if history_status.last_watched_at else 0
                    return history_status.is_watched, history_status.is_download
                return False, False

            except NoResultFound:
                self.logger.debug(
                    f"No history found for user_id: {user_id}, title_id: {title_id}, episode_id: {episode_id}, torrent_id: {torrent_id}")
                return False, False
            except Exception as e:
                self.logger.error(f"Error fetching watch status for user_id {user_id}, title_id {title_id}, episode_id {episode_id}: {e}")
                raise

    def get_need_to_see(self, user_id, title_id):
        with self.Session as session:
            try:
                # Получение записей для данного title_id, где need_to_see=True
                need_to_see_statuses = session.query(History).filter(
                    History.user_id == user_id,
                    History.title_id == title_id,
                    History.need_to_see == True
                ).all()

                # Возвращаем список найденных эпизодов с флагом need_to_see
                self.logger.debug(
                    f"Fetched need_to_see statuses for title_id: {title_id}, count: {len(need_to_see_statuses)}")
                return need_to_see_statuses
            except Exception as e:
                self.logger.error(f"Error fetching need_to_see for title_id {title_id}: {e}")
                raise

    def get_all_episodes_watched_status(self, user_id, title_id):
        with self.Session as session:
            try:
                query = session.query(History).filter(
                    History.user_id == user_id,
                    History.title_id == title_id
                )

                query = query.filter(History.episode_id != None)
                history_statuses = query.all()

                if not history_statuses:
                    return False

                all_watched = all(status.is_watched for status in history_statuses)

                return all_watched

            except Exception as e:
                self.logger.error(f"Error fetching watch status for user_id {user_id}, title_id {title_id}: {e}")
                raise

    def get_rating_from_db(self, title_id):
        with self.Session as session:
            try:
                ratings = session.query(Rating).filter_by(title_id=title_id).one_or_none()
                if ratings:
                    self.logger.debug(f"Rating '{ratings.rating_value}' for title_id: {ratings.title_id}")
                    return ratings
                self.logger.warning(f"No ratings found for title_id: {title_id}.")
                return None
            except Exception as e:
                self.logger.error(f"Error fetching rating for title_id {title_id}: {e}")
                raise

    def get_statistics_from_db(self):
        """Получает статистику из базы данных."""
        with self.Session as session:
            try:
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
                    'schedules_count': "SELECT COUNT(DISTINCT title_id) FROM schedule",
                    'history_count': "SELECT COUNT(DISTINCT id) FROM history",
                    'history_total_count': "SELECT COUNT(*) AS total_count FROM history",
                    'history_total_watch_changes': "SELECT SUM(watch_change_count) AS total_watch_changes FROM history",
                    'history_total_download_changes': "SELECT SUM(download_change_count) AS total_download_changes FROM history",
                    'need_to_see_count': "SELECT COUNT(*) AS need_to_see_count FROM history WHERE need_to_see = TRUE",
                    'torrents_count': "SELECT COUNT(DISTINCT torrent_id) FROM torrents",
                    'genres_count': """
                        SELECT COUNT(DISTINCT g.genre_id)
                        FROM genres g
                        LEFT JOIN title_genre_relation tgr ON g.genre_id = tgr.genre_id
                    """
                }

                statistics = {}
                for key, query in queries.items():
                    result = session.execute(sqlalchemy.text(query)).scalar()
                    statistics[key] = result

                return statistics

            except Exception as e:
                self.logger.error(f"Ошибка при получении статистики из базы данных: {e}")
                return {}

    def get_poster_link(self, title_id):
        with self.Session as session:
            try:
                self.logger.debug(f"Processing poster link for title_id: {title_id}")
                poster_link = session.query(Title.poster_path_original).filter(Title.title_id == title_id).scalar()

                if poster_link:
                    self.logger.debug(f"Poster link found for title_id: {title_id}, link: {poster_link}")
                    return poster_link

                self.logger.warning(f"No poster link found for title_id: {title_id}")
                return None

            except Exception as e:
                self.logger.error(f"Error fetching poster from database: {e}")
                return None

    def get_poster_blob(self, title_id):
        """
        Retrieves the poster blob for a given title_id.
        If check_exists_only is True, returns a boolean indicating whether the poster exists.
        """
        with self.Session as session:
            try:
                poster = session.query(Poster).filter_by(title_id=title_id).first()
                if poster:
                    # TODO: remove unused logic
                    if title_id in [3, 4, 5, 6, 7, 8, 9, 10, 11]:
                        # No need log message for rating stars images
                        # 3, 4 : rating images
                        # 5, 6 : watch images
                        # 7 : reload image
                        # 8, 9 : download image
                        # 10, 11 : need to see image
                        return poster.poster_blob, False
                    else:
                        self.logger.debug(f"Poster image was found in database. title_id: {title_id}")
                        return poster.poster_blob, False

                placeholder_poster = session.query(Poster).filter_by(title_id=2).first()
                if placeholder_poster:
                    self.logger.debug(
                    f"Poster image was not found in database for title_id: {title_id}. Using placeholder.")
                    return placeholder_poster.poster_blob, True
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
                self.logger.warning(f"No torrents found for title_id: {title_id}.")
                return None

            except Exception as e:
                self.logger.error(f"Error fetching torrent data from database: {e}")
                return None

    def get_genres_from_db(self, title_id):
        with self.Session as session:
            try:
                relations = session.query(TitleGenreRelation).filter_by(title_id=title_id).all()
                genres = [relation.genre.name for relation in relations]
                if genres:
                    self.logger.debug(f"Genres were found in database for title_id: {title_id}")
                    return genres
                self.logger.warning(f"No genres found for title_id: {title_id}.")
                return None
            except Exception as e:
                self.logger.error(f"Ошибка при загрузке Genres из базы данных: {e}")
                return None

    def get_team_from_db(self, title_id):
        with self.Session as session:
            try:
                relations = session.query(TitleTeamRelation).filter_by(title_id=title_id).all()
                team_data = {
                    'voice': [],
                    'translator': [],
                    'timing': []
                }

                for relation in relations:
                    role = relation.team_member.role.lower()
                    name = relation.team_member.name

                    if 'voice' in role:
                        team_data['voice'].append(name)
                    elif 'translator' in role:
                        team_data['translator'].append(name)
                    elif 'timing' in role:
                        team_data['timing'].append(name)

                team_data = {
                    'voice': json.dumps(team_data['voice']),
                    'translator': json.dumps(team_data['translator']),
                    'timing': json.dumps(team_data['timing'])
                }

                if any(team_data.values()):
                    self.logger.debug(f"Team data were found in database for title_id: {title_id}")
                    return team_data

                return None

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке данных о команде из базы данных: {e}")
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
                if all(kw.isdigit() for kw in keywords):
                    title_ids = [int(kw) for kw in keywords]
                    query = session.query(Title).filter(Title.title_id.in_(title_ids))
                    titles = query.all()
                else:
                    # Build dynamic filter using SQLAlchemy's 'or_' to match any keyword in any column
                    keyword_filters = [
                        or_(
                            Title.code.ilike(f"%{keyword}%"),
                            Title.name_ru.ilike(f"%{keyword}%"),
                            Title.name_en.ilike(f"%{keyword}%"),
                            Title.alternative_name.ilike(f"%{keyword}%")
                        )
                        for keyword in keywords
                    ]
                    # Combine filters using 'and_' so that all keywords must match (across any field)
                    query = session.query(Title).filter(and_(*keyword_filters))
                    self.logger.info(f"keywords find in DB")
                    titles = query.all()

                title_ids = [title.title_id for title in titles]
                return title_ids

            except Exception as e:
                self.logger.error(f"Error during title search: {e}")
                return []

    def get_template(self, name=None):
        """
        Загружает темплейт из базы данных по имени.
        """
        if name is None:
            name = 'default'
        with self.Session as session:
            try:
                template = session.query(Template).filter_by(name=name).first()
                if template:
                    self.logger.info(f"Template '{name}' loaded successfully.")
                    return template.titles_html, template.one_title_html, template.text_list_html, template.styles_css
                else:
                    self.logger.warning(f"Template '{name}' not found.")
                    return None, None, None, None

            except Exception as e:
                self.logger.error(f"Error loading template '{name}': {e}")
                return None, None, None, None

    def get_available_templates(self):
        """
        Возвращает список доступных шаблонов из базы данных.
        """
        with self.Session as session:
            try:
                templates = session.query(Template.name).all()
                return [t[0] for t in templates]

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке списка шаблонов: {e}")
                return []

    def get_franchises_from_db(self, batch_size=None, offset=0, title_id=None):
        """Получает все тайтлы вместе с информацией о франшизах."""
        with self.Session as session:
            try:
                if title_id:
                    franchise_subquery = session.query(FranchiseRelease.franchise_id).filter(
                        FranchiseRelease.title_id == title_id
                    ).scalar_subquery()

                    query = session.query(Title).join(FranchiseRelease).join(Franchise).filter(
                        FranchiseRelease.franchise_id == franchise_subquery,
                        FranchiseRelease.franchise_id.isnot(None)
                    )
                else:
                    query = session.query(Title).join(FranchiseRelease).join(Franchise).filter(
                        FranchiseRelease.franchise_id.isnot(None)
                    )

                total_count = query.count()
                if offset >= total_count:
                    offset = 0

                if batch_size:
                    query = query.offset(offset).limit(batch_size)

                titles = query.options(joinedload(Title.franchises).joinedload(FranchiseRelease.franchise)).all()
                return titles

            except Exception as e:
                self.logger.error(f"Ошибка при получении тайтлов с франшизами: {e}")
                return []

    def get_need_to_see_from_db(self, batch_size=None, offset=0, title_id=None):
        """Need to see Titles without episodes"""
        with self.Session as session:
            try:
                query = session.query(Title).join(History, Title.title_id == History.title_id)

                if title_id:
                    query = query.filter(History.title_id == title_id, History.need_to_see == True)
                else:
                    query = query.filter(History.need_to_see == True)

                total_count = query.count()
                if offset >= total_count:
                    offset = 0

                if batch_size:
                    query = query.offset(offset).limit(batch_size)

                titles = query.all()
                return titles

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке тайтлов из базы данных: {e}")
                return []

    def get_titles_list_from_db(self, title_ids=None, batch_size=None, offset=0):
        """Titles without episodes"""
        with self.Session as session:
            try:
                query = session.query(Title)
                if title_ids:
                    query = query.filter(Title.title_id.in_(title_ids))
                else:
                    if batch_size:
                        query = query.offset(offset).limit(batch_size)

                titles = query.all()
                return titles

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке тайтлов из базы данных: {e}")
                return []

    def get_total_titles_count(self, show_mode=None):
        """Возвращает общее количество тайтлов с учетом фильтров."""
        query_strategies = {
            'titles_list': lambda session: session.query(Title),
            'franchise_list': lambda session: session.query(Title).join(FranchiseRelease).join(Franchise).filter(
                FranchiseRelease.franchise_id.isnot(None)
            ),
            'need_to_see_list': lambda session: session.query(Title).join(History).filter(History.need_to_see == True)
        }

        with self.Session as session:
            try:
                query_strategy = query_strategies.get(show_mode)

                if query_strategy:
                    query = query_strategy(session)
                else:
                    query = session.query(Title)

                count = query.count()
                self.logger.debug(f"Total titles count: {count}")
                return count

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке тайтлов из базы данных: {e}")
                return 0

    def get_titles_from_db(self, show_all=False, day_of_week=None, batch_size=None, title_id=None, title_ids=None, offset=0):
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
                query = session.query(Title).options(
                    joinedload(Title.genres).joinedload(TitleGenreRelation.genre),
                    joinedload(Title.episodes)
                )

                if title_id:
                    query = query.filter(Title.title_id == title_id)
                elif title_ids:
                    query = query.filter(Title.title_id.in_(title_ids))
                elif not show_all:
                    query = query.join(Schedule).filter(Schedule.day_of_week == day_of_week)
                if batch_size:
                    query = query.offset(offset).limit(batch_size)

                titles = query.all()
                for title in titles:
                    genre_data = [(relation.genre.name, relation.genre.genre_id)
                                  for relation in title.genres if relation.genre]
                    if genre_data:
                        title.genre_names, title.genre_ids = zip(*genre_data)
                    else:
                        title.genre_names = []
                        title.genre_ids = []

                    # Add day of week
                    if not show_all and day_of_week:
                        title.day_of_week = day_of_week
                    else:
                        schedule = session.query(Schedule).filter(Schedule.title_id == title.title_id).first()
                        title.day_of_week = schedule.day_of_week if schedule else None

                return titles

            except Exception as e:
                self.logger.error(f"Ошибка при загрузке тайтлов из базы данных: {e}")
                return []

    def get_titles_by_year(self, year):
        """Получает список title_id по году выпуска."""
        with self.Session as session:
            try:
                query = session.query(Title).filter(Title.season_year == year)
                titles = query.all()
                title_ids = [title.title_id for title in titles]
                return title_ids

            except Exception as e:
                self.logger.error(f"Ошибка при поиске тайтлов по year {year}: {e}")
                return []

    def get_titles_by_status(self, status_code):
        """Получает список title_id по году выпуска."""
        with self.Session as session:
            try:
                query = session.query(Title).filter(Title.status_code == status_code)
                titles = query.all()
                title_ids = [title.title_id for title in titles]
                return title_ids

            except Exception as e:
                self.logger.error(f"Ошибка при поиске тайтлов по status {status_code}: {e}")
                return []

    def get_titles_by_genre(self, genre_id):
        """Получает список title_id, связанных с указанным жанром по его ID."""
        with self.Session as session:
            try:
                title_relations = session.query(TitleGenreRelation).filter_by(genre_id=genre_id).all()
                title_ids = [relation.title_id for relation in title_relations]
                self.logger.info(f"Найдено {len(title_ids)} тайтлов с genre_id: {genre_id}")
                return title_ids

            except Exception as e:
                self.logger.error(f"Ошибка при поиске тайтлов по genre_id {genre_id}: {e}")
                return []

    def get_titles_by_team_member(self, team_member):
        """Получает список title_id, связанных с указанным team_member по его имени."""
        with self.Session as session:
            try:
                team_member_obj = session.query(TeamMember).filter_by(name=team_member).first()
                if not team_member_obj:
                    self.logger.warning(f"team_member: '{team_member}' не найден в базе данных.")
                    return []
                team_member_id = team_member_obj.id
                title_relations = session.query(TitleTeamRelation).filter_by(team_member_id=team_member_id).all()
                title_ids = [relation.title_id for relation in title_relations]
                self.logger.info(
                    f"Найдено {len(title_ids)} тайтлов с team_member_id: {team_member_id} team_member: {team_member}")
                return title_ids

            except Exception as e:
                self.logger.error(f"Ошибка при поиске тайтлов по team_member: {team_member}: {e}")
                return []