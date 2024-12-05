# Anime Player App 0.3.0.1 

## Этап 1: Подготовка Таблиц и Структуры Базы Данных
### 1.1 Создание `DatabaseManager` для работы с SQLite
- [x] Выбрать SQLAlchemy как ORM для безопасного и удобного управления базой данных.
- [x] Создать класс `DatabaseManager`, который будет управлять подключением к базе и CRUD-операциями.
- [x] Настроить соединение с базой данных (`anime_player.db`).

### 1.2 Определение Таблиц для Хранения Данных
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

### 1.3 Реализация Метода Инициализации Базы Данных
- [x] Создать метод `initialize_tables` в `DatabaseManager`, который будет создавать все таблицы при запуске приложения.

## Этап 2: Асинхронное Сохранение Данных после Запроса
### 2.1 Модификация Логики Запросов
- [x] Добавить логику для асинхронного сохранения данных после получения ответа от API.
- [x] Подключить `DatabaseManager` к месту, где выполняются запросы к API, чтобы сохранять полученные данные.

### 2.2 Асинхронное Сохранение Данных
- [x] Реализовать функцию `save_title_async`, которая асинхронно сохраняет данные о тайтлах в базу данных.
- [x] Обновить код для обработки расписания, чтобы после получения JSON сохранять все тайтлы и эпизоды в базу.


## Этап 3: Валидация Данных
### 3.1 Добавление Проверок Перед Сохранением
- [x] Реализовать проверку структуры JSON перед сохранением, чтобы убедиться, что все ключевые поля присутствуют.
- [x] Добавить логику для обработки ошибок при отсутствии необходимых данных.

### 3.2 Использование Pydantic для Валидации
- [ ] Установить Pydantic и создать схемы для валидации данных (`TitleSchema`, `EpisodeSchema` и т.д.).
- [ ] Подключить валидацию к функциям сохранения, чтобы проверять данные перед их записью в базу.

## Этап 4: Хранение Постеров в Базе Данных
### 4.1 Преобразование Постеров в Байты и Сохранение
- [x] Реализовать метод для преобразования постера в байты при загрузке через URL.
- [x] Добавить поле `poster_blob` в таблицу `Posters` для хранения бинарных данных постера.

### 4.2 Логика Кеширования Постеров
- [x] Реализовать метод `get_poster` в `DatabaseManager` для проверки наличия постера в базе данных.
- [x] Если постера нет, загрузить его и сохранить в базе данных.

## Этап 5: Подготовка Нового Интерфейса
### 5.1 Создание Окна для Нового Интерфейса
- [x] Создать новое окно интерфейса с использованием PyQt, которое подключается к базе данных для получения информации о тайтлах.
- [x] Добавить в интерфейс отображение тайтлов и эпизодов из базы данных.

### 5.2 Переход к Новому Интерфейсу
- [x] Перенести логику отправки запросов в новый интерфейс.
- [x] Постепенно заменить старый интерфейс на новый, используя данные из базы.

### Этап 6: Дополнительные Улучшения и Оптимизация
### 6.1 разнести логику
- [ ] распилить qt/app.py , возможно часть логики можно оптимизировать
- [ ] возможно стоит вынести сохранение в бд


## Этап 7: Дополнительные Улучшения и Оптимизация
### 7.1 Оптимизация Работы с Датами
- [x] Добавить проверку на устаревшие данные (`last_updated`) для постеров и тайтлов, чтобы при необходимости загружать их заново.

### 7.2 Обработка Ошибок и Резервное Копирование
- [ ] Реализовать обработку ошибок при взаимодействии с базой данных, чтобы избежать потери данных.
- [ ] Добавить функциональность для резервного копирования базы данных.

### 7.3 Улучшение Интерфейса
- [ ] Добавить отображение истории просмотра и рейтингов тайтлов в новом интерфейсе.
- [ ] Реализовать возможность пользователю отмечать просмотренные эпизоды и добавлять рейтинг.

## 8. Anime Player App 0.3.8.3 

### 8.4. add reload button in title_browser
-[x] static\reload.png
-[x] will be triggered self.refresh_display()

### 8.5. add torrent downloaded status icon
-[x] uses watch_history table add torrent downloaded status
-[x] filter by torrent_id
-[x] relationship title_id

### 8.6. add watch history bulk selection
-[x] select all ^-^
-[ ] select many >_< 
-[x] add flag "need to see"-[x]
-[x] fix statistics

### 8.7. UI REFACTORING '-' 0.3.8.7
-[x] ui_generator for title_browser
-[x] ui_system_generator for system_browser
-[x] Refactor ui_generator
-[x] html templates in static/ folder
-[x] implement jinja
-[x] save/get html templates from db
-[x] titles_browser
-[x] one_title_browser

### 8.8. DB REFACTORING ^-^
-[x] move logic to new files and create proxy methods
```commandline
	core/
		├── save.py
		├── process.py
		├── get.py
		├── tables.py
		├── utils.py
		└── database_manager.py

```

### 8.9. Add ProductionStudio table
-[x] with fields: title_id, studio_name, last_update
-[x] with relationship Titles
-[x] saves title_ids, studio_name
-[x] add new studios on System screen
-[x] bug fixes and improvements
-[x] fix builder
-[x] add icon to app
- 
### 8.10. APP REFACTORING
-[x] refactor display_titles
-[x] refactor display_titles_in_ui
-[x] refactor ui_manager
-[x] added:
-[x] TitleDisplayFactory
-[x] TitleDataFactory
-[x] TitleBrowserFactory
-[x] TitleHtmlFactory
-[x] dynamic ui generating from metadata file
-[ ] get titles list without episodes
-[x] get franchises list without episodes
-[x] get need to see without episodes
-[x] fixed empty screen by reset offset when offset is high and titles was not found
-[x] fixed play button
-[x] added shadow for UI elements

### 8.11. need to think how to merge data from other devices
-[x] added merge_utility
-[x] merge 2 db from arguments
-[x] merge db from temp folder as default
-[x] upload to file.io
-[x] save qrcode image with link
-[x] download from file.io by link
-[x] download from file.io by qrcode
-[x] send email with link
-[x] send email with qrcode image
-[x] Anime Player Merge Utility App version 0.0.0.1
-[x] Anime Player Sync App version 0.0.0.1
-[ ] Fix Merge same DB ERROR in logs
-[x] Added checksum verify for injection merge_utility.exe

   - #### Create binary: 
      ```commandline
      pyinstaller main.spec --noconfirm 
      pyinstaller merge_utility.spec --noconfirm
      pyinstaller sync.spec --noconfirm
      ```

### 8.12. redesign system browser
-[x] need to add new layout window
-[x] view statics
-[ ] add/update table data
-[ ] template name add
-[x] reset offset link for extra issues

### 8.13. Some fixes
-[ ] add night theme
-[ ] deprecate more than one run
-[ ] add button to show Need to see list
-[ ] max size for log file then rotate
-[ ] need to fix watch status for title_id when set status first time

### 8.14. change one title view
-[ ] show production studio
-[ ] need to change width of title browser if window is changed
-[ ] idea: you can change window horizontal size and stretch title browser with window

### 8.15. need to implement own player window uses vlc_lib

### 8.16. something for db
-[ ] remove schedule view logic from get_titles
-[ ] Try to do migration for old big db
-[ ] create job to inspect db tables for condition

## Этап 9: Тестирование и Оптимизация
### 9.1 Тестирование Методов `DatabaseManager`
- [ ] Написать юнит-тесты для каждого метода `DatabaseManager` (создание, чтение, обновление, удаление данных).
- [ ] Тестировать работу с базой данных на корректность добавления и получения данных.

### 9.2 Тестирование Интеграции
- [ ] Тестировать взаимодействие базы данных с остальным приложением, чтобы убедиться в правильности логики сохранения и загрузки данных.
- [ ] Тестировать новый интерфейс, чтобы проверить отображение данных и правильность работы функционала.
