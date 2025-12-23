# Anime Player App 0.3.0.1 
## Этап 1. Подготовка Таблиц и Структуры Базы Данных
### 1.1. Создание `DatabaseManager` для работы с SQLite
- [x] Выбрать SQLAlchemy как ORM для безопасного и удобного управления базой данных.
- [x] Создать класс `DatabaseManager`, который будет управлять подключением к базе и CRUD-операциями.
- [x] Настроить соединение с базой данных (`anime_player.db`).

### 1.2. Определение Таблиц для Хранения Данных
- [x] Создать таблицу `Titles` для хранения информации о тайтлах.
  - Поля: `title_id`, `name_ru`, `name_en`, `alternative_name`, `poster_path`, `description`, `type`, `episodes_count`, `last_updated`.
- [x] Создать таблицу `Episodes` для хранения информации о сериях.
  - Поля: `episode_id`, `title_id`, `episode_number`, `name`, `hls_fhd`, `hls_hd`, `hls_sd`, `preview_path`, `skips`.
- [x] Создать таблицу `WatchHistory` для отслеживания истории просмотра.
  - Поля: `user_id`, `title_id`, `episode_number`, `is_watched`, `last_watched_at`.
- [x] Создать таблицу `Torrents` для хранения информации о торрентах.
  - Поля: `torrent_id`, `title_id`, `episodes_range`, `quality`, `size_string`, `magnet_link`.
- [x] Создать таблицу `Posters` для хранения постеров.
  - Поля: `poster_id`, `title_id`, `size`, `poster_blob`, `last_updated`.

### 1.3. Реализация Метода Инициализации Базы Данных
- [x] Создать метод `initialize_tables` в `DatabaseManager`, который будет создавать все таблицы при запуске приложения.

## Этап 2. Асинхронное Сохранение Данных после Запроса
### 2.1. Модификация Логики Запросов
- [x] Добавить логику для асинхронного сохранения данных после получения ответа от API.
- [x] Подключить `DatabaseManager` к месту, где выполняются запросы к API, чтобы сохранять полученные данные.

### 2.2. Асинхронное Сохранение Данных
- [x] Реализовать функцию `save_title_async`, которая асинхронно сохраняет данные о тайтлах в базу данных.
- [x] Обновить код для обработки расписания, чтобы после получения JSON сохранять все тайтлы и эпизоды в базу.

## Этап 3. Валидация Данных
### 3.1. Добавление Проверок Перед Сохранением
- [x] Реализовать проверку структуры JSON перед сохранением, чтобы убедиться, что все ключевые поля присутствуют.
- [x] Добавить логику для обработки ошибок при отсутствии необходимых данных.

## Этап 4. Хранение Постеров в Базе Данных
### 4.1. Преобразование Постеров в Байты и Сохранение
- [x] Реализовать метод для преобразования постера в байты при загрузке через URL.
- [x] Добавить поле `poster_blob` в таблицу `Posters` для хранения бинарных данных постера.

### 4.2. Логика Кеширования Постеров
- [x] Реализовать метод `get_poster` в `DatabaseManager` для проверки наличия постера в базе данных.
- [x] Если постера нет, загрузить его и сохранить в базе данных.

## Этап 5. Подготовка Нового Интерфейса
### 5.1. Создание Окна для Нового Интерфейса
- [x] Создать новое окно интерфейса с использованием PyQt, которое подключается к базе данных для получения информации о тайтлах.
- [x] Добавить в интерфейс отображение тайтлов и эпизодов из базы данных.

### 5.2. Переход к Новому Интерфейсу
- [x] Перенести логику отправки запросов в новый интерфейс.
- [x] Постепенно заменить старый интерфейс на новый, используя данные из базы.

### Этап 6. Дополнительные Улучшения и Оптимизация
### 6.1. разнести логику
- [x] распилить qt/app.py , возможно часть логики можно оптимизировать
- [x] возможно стоит вынести сохранение в бд

## Этап 7. Дополнительные Улучшения и Оптимизация
### 7.1. Оптимизация Работы с Датами
- [x] Добавить проверку на устаревшие данные (`last_updated`) для постеров и тайтлов, чтобы при необходимости загружать их заново.

### 7.3. Улучшение Интерфейса
- [x] Добавить отображение истории просмотра и рейтингов тайтлов в новом интерфейсе.
- [x] Реализовать возможность пользователю отмечать просмотренные эпизоды и добавлять рейтинг.

## 8. Anime Player App 0.3.8.3 
### 8.4. add reload button in title_browser
- [x] static\reload.png
- [x] will be triggered self.refresh_display()

### 8.5. add torrent downloaded status icon
- [x] uses watch_history table add torrent downloaded status
- [x] filter by torrent_id
- [x] relationship title_id

### 8.6. add watch history bulk selection
- [x] select all ^-^
- [x] add flag "need to see"- [x]
- [x] fix statistics

### 8.7. UI REFACTORING '-' 0.3.8.7
- [x] ui_generator for title_browser
- [x] ui_system_generator for system_browser
- [x] Refactor ui_generator
- [x] html templates in static/ folder
- [x] implement jinja
- [x] save/get html templates from db
- [x] titles_browser
- [x] one_title_browser

### 8.8. DB REFACTORING ^-^
- [x] move logic to new files and create proxy methods
```commandline
            core/
		├── save.py
		├── process.py
		├── get.py
		├── tables.py
		├── utils.py
		└── database_manager.py
```

### 8.9. redesign system browser
- [x] need to add new layout window
- [x] view statics
- [x] reset offset link for extra issues
### 8.9.2. Add ProductionStudio table
- [x] with fields: title_id, studio_name, last_update
- [x] with relationship Titles
- [x] saves title_ids, studio_name
- [x] add new studios on System screen
- [x] bug fixes and improvements
- [x] fix builder
- [x] add icon to app

### 8.10. APP REFACTORING
- [x] refactor display_titles
- [x] refactor display_titles_in_ui
- [x] refactor ui_manager
- [x] added: TitleDisplayFactory
- [x] added: TitleDataFactory
- [x] added: TitleBrowserFactory
- [x] added: TitleHtmlFactory
- [x] dynamic ui generating from metadata file
- [x] get franchises list without episodes
- [x] get need to see without episodes
- [x] fixed empty screen by reset offset when offset is high and titles was not found
- [x] fixed play button
- [x] added shadow for UI elements

### 8.11. need to think how to merge data from other devices
- [x] added merge_utility
- [x] merge 2 db from arguments
- [x] merge db from temp folder as default
- [x] upload to file.io
- [x] save qrcode image with link
- [x] download from file.io by link
- [x] download from file.io by qrcode
- [x] send email with link
- [x] send email with qrcode image
- [x] Anime Player Merge Utility App version 0.0.0.1
- [x] Anime Player Sync App version 0.0.0.1
- [x] Added checksum verify for injection merge_utility.exe
   - #### Create binary: 
      ```commandline
      pyinstaller build.spec --noconfirm 
      ```
- [x] bug fix: get schedule or reload schedule when request fails
- [x] check_dll script added
- [x] add button to show Need to see list

### 8.12. need to implement own player window uses vlc_lib
- [x] added config setting 'use_libvlc'
- [x] added verifying and injecting libvlc.dll
- [x] vlc layout
- [x] player controls layout
- [x] video seek bar fixed ?
- [x] add skip_opening and skip_endings
- [x] fixed skip_opening and skip_endings ^-^
- [x] add skip credits button
- [x] add highlighting for current playing stream
- [x] need to fix  skip_opening and skip_endings ^-^ when next episode started from playlist
- [x] prevent multiple instances of your app from running
- [x] add prevent to sleep while playing 
- [x] fixed saving screenshot 
- [x] fix bug with PAUSE button it set on position
- [x] max size for log file then rotate
- [x] fixed search by keywords in local db 

### 8.13 REFACTORING 
- [x] refactoring skip credits
- [x] refactoring episode skip credits data sending
- [x] fix fetching version for production version
- [x] fix bug with logging file rotation
- [x] removed 2.x version
- [x] add creating archive module with production version
- [x] small optimizations for build
- [x] AnimePlayerLite from app version 1.9 added

### 8.14. Some fixes
- [x] some fixes for build pyInstaller 5.x
- [x] .spec for pyInstaller 6.x
```bash
python create_archive.py
```

### 8.15. Add title scrapper & compare
- [x] add title_id scrapper
```bash
python scrapper.py
```
- [x] add comparing scrapping result file with local db
```bash
python compare_titles.py
```

### 8.16. Some fixes
- [x] fix get multiply titles in api client 
- [x] fix uploading db
- [x] fix downloading db 
- [x] add logic for logging app closing
- [x] add logic for logging app crash
- [x] add additional logic for handling Qt errors
- [x] fixed creating the fault.log on app start
- [x] utils excluded from the build were moving to the midnight folder
- [x] Need to add refreshing title when loaded from db by api request 

### 8.17. Saving app current state on exit
- [x] add logic to save app current state on exit
- [x] add logic to load saved app state on start
- [x] fixes restoring logic
- [x] add loader for hard tasks
- [x] remove unused imports

### 8.18. New templates
- [x] disable console
- [x] add window for logs in system browser
- [x] add switching template in system browser
- [x] prepare to save current template
- [x] add saving current template on app exit
- [x] load saved template on app start
- [x] add night theme
- [x] show current template in select box 
- [x] apply templates for log window
- [x] update logs data while log window open
- [x] close all child windows on main window closed 
- [x] apply template to custom VLC window 
- [x] fix saving state for the list of title_ids 
- [x] add api error message
- [x] some improvements for build.spec
- [x] fix Database comparison after build

### 8.19. Some fixes
- [x] ERROR | app.qt.app_state_manager.save_state_to_db | Ошибка при сохранении состояния в БД: Object of type set is not JSON serializable
- [x] change text on log button when closed window
- [x] fix fetch title by id
- [x] fix saving state for title_id
- [x] add code stats script

### 8.20. Improvements
- [x] New feature: show titles by genre
- [x] New feature: add pagination info
- [x] fix find more than 2 titles
- [x] small fixes for compare_titles
- [x] New feature: add UPDATE TITLE button for title
- [x] changed button titles: UPDATE TITLE -> UT⮂, RELOAD -> RS⮂
- [x] New feature: scrapping and compare poster links
- [x] fix updating title
- [x] New feature: show titles by team member
- [x] fix filter by genre & team_member
- [x] fix reload template
- [x] New feature: show titles by year
- [x] add current show_mode in pagination
- [x] add show_mode in app_state
- [x] fix pagination: shows wrong first page, large offset value 

### 8.21. Some fixes
- [x] update build.spec for py installer 6.x
- [x] New feature: show titles by status 
- [x] change background-color in no_background & no_background_night template for system, text_list
- [x] addd pagination for titles list, franchises, need to see
- [x] refactoring pagination logic
- [x] add check all tables enhanced_duplicate_finder.py
#### Check all tables for duplicates interactively
```commandline
python enhanced_duplicate_finder.py
```
#### Auto-fix duplicates in all tables, keeping the latest records
```commandline
python enhanced_duplicate_finder.py --auto-fix
```
#### Check only specific tables
```commandline
python enhanced_duplicate_finder.py --tables title_team_relation,posters
```
#### Auto-fix duplicates, but keep the oldest records
```commandline
python enhanced_duplicate_finder.py --auto-fix --keep-oldest
```
#### Specify a custom output file
```commandline
python enhanced_duplicate_finder.py --output /path/to/results.txt
```
- [x] move logs from midnight scripts to logs folder
- [x] improvements in enhanced_duplicate_finder.py 
- [x] CHECK fix deleting titles from schedule table after reload
- [x] error notification for updating titles

### 8.22. Some changes 
- [x] use symbols instead of images for icons
- [x] add hints for links
- [x] little changes
 
### 8.23. Some fixes
- [x] Updated deprecated Datetime calls
- [x] Fixed saving date in episodes tables
- [x] Show franchises links in title
- [x] Filter titles by franchise
- [x] Show day of week in title 
- [x] Fix offset and pagination
- [x] Reload poster images
- [x] Reload schedule rework
- [x] Some fixes in Rating
- [x] Some fixed in Episode saving

### 8.24. Refactoring and bug fixes  
- [x] Add standalone for vlc_player
- [x] Moved custom vlc player to another process thread
- [x] Add query thread for saving posters
- [x] More robust for downloading posters
- [x] Small fixes
- [x] Clean PosterManager
- [x] Added LinkActionHandler
- [x] Fixed saving date in torrents tables
- [x] Fixed updating torrents in torrents tables
- [x] Fixed cleaning torrent duplicates in enhanced_db_manager

### 8.25. Some fixes
- [x] save torrent fix for api v3

### 8.26. New feature
- [x] API v3 obsolete - disabled
- [x] API v1 implemented

### 8.27. Some fixes
- [x] switch day_of_week from api v3 to api v1
- [x] fix removing titles from schedule
- [x] 2025-03-19 11:58:03 | ERROR | core.save.remove_schedule_day | Error while removing schedules for title_ids [<core.tables.Title object at 0x000002446AA96AE0>] and day 0: Object <core.tables.Title object at 0x000002446AA96AE0> is not legal as a SQL literal value

### 8.28. Some fixes
- [x] added httpx as easy async fix
- [x] fixes in adapter
- [x] fix saving torrents

### 8.29. Some fixes
- [x] enrich fetch episodes checks
- [x] fix random title load
- [x] add check for 404 for api client
- [x] add docs
- [x] Enabled torrent loading on schedule
- [x] Fix mapping status_code & status_string
- [x] Fix presenting day of eek on schedule
- [x] Builder 5.x checked
- [x] remove possible duplicates on saving torrents

### 8.30. docs
- [x] Readme eng added
- [x] License eng added

### 8.31. saving torrents
- [x] fix saving torrents
- [x] deduplicate torrents
- [x] add more info on UI for torrents
- [x] add more info on UI for episodes

### 8.32. simple callback
- [x] add ongoing titles button
- [x] Add status for buttons (simple callback) - show in pagination 
- [x] fix skip credits
- [x] fix saving episode no. 0
- [x] fix app lite version for api v1 
- [x] optimizations for app lite
- [x] added properties details on build  

### 8.33 AnimePlayerAPP Add AniMedia as second provider
- [x] Add scraper for AniMedia
- [x] Add adapter to resolve data inconsistency  
- [x] Create demo app creating full data response that can process AnimePlayer
- [x] Implement worker for async scraper
- [x] Build-in AniMedia provider in AnimePlayer
- [x] Add provider to FIND
- [x] Add provider to Update Title
- [x] Fix playing in AnimePlayerVLC
- [x] Fix fetch posters
- [x] Fix saving episodes
- [x] Show provider in UI for title
- [x] Remove unused logic
- [x] Fix process poster link
- [x] Add check for poster download
- [x] Pretty code Restore app state
- [x] Add check for Fatal log
- [x] test build.spec for py installer 6.x

### 8.33 Player DB Sync Utility 
- [x] Сквозное шифрование (X25519 + HKDF + NaCl SecretBox), направленные ключи, SAS, TOFU-хранилище (атомично, с fsync).
- [x] Чанковая передача с ACK, итоговый SHA-256, атомарная запись на приёмнике (`.tmp` → `os.replace`).
- [x] mDNS: объявление/поиск, корректный unreg при стопе, подбор реального IPv4.
- [+] «Проверить соединение» с таймаутом/ретраями и подсказками (порт, фаервол). *(базовый есть, доработать UX/тексты ошибок)*
- [x] Троттлинг скорости (лимит КБ/c) — опция в GUI.
- [x] Перезапуск приёмника при сбое mDNS/сокета (авто-рестарт).
- [x] Резюмируемая отправка (resume from offset): сверка размера/хеша снапшота и докачка недостающих чанков.
- [x] Доп. контроль целостности на каждый чанк (CRC32/sha256) + перезапрос конкретных чанков.
- [x] Опциональное сжатие (gzip) на лету для SQLite-снапшота.
- [x] Вкладки: Send / Receive / Merge / Logs; крупный SAS в обеих; индикатор статуса сервера (красный/зелёный).
- [x] История адресов/портов (~/.player_db_gui.json); автоскролл логов; метки времени.
- [x] Тихие логи (агрегаты), сводка по таблицам всегда; компактный вывод FK-violations (топ-10).
- [+] mDNS-список приёмников в выпадающем списке (есть скан; добить автo-обновление и «Очистить/Обновить»).
- [x] Кнопки «Сохранить лог» и «Очистить лог».
- [x] Кнопка «Сбросить доверие (TOFU)» для выбранного хоста.
- [x] Настройки: лимит скорости, размер чанка, опция сжатия, флаги merge (см. ниже) — сохранять в конфиг.
- [x] Вывод всех сообщений в логи
- [x] Чекбокс compress gzip при отправке
- [x] Чекбокс VACUUM при отправке
- [x] Мёрдж по «естественным» ключам: `episodes.uuid`, `torrents.hash`; **никогда** не переписывать локальные `episode_id/torrent_id`.
- [x] `history`: резолв `episode_id` через `uuid`, `torrent_id` через `hash`; пропуск сирот с логом.
- [x] `schedule/production_studios/posters/franchise_releases`: `ensure_title_in_dst(...)`; щадящий пропуск сирот; `posters` — дедуп по `(title_id, hash_value)`, insert без `poster_id`.
- [x] Умный мёрдж `franchise_releases` по смысловому ключу, без переноса суррогатного `id`.
- [x] Итоговый отчёт: число пропущенных по каждой таблице + экспорт CSV «сироты/дубликаты».
- [x] Чекбоксы в GUI Merge: 
      1. «Пропускать постеры без hash»
      2. «Нормализовать дни недели (0..6→1..7)» *(дефолт: выкл, на случай неконсистентных источников)*
      3. «Skip orphans» (поведение по умолчанию уже щадящее — оставить как опцию).
- [x] `PRAGMA optimize`/`VACUUM` после большого мержа (по чекбоксу).
- [x] Новый entry-point `db_sync_gui.py`; старые `sync/merge_utility` исключить из spec/бандла.
- [+] PyInstaller spec: `zeroconf`, `nacl` в hiddenimports; иконка/версия/имя EXE.
- [x] Post-install подсказка про Windows Firewall (вход на выбранный порт).

### 8.34 Player DB Sync Utility  «Через интернет» без релея
#### Internet (TCP + STUN/UPnP)
- [x] использовать текущий TCP протокол
- [x] Режим «Internet» в GUI (переключатель Receive)
- [x]  STUN-детектор внешнего IP (pystun3), отображение адреса и порта
- [x] UPnP / NAT-PMP автопроброс (miniupnpc); результат в логах
- [x] Кнопка «Проверить доступность» (таймаут, диагностика)
- [x] Абстрактный TransportBase
- [x] Реализация TCPTransport

#### WebRTC (DataChannel)
- [x] WebRTCTransport — ядро (offer/answer, ICE, DataChannel) есть.
- [x] GUI: офлайн-сигналинг (Offer/Answer) есть.
- [x] Индикатор ICE есть (states в логах и label).
- [+] Логика fallback к TCP
- [x] GUI: Отобразить компактно в два столбца по смыслу, add scroll
- [x] Pretty Gui
- [x] Split in 2 version LAN and Inet
- [x] Fix transport for LAN version
- [x] Fix shutdown
- [x] Add **Отправитель (WebRTCSenderTransport):**
- [x] Add **Приёмник (WebRTCReceiverCore + GUI):** 
- [+] Добить мелкую косметику (например, текст заголовков/подсказок под каждый режим)
- [x] Fix Delete snapshot
- [x] WebRTC. Fix send more than 1 time  
- [x] после отправки мы не сбрасываем состояние подсказок
- [x] после Приемки мы не сбрасываем состояние подсказок
- [x] после Приемки не очищаем блоки с Offer/Answer

### 8.34 Small fixes
- [x] Fixes in *.spec files
- [x] Fix get_titles_animedia 
- [x] Fix playwright executable doesn't exist at

### 8.35 Fixes Anime Player APP 0.3.8.35
- [x] Removed playwright framework
- [x] Windows fatal exception: access violation 2025-12-03 02:18:29 | CRITICAL | __main__.log_exception | Unexpected exception TypeError: invalid argument to sipBadCatcherResult()
- [x] Pretty code
- [x] Add new tables for providers
- [x] Fix saving titles
- [x] Delete titles
- [x] Fix get titles by keywords
- [x] Add get titles for search query
- [x] Add get titles by provider & external_id
- [x] Fix Update titles
- [x] Add get_studio_by_title_id, get_provider_by_title_id
- [x] Show production studio 
- [x] Fix saving host_for_player from AniLibria
- [x] Add get_player_host_by_title_id
- [x] Fix regress saving dates in titles
- [x] Fix playing video
- [x] Removed playwright from Animedia demo app
- [x] Removed playwright from .spec
- [x] Filter by provider

### 8.36 Anime Player Add Sock proxy
- [x] Add Net client
- [x] Add workaround for net client
- [x] Add net client for each request
- [:(] Add net client for vlc player 
- [x] Create demo app for blocked anime
- [x] Create qt browser for vk, rutube player
- [x] fixes for qt browser
- [x] fix saving combined playlist with multiply providers
- [x] Add New episodes on AniMedia
- [x] Created demo app for new episodes on AniMedia
- [x] Fixes for AniMedia schedule
- [x] Add cache for AniMedia schedule and vlinks
- [x] Add Widget in Anime Player for new episodes on AniMedia
- [x] Add restore on AniMedia schedule screen
- [x] Init AniMedia cache once
- [x] Invalidate cache item for vlinks
- [x] Invalidate title when open from AMS
- [x] Fix on change quality in schedule 2025-12-13 14:44:50 | ERROR | app.qt.app.refresh_display | Ошибка при обновлении экрана при нажатии REFRESH: 'int' object has no attribute 'episodes'
- [x] Remove unused logic from app
- [x] Add generic state

### 8.36 Refactoring AniLiberty API client
- [x] Done
- [x] Smoke tests - done
- [x] Add Unit tests 

### 8.36 Fixes 
- [x] Create adapter for season / We have to many same seasons with different name
- [x] fix play video after was paused
- [x] need to fix watch status for title_id when set status first time
- [x] vlc logs enabled
- [ ] fix vlc proxy

### 8.37 Refactoring Player DB Sync Utility 0.0.0.2
- [ ] Split logic im moduls (managers) from db_sync_gui
- [ ] ...

### 8.38 New features Player DB Sync Utility 0.0.0.3
- [ ] если нажать clear и попробовать отправить бд еще раз то офер не сформируется, то и с ответом
- [ ] Cancel Send
- [ ] Cancel Receive
- [ ] Тест-кнопка «ICE connected?» с логом статусов
- [ ] Тестирование разных NAT/CGNAT сценариев
- [ ] expand offer/answer data. показывать свернутым по умолчанию
- [ ] формировать QR code for offer/answer
- [ ] Отправка Offer/Answer по почте (Postmark): текст + QR в приложении (PNG).
- [ ] Шифрование Offer/Answer перед QR/почтой:
      - либо X25519 + NaCl SecretBox (как в TCP-режиме),
      - либо простая парольная схема (SAS / passphrase) с локальным вводом.
- [ ] Загрузка Offer/Answer из QR (импорт PNG из письма / файла).
- [ ] При выборе WebRTC:
      - дизейблить блок Internet TCP mode (серым),
      - по возможности отключать несвязанные элементы (скорость/лимит порта),
      - в хинтах явно показывать, что используется офлайн-сигналинг.
- [ ] Internet (TCP + STUN/UPnP) Ограничение источников по IP / rate-limit


 ## 9. Check maybe obsolete
### 9.0. Migration to PyQt6
- [x] Started in branch 0.3.8.34
- [ ] Have some bugs
- [ ] ...

### 9.1 Refactoring
- [ ] refactoring app.py

### 9.2. New features & change one title view & redesign system browser 2
- [ ] add additional feature to custom player for seek bar: sliding toggle with click to position
- [ ] need to change width of title browser if window is changed
- [ ] idea: you can change window horizontal size and stretch title browser with window
- [ ] add/update table data
- [ ] ...


## 10. TECH DEBT
### 10.1. Использование Pydantic для Валидации
- [ ] Установить Pydantic и создать схемы для валидации данных (`TitleSchema`, `EpisodeSchema` и т.д.).
- [ ] Подключить валидацию к функциям сохранения, чтобы проверять данные перед их записью в базу.

### 10.2. Обработка Ошибок и Резервное Копирование
- [ ] Реализовать обработку ошибок при взаимодействии с базой данных, чтобы избежать потери данных.
- [ ] Добавить функциональность для резервного копирования базы данных.
- [ ] ? remove schedule view logic from get_titles ?
- [ ] create job to inspect db tables for condition

### 10.3. add watch history bulk selection
- [ ] select many >_< 

## Этап 11. Тестирование и Оптимизация
### 11.1. Тестирование Методов `DatabaseManager`
- [ ] Написать юнит-тесты для каждого метода `DatabaseManager` (создание, чтение, обновление, удаление данных).
- [ ] Тестировать работу с базой данных на корректность добавления и получения данных.

### 11.2. Тестирование Интеграции
- [ ] Тестировать взаимодействие базы данных с остальным приложением, чтобы убедиться в правильности логики сохранения и загрузки данных.
- [ ] Тестировать новый интерфейс, чтобы проверить отображение данных и правильность работы функционала.
