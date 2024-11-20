# tables.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, LargeBinary, ForeignKey, Text, or_, \
    and_, SmallInteger, PrimaryKeyConstraint
from sqlalchemy.orm import sessionmaker, declarative_base, session, relationship, validates, joinedload, load_only
from datetime import datetime, timezone
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Модели для таблиц
class Title(Base):
    __tablename__ = 'titles'
    title_id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)
    name_ru = Column(String, nullable=False)
    name_en = Column(String)
    alternative_name = Column(String)
    title_franchises = Column(String)
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
    title_genres = Column(String)
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
    host_for_player = Column(String)
    alternative_player = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

    franchises = relationship("FranchiseRelease", back_populates="title", cascade="all, delete-orphan")
    genres = relationship("TitleGenreRelation", back_populates="title")
    team_members = relationship("TitleTeamRelation", back_populates="title")
    episodes = relationship("Episode", back_populates="title")
    torrents = relationship("Torrent", back_populates="title")
    posters = relationship("Poster", back_populates="title")
    schedules = relationship("Schedule", back_populates="title")
    ratings = relationship("Rating", back_populates="title")
    history = relationship("History", back_populates="title")


class DaysOfWeek(Base):
    __tablename__ = 'days_of_week'
    day_of_week = Column(Integer, primary_key=True)
    day_name = Column(String, unique=True)

# Данные для заполнения
days = [
    {"day_of_week": 0, "day_name": "Monday"},
    {"day_of_week": 1, "day_name": "Tuesday"},
    {"day_of_week": 2, "day_name": "Wednesday"},
    {"day_of_week": 3, "day_name": "Thursday"},
    {"day_of_week": 4, "day_name": "Friday"},
    {"day_of_week": 5, "day_name": "Saturday"},
    {"day_of_week": 6, "day_name": "Sunday"},
]


class Schedule(Base):
    __tablename__ = 'schedule'
    day_of_week = Column(Integer, ForeignKey('days_of_week.day_of_week'), nullable=False)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        PrimaryKeyConstraint('day_of_week', 'title_id'),
    )

    title = relationship("Title", back_populates="schedules")
    day = relationship("DaysOfWeek")


class History(Base):
    __tablename__ = 'history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)  # Предполагается, что `user_id` будет использоваться для идентификации пользователя
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    episode_id = Column(Integer, ForeignKey('episodes.episode_id'), nullable=True)
    torrent_id = Column(Integer, ForeignKey('torrents.torrent_id'), nullable=True)
    is_watched = Column(Boolean, default=False)
    last_watched_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    previous_watched_at = Column(DateTime, nullable=True)
    watch_change_count = Column(Integer, default=0)
    is_download = Column(Boolean, default=False)
    last_download_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    previous_download_at = Column(DateTime, nullable=True)
    download_change_count = Column(Integer, default=0)
    need_to_see = Column(Boolean, default=False)

    title = relationship("Title", back_populates="history")
    episode = relationship("Episode", back_populates="history")
    torrent = relationship("Torrent", back_populates="history")

class Rating(Base):
    __tablename__ = 'ratings'

    rating_id = Column(Integer, primary_key=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    rating_name = Column(String, default='CMERS', nullable=False)
    rating_value = Column(SmallInteger, nullable=False)

    title = relationship("Title", back_populates="ratings")

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
    history = relationship("History", back_populates="episode")

    @validates('created_timestamp', 'last_updated')
    def validate_timestamp(self, key, value):
        if isinstance(value, (int, float)):
            return datetime.utcfromtimestamp(value)
        return value

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
    history = relationship("History", back_populates="torrent")

class Poster(Base):
    __tablename__ = 'posters'
    poster_id = Column(Integer, primary_key=True, autoincrement=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'), nullable=False)
    poster_blob = Column(LargeBinary, nullable=False)  # Поле для хранения бинарных данных изображения
    last_updated = Column(DateTime, default=datetime.utcnow)

    title = relationship("Title", back_populates="posters")

class Template(Base):
    __tablename__ = 'templates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    one_title_html = Column(Text, nullable=False)
    titles_html = Column(Text, nullable=False)
    text_list_html = Column(Text, nullable=False)
    styles_css = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
