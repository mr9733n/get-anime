# Backend Roadmap — Anime Player

## 📍 Текущий статус

**Backend выделен из Qt-приложения и стабилен.**
Архитектура чистая, контроллеры изолированы от БД, JSON-tool работает.

```
[ DONE: Core Architecture ] → [ DONE: Titles Read ] → NEXT
```

---

## 🟢 DONE — Базовая архитектура

* [x] Standalone backend (без Qt / mpv / vlc)
* [x] JSON-tool (stdin → stdout)
* [x] Stateless backend
* [x] Core / Infra / Transport разделены
* [x] Контроллеры не работают с БД напрямую
* [x] Работа с БД только через порты
* [x] Enricher вынесен в infra

---

## 🟢 DONE — Titles (чтение из БД)

* [x] `titles.search`
* [x] `titles.get` (single / batch)
* [x] `titles.list_episodes`
* [x] provider_links через порт (batched)
* [x] Episodes с абсолютными stream URL
* [x] Posters / previews / torrents через assets-host
* [x] User prefs (history / need_to_see / watched)
[0.3.8.39] branch: feature/0.3.8.39 | 1/8/26 | Merged to main
---

## 🟡🟢 DONE — Write-path (process → save)

**Цель:** любые данные от провайдера (включая расписание) попадают в БД **только** через единый `process`-канал,
где выполняются проверки/нормализация/мерж (и только потом `save`).

* [x] Новый backend-op: `process.provider_payload` (или `sync.apply`)
  * `params`: `{ provider_code, payload, mode }`
* [x] Core: `ProcessController` + use-case `ApplyProviderPayload`
  * Контроллер принимает нормализованный input
  * Дергает use-case
  * Use-case вызывает write-port
* [x] Infra: write-port (обёртка над существующим `db.process_*` / `storage.process`)
  * Core **не видит** `db_manager` / storage напрямую
  * Один канал записи = база для schedule и новых провайдеров
* [x] Unified provider pipeline (search_external_ids/fetch_payload/fetch_and_process/search_and_process)
* [x] titles.update (by provider_links + fallback query)
* [x] unit tests for json handlers + sync + providers (baseline)

**Definition of Done:**

* запись в БД из backend происходит через `process` (одна точка входа)
* Sync-код может вызывать только этот op для применения provider payload
* Update обновляет тайтлы разных провайдеров
* unit-test на ранее созданный функционал
[0.3.8.40] branch: feature/0.3.8.40 | 1/9/26
---

## 🟢 DONE — Связанные сущности Title

**Цель:** сделать `TitleDetailsDTO` действительно полным.

* [x] Ratings (`_pref_ratings` → `list[RatingDTO]`)
* [x] Watch history / history records (`_pref_history_records` → `list[HistoryDTO]`)
* [x] Production studio (`_pref_production_studio_obj` → `ProductionStudioDTO | None`)
* [x] Team members (`_pref_team_members` → `list[TeamMemberDTO]`)
* [x] Franchises (уже было)

**Как сделано:**
- `storage/get.py`: `get_team_members_from_db`, `get_ratings_list_from_db`, `get_history_records_from_db`, `get_production_studio_obj_from_db`
- `storage/database_manager.py`: делегаты
- `storage/queries/title_enricher.py`: устанавливает `_pref_team_members`, `_pref_ratings`, `_pref_history_records`, `_pref_production_studio_obj`
- `backend/core/controllers/titles_controller.py`: читает из `_pref_*`, конвертирует в DTO

📌 Правило:

> никаких heavy-join
> только batched read-порты

[0.3.8.41] branch: feature/0.3.8.41 | 4/24/26
---

## 🟢 DONE — DTO-оптимизация под UI

* [x] `TitleCardDTO` (облегчённый) — без episodes, torrents, team_members, history, franchises
* [x] Разделение:
  * list-view / search → `TitleCardDTO` (param `"view": "card"`)
  * detail-view → `TitleDetailsDTO` (default, `"view": "full"`)
* [x] `TitleViewMode` enum (политика вместо boolean flag `compact`)
* [x] `_parse_view_mode()`: graceful fallback на `FULL` для неизвестных значений
* [x] Enricher CARD mode: пропускает per-episode N+1 запросы (watched loop, torrent download loop, team_members, history_records, franchises)

[0.3.8.41] branch: feature/0.3.8.41 | 4/24/26

---

## 🟢 DONE — Schedule / Providers (Unified pipeline)

**Цель:** не “умный контроллер под одного провайдера”, а общий pipeline через нормализованный `ScheduleItem`.

* [x] DTO/модель `ScheduleItemNormalized`
  * `provider_code`, `external_title_id`
  * `air_dt` (datetime tz-naive)
  * `episode_label`, `poster_url`, `title_url`
  * `raw` (fallback)
* [x] Парсер AniMedia → `ScheduleItemNormalized`
  * “Сегодня/Вчера/7-01-2026, 16:00” → datetime
* [x] Маппинг AniLiberty schedule → тот же формат
* [x] `schedule.sync` (через write-path!)
  * resolve `external_title_id → title_id` через `TitleProviderMap`
  * upsert schedule (resolved → upserted, missing → unresolved)
* [x] `schedule.get` = DB-only
* [x] Schedule порты: `IScheduleReadPort`, `IScheduleWritePort`, `IProviderScheduleSource`
* [x] `ScheduleController` (schedule_get / schedule_sync)
* [x] `SqlAlchemyScheduleReadPort` / `SqlAlchemyScheduleWritePort`
* [x] `AniMediaScheduleSource` (async → sync adapter, meta date parser)
* [x] `AniLibertyScheduleSource` (sync, day-by-day or all-week)
* [x] unit tests: handlers (7) + date parser (7) = 14 tests
* [x] `AniMediaProviderAdapter` — sync facade + async proxies (симметрично `AniLibertyProviderAdapter`)
* [x] Lazy enrich при открытии тайтла
  * `schedule.sync` param `fetch_unresolved: true`
  * для unresolved: `pipeline.fetch_and_process(provider_code, external_id)` → title в БД
  * retry upsert — новые тайтлы попадают в schedule
  * `ScheduleSyncResult.fetched_missing` — счётчик подтянутых

**Как сделано:**
- `backend/core/dto/schedule.py`: `ScheduleItemNormalized`, `ScheduleEntryDTO`, `ScheduleUpsertResult` (+ `unresolved_items`), `ScheduleSyncResult` (+ `fetched_missing`)
- `backend/core/ports/schedule_port.py`: 3 Protocol interfaces
- `backend/core/controllers/schedule_controller.py`: `ScheduleController` (+ `fetch_title_fn`, `fetch_unresolved`)
- `backend/infra/db/schedule_sqlalchemy.py`: DB read/write ports
- `backend/infra/providers/animedia_schedule_source.py`: wraps `AniMediaAdapter.get_new_titles()`
- `backend/infra/providers/aniliberty_schedule_source.py`: wraps `APIAdapter.get_schedule(day)`
- `backend/adapters/animedia_provider.py`: `AniMediaProviderAdapter` (sync + async proxy)
- `backend/bootstrap/providers_factory.py`: `ProvidersBuildResult`, `build_all()`
- Wired into `StandaloneBackend.schedule` с `fetch_title_fn`
- JSON ops: `schedule.get`, `schedule.sync` (+ `fetch_unresolved`)

[0.3.8.41] branch: feature/0.3.8.41 | 4/24/26

---

## 🟢 DONE — UI Prerequisites (History Write + Pagination)

**Цель:** закрыть все недостающие write-операции и метаданные пагинации перед разработкой UI.

* [x] `history.mark_watched` — отметить эпизод просмотренным / снять отметку
  * `title_id`, `episode_id?`, `is_watched`, `user_id`
  * ответ: `MarkWatchedResult(ok, title_id, episode_id, is_watched, error)`
* [x] `history.mark_all_watched` — отметить все эпизоды тайтла
  * `title_id`, `is_watched`, `episode_ids?` (subset), `user_id`
  * ответ: `MarkAllWatchedResult(ok, title_id, is_watched, episodes_affected, error)`
* [x] `history.set_need_to_see` — добавить/убрать из “хочу посмотреть”
  * `title_id`, `need_to_see`, `user_id`
  * ответ: `NeedToSeeResult(ok, title_id, need_to_see, error)`
* [x] Pagination metadata в `titles.search`:
  * `total_count` — общее число результатов
  * `has_more` — есть ли следующая страница
  * `offset`, `limit` — текущее окно
* [x] Port `IHistoryWritePort` (Protocol)
* [x] `HistoryController` (wraps port, typed Results)
* [x] `SqlAlchemyHistoryWritePort` (delegates to `db.save_watch_status` / `save_watch_all_episodes` / `save_need_to_see`)
* [x] `ITitlesPort.count_search_titles(query)` + реализация в infra + `TitlesController.count_titles()`
* [x] unit tests: history handlers (16) — все 3 операции, граничные случаи

**Как сделано:**
- `backend/core/dto/history.py`: `MarkWatchedResult`, `MarkAllWatchedResult`, `NeedToSeeResult`
- `backend/core/ports/history_write.py`: `IHistoryWritePort` Protocol
- `backend/core/controllers/history_controller.py`: `HistoryController`
- `backend/infra/db/history_write_sqlalchemy.py`: `SqlAlchemyHistoryWritePort`
- `backend/transport/json_tool/handlers.py`: handlers + HANDLERS dict (17 ops total)
- `tests/backend/test_json_handlers_history.py`: 16 tests

**Итого тестов:** 50 (было 41 → +16 history, +7 schedule были ранее)

[0.3.8.42] branch: feature/0.3.8.42 | 4/24/26

---

## 🟡 UI Targets — Desktop + Android TV

**Статус:** backend готов. UI разрабатывается отдельно.

### Целевые платформы

| Платформа | Язык / Фреймворк | Интеграция |
|-----------|-----------------|-----------|
| Desktop (Windows / Linux) | любой (не Python) | JSON-tool IPC → `stdin/stdout` |
| Android TV | любой (Kotlin / Compose TV) | JSON-tool через embedded binary или HTTP shim |

### Контракт UI ↔ Backend

```
UI process
  ↓ {“op”: “titles.search”, “params”: {“query”: “...”, “view”: “card”}}
backend_tool (stdin → stdout)
  ↑ {“ok”: true, “result”: {“titles”: [...], “total_count”: 42, “has_more”: true}}
```

### Доступные JSON-операции (17)

| Группа | Операции |
|--------|---------|
| titles | `titles.search`, `titles.get`, `titles.list_episodes`, `titles_ids.search` |
| streams | `streams.get` |
| playlists | `playlist.compose`, `playlist.compose_multi` |
| sync | `sync.fetch_and_process`, `sync.search_and_process`, `sync.search_external_ids`, `sync.fetch_payload` |
| update | `titles.update` |
| schedule | `schedule.get`, `schedule.sync` |
| history | `history.mark_watched`, `history.mark_all_watched`, `history.set_need_to_see` |

### Ключевые view-режимы

| `”view”` | DTO | Когда использовать |
|----------|-----|-------------------|
| `”card”` | `TitleCardDTO` | Списки, поиск, расписание |
| `”full”` | `TitleDetailsDTO` | Карточка тайтла, detail screen |

### Сборка backend как binary

```bash
pyinstaller backend_tool.spec  # → dist/backend_tool(.exe)
```

Бинарник принимает `--db <path>`, читает JSON из stdin, пишет JSON в stdout. Никакого сервера — UI сам запускает процесс.

---

## 🟢 FIXED — Bugs Found During Testing (UI + HTTP Server)

Обнаружены при тестировании нового Kotlin Multiplatform UI против HTTP-бэкенда.
Все 9 багов исправлены.

### Backend — Stream URLs

* [x] **#1 AniMedia: хост в stream URL отсутствует**
  * `_make_abs_stream(url, host_for_player)` в `transport/http/server.py`
  * `_normalize_episode()` принимает `host_for_player`, строит абсолютные HLS URL
  * `_normalize_title_details()` извлекает `host_for_player` из raw dict и передаёт в каждый эпизод

### Backend — Posters

* [x] **#2 Постеры не отображаются**
  * Добавлен endpoint `GET /poster/{title_id}` — отдаёт JPEG/PNG blob из таблицы `poster`
  * `_poster_url(d)` возвращает CDN URL если есть, иначе `/poster/{title_id}`
  * `AnimeRepository.resolveUrl()` в UI: относительный `/poster/…` → `baseUrl + path`
  * Coil3 (`coil-compose` + `coil-network-ktor3`) — async image loading на Desktop и Android

### Backend / UI — Sync

* [x] **#3 Нет возможности загрузить / синхронизировать тайтлы из провайдеров через UI**
  * `AnimeRepository.updateTitle(titleId)` вызывает backend op `titles.update`
  * `TitleViewModel.updateFromProvider()` + `UpdateState` sealed interface (Idle/Loading/Done/Error)
  * Кнопка Refresh на `TitleDetailScreen` с индикатором загрузки + Snackbar с результатом

### Docs / Build

* [x] **#4 Нет документации и скриптов для сборки и деплоя нового UI**
  * Создан `ui/README.md`: prerequisites, `./gradlew desktopRun`, MSI/DEB/DMG, Android APK, ADB install, keystore setup

* [x] **#5 Нет документации для сборки и деплоя нового backend**
  * Создан `backend/README_HTTP_BACKEND.md`: CLI args, systemd/Task Scheduler deploy, PyInstaller binary, API overview
  * ⚠️ Папка `make_bin/` не затронута

### UI — Player Settings

* [x] **#6 Кнопка Save настроек плеера не показывает результат**
  * `PlayerSettingsSectionDesktop.kt`: `var saved` state → CheckCircle + «Сохранено» с auto-dismiss через 2 сек

### UI — Missing Screens

* [x] **#7 Нет экрана списка тайтлов (titles list / browse)**
  * `SearchViewModel(repo, autoLoad = true)` — при старте автоматически загружает все тайтлы
  * `DesktopApp`: маршрут SEARCH использует `autoLoad = true` → полноценный Browse/Catalog

* [x] **#8 Нет экрана расписания (schedule list)**
  * `ScheduleViewModel` + `ScheduleScreen` (Desktop) + `TvScheduleScreen` (Android TV)
  * Расписание на 7 дней, группировка по дням недели с русскими названиями
  * Маршруты добавлены в `DesktopApp` и `TvApp`; кнопка «Расписание» на TV главном экране

### UI — Filters

* [x] **#9 Нет фильтрации / расширенного поиска**
  * `SearchFilters(year, genre, status, type)` + `isActive` computed property
  * Бэкенд: фильтры пробрасываются через весь стек (port → controller → handler)
  * `FilterPanel` на `SearchScreen`: год, жанр, статус, тип + кнопка «Сбросить»
  * `AnimatedVisibility` — панель сворачивается; иконка FilterList подсвечивается при активных фильтрах

---

## 🟡 TODO — Backend Provider Gaps / Runtime Assets

**Цель:** зафиксировать реальные пробелы после проверки HTTP-backend и UI. DONE-секции выше не считаем финальной приемкой provider-flow, пока эти пункты не проверены на живых сценариях AniLiberty / AniMedia.

### Runtime / deploy docs

* [x] Исправить `backend/README_HTTP_BACKEND.md`: добавлены `storage/`, `utils/`, `providers/` как обязательные runtime-директории; добавлено предупреждение о `WorkingDirectory` для systemd/Task Scheduler.
* [x] Созданы PyInstaller specs `make_bin/specs/backend_http.spec` и `make_bin/specs/backend_tool.spec`.
  * `backend_http.spec` — HTTP сервер (`server.py`), бандлит `storage/`, `utils/`, `providers/`, `backend/`, `config/`.
  * `backend_tool.spec` — JSON-tool CLI (`backend_tool.py`), тот же набор без FastAPI/uvicorn.
  * Обе сборки excludes Qt/kivy/scipy. `console=True` для обоих.
* [x] Добавлена fail-fast диагностика в `build_backend()` (`backend/bootstrap/standalone.py`):
  * Жёсткая проверка: директория родителя DB должна существовать → `RuntimeError`.
  * Мягкие предупреждения: если `storage`, `utils`, `providers` не импортируются → `logger.warning` с указанием текущего CWD.

### Posters / asset ingestion

* [x] Найдена `utils/downloads/poster_manager.py` — существующая утилита с background download/save threads.
* [x] Создан `backend/infra/poster/poster_job_adapter.py` — тонкий адаптер над `PosterManager`:
  * `_extract_poster_links()` собирает URLs из `posters.{size}.url` (AniLiberty) и `poster_path_*` полей (AniMedia).
  * Всегда скачивает под ключом `"medium"` (blob endpoint проверяет именно medium → small) для корректной работы с `/poster/{id}`.
  * `queue_posters_for_payload(title_id, payload)` — никогда не поднимает исключений, пишет только в лог.
* [x] `StorageProcessWritePort` получил опциональное поле `poster_job` — вызывает `_with_poster()` после каждого успешного `apply_provider_payload`. Точки: `title`, `title_full`, `episodes`, `torrents` modes.
* [x] `StandaloneBackend.__init__` строит `PosterJobAdapter(db, NetClient(cfg.network))` — подключён ко всем sync/update путям через write-port. Недоступность → тихий warning.
* [x] Сохранение идемпотентно: `PosterManager` скипает уже стоящие в очереди `(title_id, size_key)` пары; `save_poster` перезаписывает только если blob изменился.
* [x] **ROOT CAUSE FIX**: AniMedia хранит URL только в `posters.original`, `medium`/`small` — пустые `{}`.
  * **`TitleCardDTO`** не имел поля `poster_path_original` → `_poster_cdn()` никогда не видел URL AniMedia-тайтлов в list-view. Добавлено поле + заполнение в `_titles_card_return()`.
  * **`_poster_cdn()` в `server.py`**: добавлена проверка `poster_path_original` как третьего fallback. Немедленно исправляет все существующие тайтлы в БД без повторного sync.
  * **`process_titles()` в `storage/process.py`**: нормализация — `poster_path_medium` и `poster_path_small` заполняются из `original`, если собственные значения пусты. Исправляет будущие syncs.

### Poster read concurrency bug

* [x] Исправлена гонка при массовых параллельных `GET /poster/{title_id}` из БД.
  * `server.py`: endpoint теперь создаёт **request-local** `sessionmaker()` сессию вместо использования общего `backend._db.Session`. Blob читается как `bytes(raw)` внутри `with _SessionLocal() as session:` и возвращается до закрытия сессии.
* [ ] Добавить regression/load test: пачка параллельных запросов к `/poster/{title_id}` не должна давать transient 404/500 для существующих poster rows.

### AniLiberty schedule

* [x] Исправлена производительность `schedule.sync` для AniLiberty.
  * Корень проблемы: `APIAdapter._process_schedule_releases()` вызывал `_enrich_and_adapt(..., fetch_episodes=True, fetch_torrents=True, allow_network=True)` для **каждого** тайтла в расписании → O(N) сетевых запросов.
  * Добавлен `APIAdapter.get_schedule_light(day)` — делает 1 API call (`/schedule/now` или `/schedule/week`), затем адаптирует каждый релиз с `allow_network=False, fetch_episodes=False, fetch_torrents=False`. Возвращает тот же формат `[{'day': d, 'list': [...]}]`.
  * `AniLibertyScheduleSource._fetch_day()` теперь предпочитает `get_schedule_light` если он доступен, с fallback на `get_schedule` для старых адаптеров.
  * Результат: schedule.sync с 50 тайтлами: 1 сетевой запрос вместо 50.
* [ ] Проверить, что `schedule.get` возвращает обновлённое расписание AniLiberty после sync (live-тест).
* [ ] Добавить тесты на day/week API mapping, unresolved titles и retry после lazy fetch.

### Provider title fetch/update

* [ ] Реализовать/починить загрузку тайтла из AniLiberty по provider id / external id.
* [ ] Реализовать/починить загрузку тайтла из AniMedia по provider id / external id.
* [ ] Проверить общий контракт `sync.fetch_and_process` и `titles.update` для обоих providers: title metadata, episodes, provider_links, posters.
* [ ] Добавить integration smoke tests с фикстурами provider payloads.

### Title update bug — episode uuid conflict

* [x] Исправлен `UNIQUE constraint failed: episodes.uuid` в `storage/save.py::save_episode()`:
  * `"uuid"` добавлен в `protected` set — uuid существующего episode row больше никогда не перезаписывается значением из провайдера.
  * `data.get("uuid")` вместо `data["uuid"]` — корректная обработка эпизодов без uuid.
  * UUID fallback lookup теперь пропускается когда `episode_uuid is None` (иначе `filter_by(uuid=None)` матчил все NULL-uuid строки).
  * При вставке нового эпизода: если провайдерский uuid уже занят другой строкой — генерируется свежий `uuid4()` с warning в лог.
* [ ] Проверить стратегию identity/upsert для эпизодов: сопоставлять по стабильному provider key (provider code + external title id + episode number), а не только по `episode_id`.
* [ ] Добавить regression test на повторный `titles.update` AniLiberty для уже сохраненного тайтла: повторный update должен быть идемпотентным.

### AniMedia search/update bug — wrong query

* [x] Исправлен корневой сценарий: legacy DB rows хранят голый numeric id (`"2002"`) без `@@name`.
  * `TitlesUpdateController._pick_external_id_from_links()`: если `provider_code == "animedia"` и `"@@"` не в строке — автоматически строится токен `"<id>@@<name>"` из имени тайтла через `_fallback_query(t)`.
  * `AniMediaPayloadSource.fetch_payload_by_external_id()` уже умеет оба формата: `"id@@name"` и чистое имя; теперь компаунд-токен всегда доходит корректным.
* [x] Источник query в `titles.update` разделён: если есть `external_id` → передаётся в `fetch_payload_by_external_id`, иначе `_fallback_query(t)` (имя из БД) идёт в `query` fallback. Голый `title_id` (число) никогда не используется как search query.
* [ ] Добавить нормальный порядок fallback для AniMedia:
  * provider link / external id, если уже есть
  * точное название из БД
  * альтернативные названия/aliases
  * год/type как уточнение, если provider search поддерживает
* [ ] Добавить regression test: для тайтла без AniMedia provider link backend не должен дергать `amd.online` с `story=<local_title_id>`.

### AniMedia catalog/cache

* [ ] Реализовать отображение новых тайтлов AniMedia через существующий локальный cache-flow.
* [ ] Реализовать backend-операцию/путь для списка тайтлов AniMedia из локального кеша.
* [ ] Определить refresh policy/cache invalidation для AniMedia cache.
* [ ] Проверить UI browse/search сценарий: новые AniMedia titles видны без прямого API-list endpoint.

**Definition of Done:**

* README и build/deploy docs перечисляют все runtime-директории backend.
* Poster ingestion запускается из provider sync/update path и не блокирует основной read-flow.
* AniLiberty schedule реально обновляется из API и отображается через `schedule.get`.
* AniLiberty/AniMedia title fetch работает через общий backend pipeline.
* AniMedia catalog/list покрыт локальным cache-flow и виден в UI.

---

## 🟢 FIXED — UI External Web Player Links

* [x] `TitleViewModel.isWebPlayerUrl()` — эвристика: URL без `.m3u8`/`.mp4`/`.ts`/`.webm`/`/hls/` → web-player страница.
* [x] `PlayerLaunchEvent.OpenInBrowser(url)` — новый тип события для web URL.
* [x] `TitleViewModel.onEpisodeClick()` — эмитирует `OpenInBrowser` вместо `Launch` для web-player URL.
* [x] `AppSettings.browserCommand: String` — новая настройка (Desktop: команда браузера; Android: `""`, не используется).
* [x] `DesktopApp.launchBrowser()` — если `browserCommand` не пустой, запускает его; иначе — OS default (`cmd start` / `open` / `xdg-open`).
* [x] `SettingsScreen` + `PlayerSettingsSectionDesktop` — поле «Команда браузера» с auto-dismiss «Сохранено».
* [x] Android TV — `OpenInBrowser` обрабатывается через `Intent.ACTION_VIEW` с `FLAG_ACTIVITY_NEW_TASK`.

---

## 🟢 FIXED — UI Play Whole Title Playlist

* [x] `TitleViewModel.playAll()` — вызывает `repo.composeSinglePlaylist(titleId)`, эмитирует `PlayerLaunchEvent.Launch(playlistPath)`. mpv/vlc умеют открывать `.m3u8` playlist-файлы напрямую.
* [x] `TitleDetailScreen` — кнопка `PlayArrow` в TopAppBar (отображается только если `episodes.isNotEmpty()`), вызывает `onPlayAll`.
* [x] `DesktopApp` — `onPlayAll = vm::playAll` подключён; playlist path уходит в `launchPlayer()` так же как обычный stream URL.
* [x] Android TV — `onPlayAll = vm::playAll` подключён; playlist path передаётся в `onPlayStream` callback.
* [x] BUG: `vm::playAll` должен быть доступен только для HLS/direct media episodes.
  * `TitleDetailScreen`: кнопка PlayArrow теперь показывается только если `title.episodes.any { ep.hlsSd != null || ep.hlsHd != null || ep.hlsFhd != null }`.
  * Тайтлы с исключительно web-player URL (все `hls*` = null) кнопку не показывают.
* [x] BUG: общий playlist сохраняется/резолвится не в стабильной директории приложения.
  * `PlaylistManagerStorage.__init__` теперь вызывает `Path(playlists_dir).resolve()` — `playlist_path` всегда абсолютный.
  * `os.makedirs(abs_dir, exist_ok=True)` гарантирует существование директории при старте.
  * Backend возвращает абсолютный путь к `.m3u8` файлу; Desktop UI может открыть его без привязки к CWD.
* [ ] Follow-up: “начать с выбранного эпизода” — отдельный параметр смещения в `playlist.compose`.

---

## 🟢 FIXED — UI Title Details Back Navigation

* [x] Android TV (`TvApp.kt`): добавлен `BackHandler(enabled = true) { navController.popBackStack() }` перед `TitleDetailScreen`. Перехватывает remote/системный back до того, как Compose TV успевает перевести фокус (что выглядело как прокрутка вверх). Один нажатий back — один переход назад.
* Для Desktop (Escape) дополнительных изменений не требуется: LazyColumn не перехватывает Escape в Compose for Desktop.

---

## 🟡 TODO — UI Search White Screen Regression

**Симптом:** после возврата из detail screen в список можно получить белый экран. Воспроизводимость около 25%, похоже на race/focus/navigation issue вокруг SearchScreen и search input.

**Шаги воспроизведения:**

1. Ввести id тайтла.
2. Перейти в тайтл.
3. Вернуться в список.
4. Нажать на иконку лупы.
5. Двойным кликом нажать чуть выше поля “Поиск аниме”.

**Фактический результат:** белый экран.

**Ожидаемый результат:** экран поиска/списка остается живым, поле поиска получает/теряет фокус без навигационного сбоя и без пустого root content.

* [ ] Проверить `SearchScreen` focus/click handling после `popBackStack()` из detail.
* [ ] Проверить route state в `DesktopApp`/`TvApp`: после возврата search route не должен терять ViewModel/state/content.
* [ ] Проверить обработчики иконки лупы, filter panel/search field и двойного клика вне поля: не должно быть повторной навигации или очистки текущего route.
* [x] Добавлен defensive UI state: `SearchScreen` теперь показывает «Введите запрос для поиска» (пустой query) или «По запросу «…» ничего не найдено» вместо пустого LazyVerticalGrid → белый экран устранён.
* [ ] Добавить manual regression checklist: выполнить шаги 10-20 раз, белого экрана быть не должно.

---

## 🟡 TODO — UI Title State / Ratings / Torrents

**Цель:** закрыть недостающие user-state и title metadata сценарии: просмотренность, рейтинг, избранное, франшизы, торренты и локальное воспроизведение должны быть видны в UI и корректно сохраняться в backend.

### Watch history / watched state bug

* [x] Исправить bulk mark-watched для тайтла: отметка “серии просмотрены” теперь сохраняется при `episode_ids=None`.
  * Логи: `ERROR:storage.save:Invalid episode_ids provided for bulk update.`
  * Логи: `BULK Error saving watch status for user_id 42, title_id 10175, episode_ids None: Episode IDs must be a non-empty list.`
  * `SaveManager.save_watch_all_episodes()` теперь резолвит `episode_ids=None` в список всех episode rows тайтла и возвращает реальный affected count.
  * `SqlAlchemyHistoryWritePort.mark_all_watched()` возвращает count из storage, а не `0` при `episode_ids=None`.
* [x] Добавлен regression test: `test_history_storage.py` проверяет, что `episode_ids=None` помечает все эпизоды тайтла, а явный `[]` остается validation error.
* [x] Отображать title metadata на detail screen одним блоком: просмотренность из `history`, рейтинг и франшизы.
  * `server.py`: HTTP UI-normalizer теперь пропускает `ratings`, `franchises`, `all_episodes_watched`, `watched_episode_count`.
  * `TitleDetailsDto.kt`: добавлены `RatingDto`, `FranchiseDto`, `allEpisodesWatched`, `watchedEpisodeCount`.
  * `TitleDetailScreen.kt`: добавлен metadata block “Просмотр / Рейтинг / Франшизы”.
  * Проверено: `:composeApp:compileKotlinDesktop` проходит.
* [x] Исправлена агрегация “все серии просмотрены”: `get_all_episodes_watched_status()` теперь сравнивает количество watched episode rows с реальным числом эпизодов тайтла, а не только проверяет существующие history-записи.
* [x] Detail screen показывает три понятных состояния просмотра:
  * `Тайтл не просмотрен`
  * `Тайтл просмотрен частично (просмотрено N серий)`
  * `Тайтл просмотрен`

### Torrents

* [ ] Отображать список торрентов в detail screen.
* [ ] Добавить настройку пути до torrent-клиента в UI settings.
* [ ] При выборе торрента сохранять `.torrent` meta file в папку `torrents/` и открывать его выбранным torrent-клиентом.
* [ ] Backend/UI contract должен возвращать понятный результат: путь к сохраненному `.torrent`, имя торрента, размер/качество, ошибки сохранения/запуска клиента.

### Local downloaded video playback

* [ ] Добавить возможность смотреть локальное видео, если файл уже скачан.
* [ ] Определить источник local path: из torrent/download metadata, отдельной таблицы или сканирования download directory.
* [ ] В UI отдавать приоритет локальному файлу, если он доступен, с fallback на stream URL.

### Immediate list tile state updates

* [x] `TitleCardDTO` и HTTP normalizer теперь пропускают `rating_name`, `rating_value`, `is_watched`, `all_episodes_watched`, `need_to_see`.
* [x] `TitleCard` отображает отдельные бейджи рейтинга, просмотренности и избранного.
* [x] Desktop catalog делает targeted refresh после возврата из detail screen, чтобы плитка подтягивала новый watched/favorite/rating state.
* [ ] Синхронизировать detail state и list state без reload search route: изменение на detail screen должно отражаться в `TitleCardDTO`/локальном UI cache.
* [ ] Добавить optimistic update или targeted reload по `title_id`; при ошибке backend откатывать UI state и показывать feedback.

**Definition of Done:**

* Mark-all-watched работает для всего тайтла и не падает при `episode_ids=None`.
* Detail screen показывает watched/history, rating, franchises и torrents.
* Torrent-клиент настраивается, `.torrent` сохраняется в `torrents/`, запуск клиента дает понятный feedback.
* Если локальный видеофайл доступен, его можно открыть из UI.
* Плитки списка сразу отражают rating/watched/favorite изменения.

---

## 🟡 Combined Titles (Preview → Job)

**Цель:** подготовить “один тайтл — много источников” без спешки с миграциями: сначала отладка правил через preview,
потом отдельный job для записи результата.

### Planned

* [ ] `titles.combine.preview`
  * вход: `title_id` или `code`
  * выход:
    * кандидаты `title_ids  `
    * `match_reason` (code_norm / name_year_type / etc)
    * “как бы выглядел комбинированный DTO” (минимально)
* [ ] Нормализация code
  * `normalized_code("one-punch-man-3nd-season") -> "one-punch-man-3"`
  * правила: убрать `-season`, исправить `3nd/3rd`, убрать `part/cour`, etc.
* [ ] Fallback-матчинг:
  * `norm(name_en)+year+type`
  * `norm(name_ru)+year+type`

Потом (когда правила проверены):

* [ ] `job: titles.combine.apply` — пишет cluster-результат в БД (новая таблица/вьюха)

---

## 🟡 Асинхронные задачи

* [ ] Event / Job abstraction
* [ ] Poster download / resize jobs
* [ ] Cache warmup
* [ ] CLI-friendly utilities

---

## 🟡 Инфраструктура (опционально)

* [ ] Read-only cache
* [ ] Metrics / debug
* [ ] Web API поверх backend
* [ ] Документация API

---

## 🧱 Принципы, которые нельзя нарушать

* ❌ Контроллер ≠ БД
* ❌ ORM наружу
* ❌ Shared state
* ✅ Ports everywhere
* ✅ Узкие batched запросы
* ✅ Явные DTO

---

## 🧭 Как пользоваться roadmap

* **Backend_TLDR.md** → что есть сейчас
* **backend_roadmap.md** → что делать дальше
* **anime_player_app_roadmap.md** → история проекта

---

## 🔒 Точка фиксации

> Backend готов к дальнейшему развитию
> без архитектурных изменений.


