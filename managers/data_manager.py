# data_manager.py
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

class Poster:
    def __init__(self, poster_data):
        self.logger = logging.getLogger(__name__)
        try:
            self.small = poster_data.get('small', {}).get('url', '')
            self.medium = poster_data.get('medium', {}).get('url', '')
            self.large = poster_data.get('large', {}).get('url', '')
            self.logger.debug(f"Poster parsed: small={self.small}, medium={self.medium}, large={self.large}")
        except Exception as e:
            self.logger.error(f"Error parsing poster data: {str(e)}")

class Torrent:
    def __init__(self, torrent_data):
        self.logger = logging.getLogger(__name__)
        try:
            self.quality = torrent_data.get('quality', {}).get('string', 'Unknown quality')
            self.url = torrent_data.get('url', '')
            self.logger.debug(f"Torrent parsed: quality={self.quality}, url={self.url}")
        except Exception as e:
            self.logger.error(f"Error parsing torrent data: {str(e)}")

class Episode:
    def __init__(self, episode_data):
        self.number = episode_data.get('number', 'Unknown')
        self.name = episode_data.get('name', 'Unknown')
        self.hls = episode_data.get('hls', {})

class Title:
    def __init__(self, title_data):
        self.logger = logging.getLogger(__name__)
        try:
            self.id = title_data.get('id', 'Unknown ID')
            self.code = title_data.get('code', 'Unknown Code')
            self.name_ru = title_data.get('names', {}).get('ru', 'Unknown')
            self.name_en = title_data.get('names', {}).get('en', 'Unknown')
            self.poster = Poster(title_data.get('posters', {}))
            self.torrents = [Torrent(t) for t in title_data.get('torrents', {}).get('list', [])]
            self.status = title_data.get('status', 'Unknown status')
            self.description = title_data.get('description', 'No description available')
            self.genres = title_data.get('genres', [])
            self.episodes = [Episode(ep) for ep in title_data.get('player', {}).get('playlist', [])]
            self.logger.debug(f"Title parsed: id={self.id}, name_en={self.name_en}, torrents={len(self.torrents)}, genres={self.genres}")
        except Exception as e:
            self.logger.error(f"Error parsing title data: {str(e)}")


class DaySchedule:
    def __init__(self, day_data):
        self.logger = logging.getLogger(__name__)
        try:
            self.day = day_data.get('day', 'Unknown')
            self.titles = [Title(title) for title in day_data.get('list', [])]
            self.logger.debug(f"Day schedule parsed: day={self.day}, number of titles={len(self.titles)}")
        except Exception as e:
            self.logger.error(f"Error parsing day schedule: {str(e)}")

class ScheduleParser:
    @staticmethod
    def parse_schedule(json_data):
        logger = logging.getLogger(__name__)
        try:
            logger.debug(f"Parsing schedule data: {len(json_data)}")
            if isinstance(json_data, dict) and 'list' in json_data:
                # If json_data contains a main object with the 'list' field
                logger.debug("Detected single day schedule in dict format.")
                return DaySchedule(json_data)
            elif isinstance(json_data, list):
                # If json_data is a list of objects (multiple days)
                logger.debug("Detected multiple days schedule in list format.")
                return [DaySchedule(day) for day in json_data]
            else:
                logger.error(f"Unrecognized format in schedule data: {json_data}")
                return None
        except Exception as e:
            logger.error(f"Error parsing schedule: {str(e)}")
            return None

class TitleParser:
    @staticmethod
    def parse_title(json_data):
        try:
            if isinstance(json_data, dict) and 'list' in json_data:
                return Title(json_data)
            else:
                return None
        except Exception as e:
            logging.error(f"Error parsing schedule: {str(e)}")
            return None

class RandomTitleParser:
    @staticmethod
    def parse_random_title(json_data):
        try:
            if isinstance(json_data, dict) and 'list' in json_data:
                return Title(json_data)

            else:
                return None
        except Exception as e:
            logging.error(f"Error parsing schedule: {str(e)}")
            return None