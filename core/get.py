# get.py
import json
import logging
import sqlalchemy

from sqlalchemy import or_, and_
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import sessionmaker, joinedload
from core.tables import Title, Schedule, History, Rating, FranchiseRelease, Franchise, Poster, Torrent, \
    TitleGenreRelation, \
    Template, Genre, TitleTeamRelation, TeamMember, TitleProviderMap, Provider, ProductionStudio


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
                poster = session.query(Poster).filter_by(title_id=title_id) \
                    .order_by(Poster.last_updated.desc()).first()
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

    def get_poster_last_updated(self, title_id):
        """
        Получает дату последнего обновления постера для указанного title_id.

        Args:
            title_id: ID тайтла

        Returns:
            datetime: Дата последнего обновления или None, если постер не найден
        """
        with self.Session as session:
            try:
                poster = session.query(Poster).filter_by(title_id=title_id).order_by(Poster.last_updated.desc()).first()
                if poster:
                    return poster.last_updated
                return None
            except Exception as e:
                self.logger.error(f"Ошибка при получении даты обновления постера: {e}")
                return None

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
                    self.logger.debug(f"Template '{name}' loaded successfully.")
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
            'need_to_see_list': lambda session: session.query(Title).join(History).filter(History.need_to_see == True),
            'ongoing_list': lambda session: session.query(Title).filter(Title.status_code.in_([1, 3])),
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
                    joinedload(Title.episodes),
                    joinedload(Title.schedules).joinedload(Schedule.day),  # <-- сразу тянем day
                )

                # Фильтры по ID/списку ID
                if title_id:
                    query = query.filter(Title.title_id == title_id)
                elif title_ids:
                    query = query.filter(Title.title_id.in_(title_ids))
                # Фильтр по дню недели (1..7) только если не show_all
                elif not show_all:
                    try:
                        wd = int(day_of_week)
                    except (TypeError, ValueError):
                        return []  # некорректный фильтр — пусто
                    if not (1 <= wd <= 7):
                        return []
                    query = query.join(Schedule).filter(Schedule.day_of_week == wd)

                if batch_size:
                    query = query.offset(offset).limit(batch_size)

                titles = query.all()

                for t in titles:
                    # жанры
                    genre_data = [(rel.genre.name, rel.genre.genre_id) for rel in t.genres if rel.genre]
                    t.genre_names, t.genre_ids = (zip(*genre_data) if genre_data else ([], []))

                    # расписание → день недели
                    if not show_all and day_of_week:
                        # при фильтре ставим выбранный wd, имя берём из подходящего Schedule (если есть)
                        s = next((sc for sc in t.schedules if sc.day_of_week == wd),
                                 t.schedules[0] if t.schedules else None)
                        t.day_of_week = wd
                    else:
                        s = t.schedules[0] if t.schedules else None
                        t.day_of_week = s.day_of_week if s else None

                    t.day_name = (s.day.day_name if s and s.day else None)

                return titles
            except Exception as e:
                self.logger.error(f"DB error in get_titles_from_db: {e}")
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
        """Получает список title_id по status_code."""
        with self.Session as session:
            try:
                query = session.query(Title).filter(Title.status_code == status_code)
                titles = query.all()
                title_ids = [title.title_id for title in titles]
                return title_ids

            except Exception as e:
                self.logger.error(f"Ошибка при поиске тайтлов по status {status_code}: {e}")
                return []

    def get_ongoing_titles(self, batch_size=None, offset=0):
        """Получает список ongoing titles."""
        with self.Session as session:
            try:
                query = session.query(Title).filter(Title.status_code.in_([1, 3]))
                if batch_size:
                    query = query.offset(offset).limit(batch_size)
                titles = query.all()

                return titles

            except Exception as e:
                self.logger.error(f"Ошибка при поиске тайтлов по status 1, 3: {e}")
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

    def get_titles_by_keywords(self, search_string: str):
        """Search for titles by keywords in code, name_ru, name_en, alternative_name, or by title_id, and returns a list of title_ids."""
        keywords = [kw.strip() for kw in search_string.split(',') if kw.strip()]
        if not keywords:
            return [], []

        self.logger.debug(f"keyword for processing: {keywords}")

        with self.Session as session:
            try:
                # базовый query с нужными joinedload
                base_query = session.query(Title).options(
                    joinedload(Title.provider_links)
                    .joinedload(TitleProviderMap.provider)
                )

                if all(kw.isdigit() for kw in keywords):
                    # Ищем по ВНУТРЕННИМ title_id
                    title_ids_input = [int(kw) for kw in keywords]
                    query = base_query.filter(Title.title_id.in_(title_ids_input))
                    titles = query.all()
                else:
                    keyword_filters = [
                        or_(
                            Title.code.ilike(f"%{keyword}%"),
                            Title.name_ru.ilike(f"%{keyword}%"),
                            Title.name_en.ilike(f"%{keyword}%"),
                            Title.alternative_name.ilike(f"%{keyword}%"),
                        )
                        for keyword in keywords
                    ]

                    query = base_query.filter(and_(*keyword_filters))
                    titles = query.all()

                title_ids = [t.title_id for t in titles]
                self.logger.info(f"keywords: {keywords} find in DB. tile_ids: {title_ids}")

                providers = []
                for t in titles:
                    if t.provider_links:
                        providers.append(t.provider_links[0].provider.code)
                    else:
                        providers.append(getattr(t, "provider", None))
                self.logger.info(f"providers: {providers} find in DB. tile_ids: {title_ids}")

                return title_ids, providers

            except Exception as e:
                self.logger.error(f"Error during title search: {e}")
                return [], []

    def get_titles_search_query(self, query) -> list[dict]:
        """
        Универсальный метод:
          - если query = "123,456" или [123, 456] → ищем по title_id
          - если query = "naruto" или "death note" → ищем по ключевым словам
        Возвращает список:
        [
            {
                "title_id": ...,
                "name_ru": ...,
                "name_en": ...,
                "providers": [
                    {"provider": "animedia", "external_id": "777"},
                    {"provider": "shikimori", "external_id": "999"},
                ],
            },
            ...
        ]
        """

        # --- 1. Нормализуем ввод ---
        title_ids: list[int] = []
        search_text: str | None = None

        # если int / список → считаем, что это title_id
        if isinstance(query, int):
            title_ids = [query]
        elif isinstance(query, (list, tuple)):
            # список - может быть смешанный (str/int)
            for x in query:
                if isinstance(x, int):
                    title_ids.append(x)
                elif isinstance(x, str) and x.strip().isdigit():
                    title_ids.append(int(x.strip()))
            # если список был, но туда ничего не попало — вернём пустой результат
            if not title_ids and query:
                return []
        elif isinstance(query, str):
            stripped = query.strip()
            if not stripped:
                return []

            # строка - либо это CSV чисел, либо ключевые слова
            parts = [p.strip() for p in stripped.split(",") if p.strip()]
            if parts and all(p.isdigit() for p in parts):
                title_ids = [int(p) for p in parts]
            else:
                search_text = stripped
        else:
            raise ValueError(f"Unsupported query type: {type(query)}")

        with self.Session as session:
            # --- 2А. Поиск по title_id, если есть ---
            if title_ids:
                titles = (
                    session.query(Title)
                    .options(
                        joinedload(Title.provider_links)
                        .joinedload(TitleProviderMap.provider)
                    )
                    .filter(Title.title_id.in_(title_ids))
                    .all()
                )
            # --- 2Б. Поиск по ключевым словам ---
            elif search_text is not None:
                keywords = [kw.strip() for kw in search_text.split(",") if kw.strip()]
                if not keywords:
                    return []

                keyword_filters = [
                    or_(
                        Title.code.ilike(f"%{kw}%"),
                        Title.name_ru.ilike(f"%{kw}%"),
                        Title.name_en.ilike(f"%{kw}%"),
                        Title.alternative_name.ilike(f"%{kw}%"),
                    )
                    for kw in keywords
                ]

                titles = (
                    session.query(Title)
                    .options(
                        joinedload(Title.provider_links)
                        .joinedload(TitleProviderMap.provider)
                    )
                    .filter(and_(*keyword_filters))
                    .all()
                )
            else:
                return []

            # --- 3. Формируем ответ ---
            result: list[dict] = []

            for t in titles:
                providers_info: list[dict] = []
                for link in t.provider_links:
                    if not link.provider:
                        continue
                    providers_info.append({
                        "provider": link.provider.code,
                        "name": link.provider.name,
                        "external_id": link.external_title_id,
                    })

                result.append({
                    "title_id": t.title_id,
                    "name_ru": t.name_ru,
                    "name_en": t.name_en,
                    "providers": providers_info,
                })

            return result

    def get_title_by_external_id(self, provider_code: str, external_id: int | str):
        with self.Session as session:
            external_id_str = str(external_id)
            title = (
                session.query(Title)
                .join(TitleProviderMap, Title.title_id == TitleProviderMap.title_id)
                .join(Provider, Provider.provider_id == TitleProviderMap.provider_id)
                .filter(
                    Provider.code == provider_code,
                    TitleProviderMap.external_title_id == external_id_str,
                )
                .one_or_none()
            )
            return title

    def get_title_ids_by_provider(self, provider_code: str) -> list[int]:
        with self.Session as session:
            rows = (
                session.query(TitleProviderMap.title_id)
                .join(Provider)
                .filter(Provider.code == provider_code)
                .all()
            )
        return [r[0] for r in rows]

    def get_provider_by_title_id(self, title_id: int) -> str | None:
        """Возвращает имя провайдера (code) для данного title_id.
           Если провайдеров несколько — возвращает первый.
        """
        with self.Session as session:
            link = (
                session.query(TitleProviderMap)
                .options(joinedload(TitleProviderMap.provider))
                .filter(TitleProviderMap.title_id == title_id)
                .first()
            )

            if not link or not link.provider:
                return None

            return link.provider.name

    def get_studio_by_title_id(self, title_id: int) -> str | None:
        """Возвращает название студии по title_id, либо None, если студии нет."""
        with self.Session as session:
            studio = (
                session.query(ProductionStudio)
                .filter(ProductionStudio.title_id == title_id)
                .one_or_none()
            )

            if studio is None:
                return None

            return studio.name