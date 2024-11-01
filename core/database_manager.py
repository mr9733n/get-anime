import logging

from PyQt5.uic.Compiler.qobjectcreator import logger
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, LargeBinary, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, session
from datetime import datetime, timezone
from sqlalchemy.dialects.sqlite import insert

# Создаем базовый класс для всех моделей
Base = declarative_base()

# Настраиваем соединение с базой данных
engine = create_engine('sqlite:///anime_player.db', echo=True)
SessionLocal = sessionmaker(bind=engine)

class DatabaseManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = SessionLocal()

    def initialize_tables(self):
        Base.metadata.create_all(engine)

    def save_title(self, title_data):
        try:
            self.logger.debug(f"Saving title data: {title_data}")

            # Проверка на наличие и корректность данных
            if not isinstance(title_data, dict):
                raise ValueError("Переданные данные для сохранения тайтла должны быть словарем")

            # Проверка типов ключевых полей
            if not isinstance(title_data.get('title_id'), int):
                raise ValueError("Неверный тип для 'title_id'. Ожидался тип int.")

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
            logger.error(f"Ошибка при сохранении тайтла в базе данных: {e}")

    def save_episode(self, episode_data):
        try:
            self.logger.debug(f"Saving episode data: {episode_data}")

            if not isinstance(episode_data, dict):
                self.logger.error(f"Invalid episode data: {episode_data}")
                return

            existing_episode = self.session.query(Episode).filter_by(episode_id=episode_data['episode_id']).first()

            if existing_episode:
                # Проверка на изменение данных эпизода и обновление атрибутов
                is_updated = False
                for key, value in episode_data.items():
                    if key != 'last_updated' and getattr(existing_episode, key) != value:
                        setattr(existing_episode, key, value)
                        is_updated = True

                if is_updated:
                    self.session.commit()  # Коммит, если данные были изменены
            else:
                # Добавление нового эпизода, если он не существует
                new_episode = Episode(**episode_data)
                self.session.add(new_episode)
                self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Ошибка при сохранении эпизода в базе данных: {e}")

        # Модели для таблиц
class Title(Base):
    __tablename__ = 'titles'
    title_id = Column(Integer, primary_key=True)
    name_ru = Column(String, nullable=False)
    name_en = Column(String)
    alternative_name = Column(String)
    poster_path = Column(String)
    description = Column(String)
    type = Column(String)
    episodes_count = Column(Integer)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Episode(Base):
    __tablename__ = 'episodes'
    episode_id = Column(Integer, primary_key=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'))
    episode_number = Column(Integer, nullable=False)
    name = Column(String)
    hls_fhd = Column(String)
    hls_hd = Column(String)
    hls_sd = Column(String)
    preview_path = Column(String)
    skips = Column(String)

class WatchHistory(Base):
    __tablename__ = 'watch_history'
    user_id = Column(Integer, primary_key=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'), primary_key=True)
    episode_number = Column(Integer)
    is_watched = Column(Boolean, default=False)
    last_watched_at = Column(DateTime, default=datetime.utcnow)

class Torrent(Base):
    __tablename__ = 'torrents'
    torrent_id = Column(Integer, primary_key=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'))
    episodes_range = Column(String)
    quality = Column(String)
    size_string = Column(String)
    magnet_link = Column(String)

class Poster(Base):
    __tablename__ = 'posters'
    poster_id = Column(Integer, primary_key=True)
    title_id = Column(Integer, ForeignKey('titles.title_id'))
    size = Column(String)
    poster_blob = Column(LargeBinary)
    last_updated = Column(DateTime, default=datetime.utcnow)

# Пример использования
if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.initialize_tables()  # Инициализируем таблицы
