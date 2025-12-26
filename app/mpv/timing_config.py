# app/mpv/timing_config.py
"""
Конфигурация задержек для стабильной инициализации MPV плеера
В debug режиме можно использовать меньшие значения, в release - большие
"""

import os

# Определяем режим по переменной окружения или наличию флага
DEBUG_MODE = os.environ.get('MPV_DEBUG', '0') == '1'


class TimingConfig:
    """
    Централизованная конфигурация всех задержек в плеере

    Domain Model:
    - WID_INIT: время на создание native window handle
    - ENGINE_READY: время на инициализацию MPV engine
    - LOAD_DELAY: время перед командой load
    - METADATA_WAIT: время на загрузку метаданных потока
    - PLAYBACK_START: время перед запуском воспроизведения
    - SWITCH_COMPLETE: время на завершение переключения треков
    """

    if DEBUG_MODE:
        # Debug режим - минимальные задержки
        WID_INIT_DELAY = 50  # После show() видео окна
        ENGINE_READY_CHECK = 100  # Проверка готовности движка
        PLAYLIST_LOAD_DELAY = 150  # Перед загрузкой плейлиста
        UI_TIMER_START = 200  # Запуск UI таймера

        TRACK_SWITCH_DELAY = 50  # Перед _do_load
        METADATA_LOAD_WAIT = 100  # Между load() и play()
        PLAYBACK_START_WAIT = 400  # Перед очисткой флага switch

        WATCHDOG_PAUSE = 1500  # Пауза watchdog после seek
        SEEKING_GUARD = 2000  # Защита от seek во время буферизации

        ZERO_DELAY = 0
        SWITCHING_TRACK = 400
        NEXT_MEDIA = 200
        FORCE_RELOAD_CUR = 900
        VIDEO_WIN_USER_CLOSE = 10

    else:
        # Release/Production режим - увеличенные задержки для стабильности
        WID_INIT_DELAY = 300  # ← КЛЮЧЕВОЕ: дать время на создание HWND
        ENGINE_READY_CHECK = 200  # ← Проверка что engine точно готов
        PLAYLIST_LOAD_DELAY = 300  # ← Задержка перед первой загрузкой
        UI_TIMER_START = 400  # ← UI таймер запускается позже

        TRACK_SWITCH_DELAY = 200  # ← Дать время на processEvents
        METADATA_LOAD_WAIT = 300  # ← ВАЖНО: MPV нужно время на парсинг потока
        PLAYBACK_START_WAIT = 300  # ← Больше времени на стабилизацию

        WATCHDOG_PAUSE = 2000  # Больше терпения к буферизации
        SEEKING_GUARD = 3000  # Защита от преждевременных seek

        ZERO_DELAY = 0
        SWITCHING_TRACK = 400
        NEXT_MEDIA = 200
        FORCE_RELOAD_CUR = 900
        VIDEO_WIN_USER_CLOSE = 10


    @classmethod
    def get_init_delays(cls):
        """Возвращает словарь с задержками для инициализации"""
        return {
            'wid_init': cls.WID_INIT_DELAY,
            'engine_ready': cls.ENGINE_READY_CHECK,
            'playlist_load': cls.PLAYLIST_LOAD_DELAY,
            'ui_timer': cls.UI_TIMER_START,
        }

    @classmethod
    def get_playback_delays(cls):
        """Возвращает словарь с задержками для воспроизведения"""
        return {
            'track_switch': cls.TRACK_SWITCH_DELAY,
            'metadata_wait': cls.METADATA_LOAD_WAIT,
            'playback_start': cls.PLAYBACK_START_WAIT,
        }

    @classmethod
    def info(cls):
        """Выводит текущую конфигурацию таймингов"""
        mode = "DEBUG" if DEBUG_MODE else "RELEASE"
        print(f"=== MPV Timing Config ({mode} mode) ===")
        print(f"WID Init Delay:        {cls.WID_INIT_DELAY}ms")
        print(f"Engine Ready Check:    {cls.ENGINE_READY_CHECK}ms")
        print(f"Playlist Load Delay:   {cls.PLAYLIST_LOAD_DELAY}ms")
        print(f"UI Timer Start:        {cls.UI_TIMER_START}ms")
        print(f"Track Switch Delay:    {cls.TRACK_SWITCH_DELAY}ms")
        print(f"Metadata Load Wait:    {cls.METADATA_LOAD_WAIT}ms")
        print(f"Playback Start Wait:   {cls.PLAYBACK_START_WAIT}ms")
        print("=" * 50)


# Экспортируем константы для удобства
WID_INIT_DELAY = TimingConfig.WID_INIT_DELAY
ENGINE_READY_CHECK = TimingConfig.ENGINE_READY_CHECK
PLAYLIST_LOAD_DELAY = TimingConfig.PLAYLIST_LOAD_DELAY
UI_TIMER_START = TimingConfig.UI_TIMER_START
TRACK_SWITCH_DELAY = TimingConfig.TRACK_SWITCH_DELAY
METADATA_LOAD_WAIT = TimingConfig.METADATA_LOAD_WAIT
PLAYBACK_START_WAIT = TimingConfig.PLAYBACK_START_WAIT
WATCHDOG_PAUSE = TimingConfig.WATCHDOG_PAUSE
SEEKING_GUARD = TimingConfig.SEEKING_GUARD
VIDEO_WIN_USER_CLOSE = TimingConfig.VIDEO_WIN_USER_CLOSE
FORCE_RELOAD_CUR = TimingConfig.FORCE_RELOAD_CUR
NEXT_MEDIA = TimingConfig.NEXT_MEDIA
SWITCHING_TRACK = TimingConfig.SWITCHING_TRACK
ZERO_DELAY = TimingConfig.ZERO_DELAY

