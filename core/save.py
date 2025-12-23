# save.py
import ast
import json
import logging
import re
import uuid

from typing import Optional
from sqlalchemy import or_, and_, nullslast, select, func, update, delete, Integer, case, exists
from datetime import datetime, timezone
from sqlalchemy.orm import sessionmaker, aliased
from core.tables import Title, Schedule, History, Rating, FranchiseRelease, Franchise, Poster, Torrent, \
    TitleGenreRelation, \
    Template, Genre, TeamMember, TitleTeamRelation, Episode, ProductionStudio, Provider, TitleProviderMap


class SaveManager:
    def __init__(self, engine):
        self.logger = logging.getLogger(__name__)
        self.Session = sessionmaker(bind=engine)()

    def save_poster(self, title_id, poster_blob, hash_value=None):
        with self.Session as session:
            try:
                current_time = datetime.now(timezone.utc)

                if hash_value:
                    existing_poster = session.query(Poster).filter_by(
                        title_id=title_id,
                        hash_value=hash_value
                    ).first()

                    if existing_poster:
                        existing_poster.last_updated = current_time
                        self.logger.debug(
                            f"Poster already exists with same hash. Updated timestamp. title_id: {title_id}")
                        session.commit()
                        return

                new_poster = Poster(
                    title_id=title_id,
                    poster_blob=poster_blob,
                    hash_value=hash_value,
                    last_updated=current_time
                )
                session.add(new_poster)
                self.logger.debug(f"New poster version saved to database. title_id: {title_id}")

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
                    existing_status.last_watched_at = datetime.now(timezone.utc)
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
                        last_watched_at=datetime.now(timezone.utc) if is_watched else None,
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

    def save_watch_status(self, user_id, title_id, episode_id=None, is_watched=False, torrent_id=None,
                          is_download=False):
        with self.Session as session:
            try:
                filters = {'user_id': user_id, 'title_id': title_id}
                if episode_id is not None:
                    filters['episode_id'] = episode_id
                elif torrent_id is not None:
                    filters['torrent_id'] = torrent_id
                else:
                    filters['episode_id'] = None
                    filters['torrent_id'] = None

                existing_status = session.query(History).filter_by(**filters).one_or_none()
                now = datetime.now(timezone.utc)

                if existing_status:
                    if episode_id is not None:
                        existing_status.previous_watched_at = existing_status.last_watched_at
                        existing_status.is_watched = is_watched
                        existing_status.last_watched_at = now
                        existing_status.watch_change_count += 1
                    elif torrent_id is not None:
                        existing_status.previous_download_at = existing_status.last_download_at
                        existing_status.is_download = is_download
                        existing_status.last_download_at = now
                        existing_status.download_change_count += 1
                    else:
                        # title-level
                        existing_status.previous_watched_at = existing_status.last_watched_at
                        existing_status.is_watched = is_watched
                        existing_status.last_watched_at = now
                        existing_status.watch_change_count += 1

                else:
                    is_episode = episode_id is not None
                    is_torrent = torrent_id is not None
                    is_title_level = (not is_episode and not is_torrent)

                    new_add = History(
                        user_id=user_id,
                        title_id=title_id,
                        episode_id=episode_id if is_episode else None,
                        torrent_id=torrent_id if is_torrent else None,

                        # ВАЖНО: title-level тоже должен сохранять is_watched
                        is_watched=is_watched if (is_episode or is_title_level) else False,
                        last_watched_at=now if (is_episode or is_title_level) else None,
                        watch_change_count=1 if (is_episode or is_title_level) else 0,

                        is_download=is_download if is_torrent else False,
                        last_download_at=now if is_torrent else None,
                        download_change_count=1 if is_torrent else 0,
                    )

                    session.add(new_add)

                session.commit()

            except Exception as e:
                session.rollback()
                self.logger.error(
                    f"Error saving watch status for user_id {user_id}, title_id {title_id}, episode_id {episode_id}: {e}"
                )
                raise

    @staticmethod
    def _map_external_to_cmers(value: float, *, max_cmers: int = 6, max_external: float = 10.0) -> int:
        """
        Приводит произвольный внешний рейтинг к шкале CMERS (0‑max_cmers).
        - Обрезаем значение, если оно выше max_external.
        - Делим на max_external, получаем долю от 0 до 1.
        - Умножаем на max_cmers и округляем до ближайшего целого.
        """
        value = min(value, max_external)          # обрезка
        fraction = value / max_external            # доля от 0 до 1
        return int(round(fraction * max_cmers))    # перевод в шкалу CMERS

    def _upsert_rating(
        self,
        *,
        title_id: int,
        rating_name: Optional[str] = None,
        rating_value: Optional[int] = None,
        name_external: Optional[str] = None,
        score_external: Optional[float] = None,
    ) -> None:
        """
        Создаёт или обновляет запись.
        * Если `rating_name == "CMERS"` → сохраняем внутренний рейтинг.
        * Иначе → сохраняем внешний рейтинг (`rating_name` – источник, `external_name` – подпись).
        """
        with self.Session as session:
            try:
                query = session.query(Rating).filter_by(title_id=title_id)
                if rating_name and rating_name != "CMERS":
                    query = query.filter_by(rating_name=rating_name)

                rating = query.one_or_none()
                if rating is None:
                    rating = Rating(
                        title_id=title_id,
                        rating_name=rating_name,
                        rating_value=rating_value,
                        name_external=name_external,
                        score_external=score_external,
                        last_updated=datetime.now(timezone.utc),
                    )
                    session.add(rating)
                    self.logger.debug(
                        f"Inserted rating title_id={title_id} source={rating_name}"
                    )
                else:
                    if rating_value is not None:
                        rating.rating_value = rating_value
                    if score_external is not None:
                        rating.score_external = score_external
                    if name_external is not None:
                        rating.name_external = name_external
                    rating.last_updated = datetime.now(timezone.utc)
                    self.logger.debug(
                        f"Updated rating title_id={title_id} source={rating_name}"
                    )

                session.commit()
            except Exception as exc:
                session.rollback()
                self.logger.error(
                    f"Error saving rating title_id={title_id}: {exc}"
                )
                raise

    def save_ratings(
        self,
        title_id: int,
        rating_name: str = "CMERS",
        rating_value: Optional[int] = None,
        name_external: Optional[str] = None,
        score_external: Optional[float] = None,
    ) -> None:
        """
        Принимает:
        * `rating_name` – имя источника (для CMERS обычно «CMERS»).
        * `rating_value` – готовый внутренний рейтинг (0‑6).
        * `external_name` – произвольное название внешнего рейтинга (например, «IMDb»).
        * `external_value` – оригинальное внешнее значение (например, 8.3).

        Логика:
        1. Если передан `external_value` → конвертируем в CMERS.
        2. Если `external_value` отсутствует, но есть `rating_value` → используем его.
        3. Если ни то, ни другое – бросаем ошибку.
        """
        if score_external is not None:
            cmers = self._map_external_to_cmers(
                score_external, max_cmers=6, max_external=10.0
            )
        elif rating_value is not None:
            if not 0 <= rating_value <= 6:
                raise ValueError("CMERS rating must be between 0 and 6")
            cmers = rating_value
        else:
            raise ValueError(
                "Either external_value or rating_value must be provided"
            )
        self._upsert_rating(
            title_id=title_id,
            rating_name=rating_name,
            rating_value=cmers,
            name_external=name_external,
            score_external=score_external,
        )

    @staticmethod
    def normalize_provider_code(raw: str) -> str:
        return (
            raw.strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

    def save_title(self, provider_code: str, external_id: int | str, title_fields: dict) -> int:
        """
        Сохраняет тайтл и связь (provider, external_id -> title_id).
        Возвращает внутренний title_id.
        """
        with self.Session as session:
            try:
                # Convert timestamps if they exist
                if 'updated' in title_fields:
                    title_fields['updated'] = datetime.fromtimestamp(title_fields['updated'], tz=timezone.utc)
                if 'last_change' in title_fields:
                    title_fields['last_change'] = datetime.fromtimestamp(title_fields['last_change'], tz=timezone.utc)
                external_id_str = str(external_id)
                provider_code = self.normalize_provider_code(provider_code)

                # 1. находим/создаём провайдера
                provider = (
                    session.query(Provider)
                    .filter_by(code=provider_code)
                    .one_or_none()
                )
                if provider is None:
                    provider = Provider(code=provider_code, name=provider_code)
                    session.add(provider)
                    session.flush()  # provider_id

                # 2. ищем маппинг
                link = (
                    session.query(TitleProviderMap)
                    .filter_by(
                        provider_id=provider.provider_id,
                        external_title_id=external_id_str,
                    )
                    .one_or_none()
                )

                if link is not None:
                    # есть существующий title — обновляем
                    title = link.title
                    is_updated = False
                    for key, value in title_fields.items():
                        if hasattr(title, key) and getattr(title, key) != value:
                            setattr(title, key, value)
                            is_updated = True
                    if is_updated:
                        session.commit()
                        self.logger.debug(f"Updated title_id: {title.title_id} for {provider_code}:{external_id}")
                else:
                    # создаём новый title
                    title = Title(**title_fields)
                    session.add(title)
                    session.flush()  # получаем title.title_id

                    link = TitleProviderMap(
                        title_id=title.title_id,
                        provider_id=provider.provider_id,
                        external_title_id=external_id_str,
                    )
                    session.add(link)
                    session.commit()
                    self.logger.debug(f"Created title_id: {title.title_id} for {provider_code}:{external_id}")

                return title.title_id

            except Exception as e:
                session.rollback()
                self.logger.error(f"Error saving title with mapping: {e}")
                raise

    def save_franchise(self, franchise_data):
        with self.Session as session:
            try:
                external_id = franchise_data['external_id']
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
                    existing_franchise.last_updated = datetime.now(timezone.utc)
                    franchise = existing_franchise
                else:
                    # Создание новой франшизы
                    new_franchise = Franchise(
                        title_id=title_id,
                        franchise_id=franchise_id,
                        franchise_name=franchise_name,
                        last_updated=datetime.now(timezone.utc)
                    )
                    session.add(new_franchise)
                    session.flush()  # Получаем ID новой франшизы для использования в релизах
                    franchise = new_franchise

                current = None
                for fr in franchise_data.get("franchise_releases", []):
                    if fr.get("release_id") == external_id:
                        current = fr
                        break

                # если не нашли — либо выходим, либо сохраняем только Franchise без релизов
                if not current:
                    session.commit()
                    return True

                release = current.get("release") or {}
                names = release.get("names") or {}

                existing_release = (
                    session.query(FranchiseRelease)
                    .filter_by(franchise_id=franchise.id, title_id=title_id)
                    .one_or_none()
                )

                if existing_release:
                    r = existing_release
                else:
                    r = FranchiseRelease(franchise_id=franchise.id, title_id=title_id)
                    session.add(r)

                r.ext_fr_id = current.get("franchise_id")
                r.ext_fr_rel_id = current.get("franchise_release_id")
                r.ext_rel_id = current.get("release_id")
                r.code = release.get("code")
                r.ordinal = current.get("ordinal")
                r.name_ru = names.get("ru")
                r.name_en = names.get("en")
                r.name_alternative = names.get("alternative")
                r.last_updated = datetime.now(timezone.utc)

                session.commit()
                self.logger.debug(f"Successfully saved franchise for title_id: {title_id}")
                return True

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
                        new_genre = Genre(name=genre, last_updated=datetime.now(timezone.utc))
                        session.add(new_genre)
                        session.commit()  # Коммитим, чтобы получить genre_id для следующего этапа
                        genre_id = new_genre.genre_id
                    else:
                        genre_id = existing_genre.genre_id

                    # Добавляем связь в таблицу TitleGenreRelation
                    existing_relation = session.query(TitleGenreRelation).filter_by(title_id=title_id,
                                                                                    genre_id=genre_id).first()
                    if not existing_relation:
                        new_relation = TitleGenreRelation(title_id=title_id, genre_id=genre_id, last_updated=datetime.now(timezone.utc))
                        session.add(new_relation)

                session.commit()
                self.logger.debug(f"Successfully saved genres for title_id: {title_id}")

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении жанров для title_id {title_id}: {e}")

    def save_team_members(self, title_id, team_data):
        with self.Session as session:
            try:
                # Сначала получим все существующие связи для этого тайтла
                existing_relations = session.query(TitleTeamRelation).filter_by(title_id=title_id).all()

                # Создадим словарь для быстрого поиска существующих связей
                existing_relations_dict = {relation.team_member_id: relation for relation in existing_relations}

                # Список для отслеживания обработанных team_member_id
                processed_team_member_ids = set()

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
                            new_member = TeamMember(name=member_name, role=role, last_updated=datetime.now(timezone.utc))
                            session.add(new_member)
                            session.flush()  # Получаем ID нового участника
                            team_member = new_member
                        else:
                            team_member = existing_member

                        # Добавляем ID в список обработанных
                        processed_team_member_ids.add(team_member.id)

                        # Проверяем, существует ли уже связь между тайтлом и участником
                        if team_member.id in existing_relations_dict:
                            # Обновляем существующую связь
                            relation = existing_relations_dict[team_member.id]
                            relation.last_updated = datetime.now(timezone.utc)
                        else:
                            # Создаем новую связь
                            title_team_relation = TitleTeamRelation(
                                title_id=title_id,
                                team_member_id=team_member.id,
                                last_updated=datetime.now(timezone.utc)
                            )
                            session.add(title_team_relation)

                # Опционально: удаляем связи, которые не были обработаны (члены команды, удаленные из тайтла)
                for relation in existing_relations:
                    if relation.team_member_id not in processed_team_member_ids:
                        session.delete(relation)

                session.commit()
                self.logger.debug(f"Successfully saved team members for title_id: {title_id}")
                return True

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при сохранении участников команды в базе данных: {e}")
                return False

    def save_episode(self, episode_data: dict) -> None:
        """
        Сохраняет эпизод, используя естественный ключ
        (title_id, episode, provider).  Если запись уже есть –
        обновляет только изменённые поля.
        """
        if not isinstance(episode_data, dict):
            self.logger.error(f"Invalid episode data: {episode_data}")
            return

        # копируем, чтобы не менять оригинал
        data = episode_data.copy()

        # обязательные поля для поиска
        title_id = data["title_id"]
        episode_no = data["episode_number"]
        episode_uuid = data["uuid"]

        with self.Session as session:
            try:
                # ищем по естественному ключу, а не по uuid
                ep = (
                    session.query(Episode)
                    .filter_by(title_id=title_id, episode_number=episode_no)
                    .first()
                )

                if not ep:
                    ep = session.query(Episode).filter_by(uuid=episode_uuid).first()

                # ---------- если запись уже есть ----------
                if ep:
                    updated = False
                    protected = {"episode_id", "title_id", "episode"}  # не меняем

                    # корректируем created_timestamp, если он был «нулевым»
                    if (
                            ep.created_timestamp == datetime.fromtimestamp(0, tz=timezone.utc)
                            and data.get("created_timestamp")
                            and data["created_timestamp"] != datetime.fromtimestamp(0, tz=timezone.utc)
                    ):
                        ep.created_timestamp = data["created_timestamp"]
                        updated = True

                    # обновляем остальные поля
                    for key, value in data.items():
                        if key in protected or not hasattr(ep, key):
                            continue

                        cur = getattr(ep, key)

                        # сравнение datetime с учётом tz
                        if isinstance(cur, datetime) and isinstance(value, datetime):
                            if cur.tzinfo is None:
                                cur = cur.replace(tzinfo=timezone.utc)

                        if cur != value:
                            setattr(ep, key, value)
                            updated = True

                    if updated:
                        session.commit()
                        self.logger.debug(
                            f"Updated episode {episode_no} for title_id={title_id}"
                        )
                    else:
                        self.logger.debug(
                            f"No changes for episode {episode_no}"
                        )

                # ---------- если записи нет ----------
                else:
                    # если created_timestamp не задан – ставим «сейчас»
                    if not data.get("created_timestamp"):
                        data["created_timestamp"] = datetime.now(timezone.utc)

                    # uuid генерируем, если его нет (можно оставить из API)
                    data.setdefault("uuid", str(uuid.uuid4()))

                    new_ep = Episode(**data)
                    session.add(new_ep)
                    session.commit()
                    self.logger.debug(
                        f"Inserted new episode {episode_no} for title_id={title_id}"
                    )

            except Exception as exc:
                session.rollback()
                self.logger.error(f"Error saving episode: {exc}")

    def save_schedule(self, day_of_week, title_id, last_updated=None):
        with self.Session as session:
            try:
                # Check if the entry already exists
                existing_schedule = session.query(Schedule).filter_by(day_of_week=day_of_week,
                                                                      title_id=title_id).first()
                if existing_schedule:
                    # If it exists, update the last_updated field
                    existing_schedule.last_updated = last_updated or datetime.now(timezone.utc)
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
        """
        list[dict]: ПОЛНАЯ замена по title_id (доверяем API, атомарно)
        dict:       upsert одной записи + ОБЯЗАТЕЛЬНОЕ удаление покрытых диапазонов,
                    чтобы 1–4 сразу чистил 1–3 даже "в производстве"
        """

        T = Torrent

        # ---------- utils ----------
        def _to_bytes(size_string: str) -> int:
            if not size_string:
                return 0
            s = str(size_string).strip().upper().replace(',', '.')
            try:
                num = float(s.split()[0])
            except Exception:
                return 0
            mult = {'TB': 1024 ** 4, 'GB': 1024 ** 3, 'MB': 1024 ** 2, 'KB': 1024, 'B': 1}
            for u in ('TB', 'GB', 'MB', 'KB', 'B'):
                if u in s:
                    return int(num * mult[u])
            return int(num)

        def _prep_one(p: dict) -> dict:
            q = dict(p)

            # нормализация/преобразования
            if isinstance(q.get('torrent_metadata'), dict):
                q['torrent_metadata'] = json.dumps(q['torrent_metadata'], ensure_ascii=False)

            if not isinstance(q.get('uploaded_timestamp'), datetime):
                q['uploaded_timestamp'] = datetime.now(timezone.utc)

            # total_size
            if q.get('total_size') is None:
                q['total_size'] = _to_bytes(q.get('size_string') or "")
            else:
                try:
                    q['total_size'] = int(q['total_size'])
                except Exception:
                    q['total_size'] = _to_bytes(q.get('size_string') or "")

            # resolution из quality/resolution
            if not q.get('resolution'):
                m = re.search(r'(\d{3,4})p', ((q.get('quality') or '') + ' ' + (q.get('resolution') or '')), re.I)
                if m:
                    q['resolution'] = f"{m.group(1)}p"

            # строковые нормализации (strip+lower где уместно)
            q['resolution'] = (q.get('resolution') or "").strip().lower()
            q['quality'] = (q.get('quality') or "").strip().lower()
            q['encoder'] = (q.get('encoder') or "").strip().lower()

            # episodes_range из description/label при отсутствии
            if not q.get('episodes_range'):
                for source in (q.get('episodes_range'), q.get('description'), q.get('label')):
                    if source:
                        m = re.search(r'(\d+)\s*[-–—]\s*(\d+)', str(source))
                        if m:
                            q['episodes_range'] = f"{m.group(1)}-{m.group(2)}"
                            break

            q['episodes_range'] = (q.get('episodes_range') or "").strip()
            q['label'] = (q.get('label') or "").strip()
            q['filename'] = (q.get('filename') or "").strip()

            # api flags
            q['api_updated_at'] = q.get('api_updated_at') or q.get('updated_at') or datetime.now(timezone.utc)
            q['is_in_production'] = int(bool(q.get('is_in_production')))
            q['episodes_total'] = int(q.get('episodes_total') or 0)

            # range_first/last
            rng = (q.get('episodes_range') or "").strip()
            if rng:
                m = re.search(r'(\d+)\s*[-–—]\s*(\d+)', rng)
                if m:
                    q['range_first'] = int(m.group(1))
                    q['range_last'] = int(m.group(2))
                else:
                    m1 = re.fullmatch(r'\s*(\d+)\s*', rng)
                    if m1:
                        q['range_first'] = q['range_last'] = int(m1.group(1))
                    else:
                        if re.search(r'(фильм|movie|ova|special|ona)', rng, re.I):
                            q['range_first'] = q['range_last'] = 1
                        else:
                            q['range_first'] = q['range_last'] = None
            else:
                q['range_first'] = q['range_last'] = None

            return q

        def _codec_family_sql(expr):
            expr_lc = func.lower(func.trim(func.coalesce(expr, '')))
            return case(
                (expr_lc.like('%av1%'), 'av1'),
                (expr_lc.like('%vp9%'), 'vp9'),
                (expr_lc.like('%265%'), 'h265'),
                (expr_lc.like('%hevc%'), 'h265'),
                (expr_lc.like('%264%'), 'h264'),
                (expr_lc.like('%avc%'), 'h264'),
                else_=expr_lc
            )

        def _norm_res_sql(expr):
            return func.lower(func.trim(func.coalesce(expr, '')))

        # ---------- pruning helpers ----------
        def _prune_covered_ranges(session, title_id: int):
            """Удалить записи, полностью покрытые более широким диапазоном в той же (resolution, codec_family)."""
            A = aliased(T);
            B = aliased(T)
            covered_ids = (
                select(B.torrent_id)
                .where(
                    B.title_id == title_id,
                    exists(
                        select(1).select_from(A).where(and_(
                            A.title_id == B.title_id,
                            _norm_res_sql(A.resolution) == _norm_res_sql(B.resolution),
                            _codec_family_sql(A.encoder) == _codec_family_sql(B.encoder),
                            A.range_first.isnot(None), A.range_last.isnot(None),
                            B.range_first.isnot(None), B.range_last.isnot(None),
                            A.range_first <= B.range_first,
                            A.range_last >= B.range_last,
                            A.torrent_id != B.torrent_id,
                        ))
                    )
                )
            )
            session.execute(
                delete(T)
                .where(T.title_id == title_id)
                .where(T.torrent_id.in_(covered_ids))
            )

        def _prune_triplet(session, title_id: int):
            """Внутри (quality, encoder, episodes_range) оставить лучший (size desc, ts desc, id desc)."""
            subq = (
                select(
                    T.torrent_id.label("tid"),
                    func.row_number().over(
                        partition_by=(
                            func.coalesce(T.quality, ''),
                            func.coalesce(T.encoder, ''),
                            func.coalesce(T.episodes_range, '')
                        ),
                        order_by=(
                            func.coalesce(T.total_size, 0).desc(),
                            func.coalesce(T.uploaded_timestamp, datetime(1970, 1, 1)).desc(),
                            T.torrent_id.desc()
                        )
                    ).label("rn")
                )
                .where(T.title_id == title_id)
                .subquery()
            )
            keep = select(subq.c.tid).where(subq.c.rn == 1)
            session.execute(
                delete(T)
                .where(T.title_id == title_id)
                .where(~T.torrent_id.in_(keep))
            )

        def _prune_res_codec(session, title_id: int):
            """Внутри (resolution_norm, codec_family, episodes_range) оставить лучший."""
            enc_lc = func.lower(func.coalesce(T.encoder, ''))
            codec_family = case(
                (enc_lc.like('%av1%'), 'av1'),
                (enc_lc.like('%vp9%'), 'vp9'),
                (enc_lc.like('%265%'), 'h265'),
                (enc_lc.like('%hevc%'), 'h265'),
                (enc_lc.like('%264%'), 'h264'),
                (enc_lc.like('%avc%'), 'h264'),
                else_=enc_lc
            )
            subq = (
                select(
                    T.torrent_id.label("tid"),
                    func.row_number().over(
                        partition_by=(
                            func.coalesce(T.resolution, ''),
                            codec_family,
                            func.coalesce(T.episodes_range, '')
                        ),
                        order_by=(
                            func.coalesce(T.total_size, 0).desc(),
                            func.coalesce(T.uploaded_timestamp, datetime(1970, 1, 1)).desc(),
                            T.torrent_id.desc()
                        )
                    ).label("rn")
                )
                .where(T.title_id == title_id)
                .subquery()
            )
            keep = select(subq.c.tid).where(subq.c.rn == 1)
            session.execute(
                delete(T)
                .where(T.title_id == title_id)
                .where(~T.torrent_id.in_(keep))
            )

        # ---------- main logic ----------
        # Полная замена по title_id (доверяем API-снэпшоту)
        if isinstance(torrent_data, list):
            if not torrent_data:
                return
            if any(not isinstance(t, dict) for t in torrent_data):
                raise TypeError("save_torrent(list): ожидались dict, нашлись не-dict элементы")

            prepared = [_prep_one(t) for t in torrent_data]
            title_id = prepared[0]['title_id']
            if any(t['title_id'] != title_id for t in prepared):
                raise ValueError("В батче обнаружены разные title_id — replace невозможен")

            # атомарный replace + мягкий дедуп
            with self.Session as session, session.begin():
                session.query(T).filter(T.title_id == title_id).delete(synchronize_session=False)
                session.bulk_save_objects([T(**t) for t in prepared])

                _prune_triplet(session, title_id)
                _prune_covered_ranges(session, title_id)
                _prune_res_codec(session, title_id)

            self.logger.info(f"[replace] title_id={title_id}: inserted {len(prepared)}")
            return

        # Upsert одиночной записи + ОБЯЗАТЕЛЬНАЯ чистка покрытых (даже «в производстве»)
        if isinstance(torrent_data, dict):
            p = _prep_one(torrent_data)
            if p.get('torrent_id') is None:
                raise ValueError("torrent_id обязателен для одиночного save")

            with self.Session as session, session.begin():
                session.merge(T(**p))

            # ВАЖНО: покрытие чистим ВСЕГДА (решает кейс «1–4» накрывает «1–3» немедленно)
            with self.Session as session, session.begin():
                _prune_covered_ranges(session, p['title_id'])
                if not p.get('is_in_production'):
                    _prune_triplet(session, p['title_id'])
                    _prune_res_codec(session, p['title_id'])

            self.logger.debug(
                f"[dict] title={p['title_id']} q='{p.get('quality') or ''}' "
                f"enc='{p.get('encoder') or ''}' rng='{p.get('episodes_range') or ''}' — upsert ok"
            )
            return

        raise TypeError("save_torrent ожидает dict или list[dict]")

    def remove_schedule_day(self, title_ids, day_of_week):
        with self.Session as session:
            try:
                if isinstance(title_ids, set):
                    title_ids = list(title_ids)
                if not title_ids or not isinstance(title_ids, list):
                    raise ValueError(f"Invalid title_ids: {title_ids}")

                self.logger.debug(f"Querying schedules with title_ids: {title_ids} and day_of_week: {day_of_week}")

                all_schedules = session.query(Schedule).all()
                self.logger.debug(f"All schedules in table: {all_schedules}")
                schedules_to_update = (
                    session.query(Schedule)
                    .filter(Schedule.title_id.in_(title_ids), Schedule.day_of_week == day_of_week)
                )
                result = schedules_to_update.all()
                self.logger.debug(f"Filtered schedules: {result}")
                if result:
                    deleted_count = (
                        session.query(Schedule)
                        .filter(Schedule.title_id.in_(title_ids), Schedule.day_of_week == day_of_week)
                        .delete(synchronize_session=False)
                    )
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
        with self.Session as session:
            try:
                if not title_ids:
                    self.logger.error("Ошибка: Массив title_ids пуст.")
                    return

                for title_id in title_ids:
                    existing_title = session.query(Title).filter_by(title_id=title_id).first()
                    if not existing_title:
                        self.logger.error(f"Ошибка: title_id '{title_id}' не найден в таблице Title.")
                        continue

                    existing_studio = session.query(ProductionStudio).filter_by(title_id=title_id).first()
                    if existing_studio:
                        self.logger.warning(f"Студия '{studio_name}' для title_id '{title_id}' уже существует.")
                        continue

                    new_studio = ProductionStudio(title_id=title_id, name=studio_name)
                    session.add(new_studio)
                    self.logger.debug(f"Новая студия добавлена: {studio_name} для title_id: {title_id}")
                session.commit()

            except Exception as e:
                session.rollback()
                self.logger.error(f"Ошибка при добавлении студии в базу данных: {e}")


