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
* [x] Добавить тесты на day/week API mapping, unresolved titles и retry после lazy fetch.
  * `tests/backend/test_schedule_controller.py` (22 tests): day/week forwarding, empty source, partial resolve, unresolved counters, ok flag, unknown provider, source exception, fetch_unresolved retry flow, partial fetch, flaky fn, no double-upsert when all fail.

### Provider title fetch/update

* [x] Исправлен критический баг в `StorageProcessWritePort.apply_provider_payload`:
  * `process_titles()` возвращает `(ok: bool, title_id: int)` tuple, не dict.
    До фикса `title_id` никогда не извлекался → `result.title_id = None` всегда.
  * Добавлен `_unpack_process_titles()` — обрабатывает tuple / dict / scalar.
  * `title_id` инжектируется в shallow-copy payload перед вызовом
    `process_episodes` / `process_torrents` — иначе FK в БД был NULL.
  * При падении `process_titles` — `process_episodes` не вызывается.
  * Payload вызывающего не мутируется.
* [x] Добавлены smoke tests `tests/backend/test_provider_integration.py` (24 total):
  * 7 unit — `_unpack_process_titles` helper.
  * 14 behavioural — `StubStorage` без реальной БД (AniLiberty + AniMedia payloads).
  * 3 real-DB — пропускаются если SQLAlchemy не импортируется; запускаются на корректном окружении.
* [x] Исправлен `FakeTitlesController` в `tests/conftest.py`:
  * Добавлены `year/genre/status_filter/type_filter` kwargs в `titles_search` и `count_titles`.
  * Устранены 2 pre-existing test failures.
* [ ] Проверить контракт `sync.fetch_and_process` / `titles.update` end-to-end на живом AniLiberty (live test).
* [ ] Добавить regression test: повторный `titles.update` AniLiberty идемпотентен (поверх real-DB smoke).

### Provider update jobs / completion events

**Проблема:** AniLiberty обновляется быстро через API, а AniMedia медленно через `httpx + BeautifulSoup`. Увеличение timeout — временная мера, а не нормальный UX/архитектура.

* [x] Заменить долгий синхронный `titles.update` request на job-flow:
  * `titles.update.start` → возвращает `job_id` сразу (daemon thread + asyncio.run).
  * `jobs.get` → возвращает `queued/running/done/error`, started_at, finished_at, progress, result.
  * `JobStore` — thread-safe in-memory registry (`backend/core/jobs/job_store.py`).
  * `titles.update` старый sync-handler сохранён — используется для JSON-tool single-shot.
  * `backend.jobs = JobStore()` добавлен в `StandaloneBackend` и `FakeBackend`.
  * 25 tests: `TestJobStore` (9), `TestTitlesUpdateStart` (8), `TestJobsGet` (6), `TestJobError` (1) + failure path.
* [ ] UI detail screen должен запускать update job, показывать progress/spinner и polling status до `done/error`, не удерживая один HTTP request.
* [ ] Для AniMedia показывать понятные стадии: search page fetched, title page parsed, vlnk resolved, payload saved, posters queued.
* [ ] Добавить cancel/ignore-stale behavior: если пользователь ушёл с detail screen, update может завершиться в фоне, но UI не должен падать или зависать.

### Title update bug — episode uuid conflict

* [x] Исправлен `UNIQUE constraint failed: episodes.uuid` в `storage/save.py::save_episode()`:
  * `"uuid"` добавлен в `protected` set — uuid существующего episode row больше никогда не перезаписывается значением из провайдера.
  * `data.get("uuid")` вместо `data["uuid"]` — корректная обработка эпизодов без uuid.
  * UUID fallback lookup теперь пропускается когда `episode_uuid is None` (иначе `filter_by(uuid=None)` матчил все NULL-uuid строки).
  * При вставке нового эпизода: если провайдерский uuid уже занят другой строкой — генерируется свежий `uuid4()` с warning в лог.
* [x] Проверить стратегию identity/upsert для эпизодов: сопоставлять по стабильному provider key (provider code + external title id + episode number), а не только по `episode_id`.
  * `tests/backend/test_episode_upsert.py` (22 tests): verifies (title_id, episode_number) natural key, both list/dict player.list formats, HLS mapping, skips-to-JSON, uuid forward, created_timestamp conversion, idempotency.
* [ ] Добавить regression test на повторный `titles.update` AniLiberty для уже сохраненного тайтла: повторный update должен быть идемпотентным.

### AniMedia search/update bug — wrong query

* [x] Исправлен корневой сценарий: legacy DB rows хранят голый numeric id (`"2002"`) без `@@name`.
  * `TitlesUpdateController._pick_external_id_from_links()`: если `provider_code == "animedia"` и `"@@"` не в строке — автоматически строится токен `"<id>@@<name>"` из имени тайтла через `_fallback_query(t)`.
  * `AniMediaPayloadSource.fetch_payload_by_external_id()` уже умеет оба формата: `"id@@name"` и чистое имя; теперь компаунд-токен всегда доходит корректным.
* [x] Источник query в `titles.update` разделён: если есть `external_id` → передаётся в `fetch_payload_by_external_id`, иначе `_fallback_query(t)` (имя из БД) идёт в `query` fallback. Голый `title_id` (число) никогда не используется как search query.
* [x] Добавить нормальный порядок fallback для AniMedia:
  * provider link / external id, если уже есть → `_pick_external_id_from_links`
  * точное название из БД → `name_en` → `name_ru` → `code`
  * альтернативные названия → `alternative_name` (добавлено в `_fallback_query`)
  * год/type как уточнение — не реализовано (AniMedia search не поддерживает structured filters)
* [x] Добавить regression test: для тайтла без AniMedia provider link backend не должен дергать `amd.online` с `story=<local_title_id>`.
  * `tests/backend/test_titles_update_controller.py` (25 tests): unit tests for `_pick_external_id_from_links`, `_fallback_query`, and end-to-end `update_titles` routing — covers no-link name-query, legacy bare-id compound rebuild, explicit vs resolved provider_code.

* [x] AniMedia episodes hot reload: `titles.update` / `sync.fetch_and_process` accept `force_refresh=true`.
  * Only the matching `temp/am_vlink_cache.json` item is invalidated; schedule/all-title caches remain untouched.
  * Detail screen exposes a separate force-refresh action for AniMedia-linked titles.

### AniMedia catalog/cache

Этот блок теперь разделён на уже сделанную schedule/feed-часть и оставшуюся работу по отдельному каталогу.

* [x] Отображать AniMedia new-title/feed items в schedule UI через существующий локальный cache-flow.
  * Refresh расписания обновляет provider cache и отдаёт provider-only lightweight items.
  * Элементы, уже связанные с локальными DB title, открывают detail; unresolved элементы показывают явное действие загрузки.
* [x] Не вызывать полный AniMedia `get_by_title()` при рендере schedule/feed.
  * Полная загрузка AniMedia остаётся явной: выбранный item load/update action.
* [x] Добавить отдельную backend-операцию/путь для полного lightweight-каталога AniMedia из локального кеша.
  * Целевой источник: provider `get_all_titles(limit/page)` / `am_all_titles_cache.json`.
  * Реализовано через `provider.catalog`: отдаёт list-safe provider items без per-item `get_by_title()`.
* [x] Определить refresh policy/cache invalidation для AniMedia catalog cache.
  * Первый срез cache-first; кнопка «Загрузить еще» двигает catalog cache через `load_more_titles()`.
* [x] Добавить отдельный UI flow «показать все тайтлы AniMedia» с фильтрами и de-duplication с DB titles.
  * `AniMediaCatalogScreen`: поиск, фильтр `Все / В базе / Не загружены`, явная загрузка выбранного тайтла.

**Definition of Done:**

* README и build/deploy docs перечисляют все code/runtime и mutable data директории backend.
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

## 🟡 TODO — UI Catalog / Title List Layout

**Симптом:** на полноэкранном desktop layout плитки тайтлов выглядят странно: фиксированный размер карточки и фиксированное число колонок плохо используют ширину окна, появляется ощущение пустого/случайного пространства.

* [x] Переработать `SearchScreen` title list layout под adaptive grid:
  * `SearchScreen` uses `GridCells.Adaptive(minSize = 150.dp)` and stable `TitleCard(width=150, height=225)`.
  * Follow-up visual QA still lives below as a manual check item.
* [ ] Добавить режим плотности/представления:
  * poster grid для визуального browse;
  * compact list/table для внутреннего поиска по `title_id`, provider, status, rating.
* [ ] Улучшить содержимое плитки:
  * не перегружать постер, но аккуратно показывать rating/watched/favorite;
  * решить, где показывать `title_id` и provider: на плитке, в tooltip/secondary line или только в compact list.
* [ ] Проверить readability длинных названий: max lines, gradient overlay, размер текста, отсутствие наложений с badges.
* [ ] Сделать manual visual QA: 1280x800, full HD, ultrawide/fullscreen.

---

## 🟡 TODO — UI Title State / Ratings / Torrents

**Цель:** закрыть недостающие user-state и title metadata сценарии: просмотренность, рейтинг, избранное, франшизы, торренты и локальное воспроизведение должны быть видны в UI и корректно сохраняться в backend.

### Приоритет ближайших мелких правок

* [x] Если на detail screen отображаются франшизы, элементы франшизы должны быть переходами в соответствующий тайтл.
  * При наличии `title_id` открывать detail screen этого тайтла.
  * Если связанный тайтл не найден/не загружен, показывать элемент без перехода или с понятным disabled-состоянием.
* [x] Вернуть полезные metadata из legacy UI: озвучка и перевод, если сведения о команде есть в данных тайтла.
  * Detail screen: показывать отдельные строки/чипы `Озвучка` и `Перевод` только при наличии значений.
  * Проверить mapping `team_members`: роли должны нормально группироваться и не смешиваться с остальной технической metadata.
* [x] На плитке тайтла стабильно показывать количество эпизодов, если оно известно.
  * Источник: `episodes_total` / фактический размер episodes list / агрегированное поле из backend, без N+1 для card-view.
  * Если количество неизвестно, не показывать пустой или вводящий в заблуждение badge.
* [x] Добавить очистку в текстовые поля desktop/common UI.
  * Основной поиск, provider-load уточнение, фильтры поиска, AniMedia catalog, schedule search, backend URL и desktop player/browser commands используют общий clear action.
* [x] Отображать дополнительный внешний рейтинг из таблицы `ratings`: `name_external: score_external`.
  * Detail screen: внешний рейтинг показывается вместе с основным рейтингом.
  * Title card / главный экран: внешний рейтинг показывается числом без названия источника, бейджи переносятся строками по доступной ширине карточки.
  * Главные подборки в пустом поиске переносят карточки строками по ширине окна, а не уходят в горизонтальный скролл.
* [ ] После этого взять торренты; перед запуском torrent-клиента сначала нужна настройка пути до клиента.

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

### Ratings

* [x] Отображать дополнительный внешний рейтинг из таблицы `ratings`: `name_external: score_external`.
  * Detail screen: внешний рейтинг показывается рядом с основным `rating_name: rating_value`.
  * Title card: внешний рейтинг показывается на плитке числом без названия источника, бейджи переносятся строками при нехватке ширины.
  * Mapping: `RatingDto.nameExternal` / `RatingDto.scoreExternal` протянуты в card DTO через HTTP normalizer.
* [ ] Добавить возможность выставлять рейтинг `CMERS` из UI.
  * Backend: добавить write operation вроде `ratings.set` / `title.rating.set` с параметрами `title_id`, `rating_value`, `rating_name=CMERS`, `user_id?`.
  * Storage: использовать/проверить `save_ratings()` как upsert, чтобы повторная установка обновляла существующую строку `ratings`.
  * UI detail screen: добавить компактный контрол выбора рейтинга CMERS.
  * UI list/card: после установки рейтинга сразу обновлять бейдж рейтинга без ручного refresh.
  * Validation: определить допустимую шкалу CMERS (например 0-10 или 1-10) и явно показать/проверять её в UI/backend.

### Title technical metadata

* [ ] Отображать `title_id` в UI.
  * [x] Detail screen: показывать явно, чтобы можно было быстро сверить/скопировать внутренний ID.
  * Search/list: решить, нужен ли компактный ID на плитке или только в detail.
* [ ] Отображать provider name / provider code в UI.
  * Проверить, что `provider_links` или enriched scalar `provider` доходят до `TitleDetailsDTO` и `TitleCardDTO`.
  * [x] Detail screen: показывать источник данных рядом с metadata.
* [ ] Отображать данные о студии в UI.
  * Проверить mapping `production_studio` / scalar `studio` из backend DTO.
  * Detail screen: показывать название студии отдельной строкой.
* [ ] Отображать данные о команде в UI.
  * Проверить mapping `team_members` / scalar `team` из backend DTO.
  * Detail screen: показывать роли/участников компактно, без перегруза карточки.
  * Legacy-compatible группировки: отдельно показывать озвучку и перевод, когда эти роли присутствуют.

### Aggregated title lists / navigation

* [ ] Добавить агрегированные списки тайтлов:
  * по жанрам;
  * по членам команды;
  * по статусам;
  * по году;
  * по франшизе.
* [x] Переходы в агрегированные списки должны быть доступны из detail screen тайтла.
  * [x] Жанр в detail → список тайтлов этого жанра.
  * [x] Участник команды в detail → список тайтлов с этим участником/ролью.
  * [x] Статус в detail → список тайтлов с этим статусом.
  * [x] Год в detail → список тайтлов этого года.
  * [x] Франшиза в detail → список тайтлов этой франшизы.
* [x] Backend/API: решить, достаточно ли расширить `titles.search` фильтрами или нужен отдельный endpoint для facet/list navigation.
  * Реализовано через расширение `titles.search`: `year`, `genre`, `status_filter`, `team_member_id` / `team_member`, `franchise_id`.
  * Для team/franchise используется id-based фильтр, когда ID есть, чтобы не зависеть от текста имени.
* [x] UI: у каждого списка должен быть понятный заголовок и возможность вернуться к исходному тайтлу без потери контекста.
  * Detail screen использует action chips вместо синих текстовых ссылок.

### Franchise discovery

* [ ] Подумать над экраном/разделом “Все франшизы” с главного экрана.
  * Это должен быть список франшиз, а не список тайтлов.
  * Нужно решить, какой постер показывать у франшизы: первый тайтл по хронологии, самый популярный/рейтинговый, последний обновленный или явно выбранный representative title.
  * При открытии франшизы показывать список всех тайтлов франшизы с переходами в detail.
  * Если у франшизы нет подходящего постера, использовать аккуратный текстовый/placeholder вариант, а не случайную картинку.

### Torrents

* [x] Отображать список торрентов в detail screen.
  * HTTP normalizer отдаёт `torrents` в `titles.get`.
  * KMP detail screen показывает качество, диапазон серий, размер, filename/hash и seed/leech/download stats.
* [ ] Добавить настройку пути до torrent-клиента в UI settings.
  * Desktop: хранить путь до executable/команды клиента и валидировать, что путь доступен перед запуском.
  * Android TV: оставить запуск торрентов disabled/unsupported, пока не определён системный сценарий.
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
* Отображаемые франшизы ведут в соответствующий тайтл, если связанный `title_id` доступен.
* Torrent-клиент настраивается, `.torrent` сохраняется в `torrents/`, запуск клиента дает понятный feedback.
* Если локальный видеофайл доступен, его можно открыть из UI.
* Плитки списка сразу отражают rating/watched/favorite изменения.

---

## 🟡 TODO — Provider Catalog / Discovery

**Problem:** title discovery/add flows should be driven by provider capabilities, not hardcoded provider names. AniMedia "new titles" / "all titles" currently can become too slow if the UI path triggers full `get_by_title()` loading for every item, while AniLiberty has API-backed schedule/catalog/random flows.

### Product scope / sequencing

* Current priority: stabilize backend contracts and bring the KMP UI to a usable pre-production level with existing providers.
* New providers are a later enrichment phase, after backend/provider contracts and core frontend workflows are stable enough for daily use.
* Provider expansion should focus on enriching metadata and availability, not forcing UI-specific branches.

### Current provider capabilities snapshot

| Capability | AniLiberty | AniMedia | Notes |
|---|---|---|---|
| Load random title | yes | no | AniLiberty provider has random release endpoint; backend/UI exposure needs verification. |
| Load by name/search | yes | yes | Covered by provider pipeline: `sync.search_and_process` / `sync.fetch_and_process` depending on input. |
| Load by external id | yes | yes | AniMedia may require compound token `external_id@@title` when bare id is not enough. |
| Load/update existing title | yes | yes | `titles.update`; AniMedia is slower because it uses HTML parsing. |
| Schedule sync | yes | yes | AniLiberty is day/week API; AniMedia is feed/cache with date/meta labels. |
| Lightweight catalog | likely | yes | AniMedia has cache-backed `get_all_titles`; AniLiberty appears to have `get_catalog_releases`, but backend usage needs verification. |

* [ ] Add a provider capability contract for UI actions.
  * Example capabilities: `search`, `fetch_by_external_id`, `random`, `schedule`, `catalog`, `update_existing`.
  * UI should render "add title" actions from capabilities instead of special-casing AniMedia/AniLiberty.
  * Future providers should plug into the same capability model without new screen-specific branches.

### Backend contract

Runtime/data layout currently assumed by the backend:

* Code/runtime imports live alongside the backend process: `backend/`, `storage/`, `utils/`, `providers/`.
* Mutable runtime dirs live under the same runtime root for now: `config/`, `db/`, `playlists/`, `torrents/`, `temp/`, `logs/`.
* AniMedia cache files live in backend runtime `temp/`:
  * Schedule/new titles cache: `temp/am_schedule_cache.json`
  * Lightweight all-titles cache: `temp/am_all_titles_cache.json`
  * Title episode/vlink cache: `temp/am_vlink_cache.json`
* [ ] Follow-up: decide whether mutable runtime dirs should be grouped under a single data root next to `db/` instead of living directly beside code/runtime imports.

* [x] Add a lightweight AniMedia discovery/list contract.
  * `get_new_titles(max_titles)` is used for the "new titles" feed.
  * `get_all_titles(limit/page)` is used for the wider AniMedia catalog; the provider already returns a minimal batch (about 50 titles).
  * The response should expose only list-safe data: provider code, external id, title/name, poster URL, page/title URL, meta/date label, episode label, and optional mapped `title_id`.
  * These list operations must not call `get_by_title()` per item.
  * Implemented as backend op `provider.catalog`.
* [x] Resolve already-loaded titles in batch through `TitleProviderMap`.
  * If AniMedia minimal item maps to an existing DB title, merge/attach the corresponding `TitleCardDTO`.
  * If the item is not loaded yet, show it as a lightweight provider item and offer an explicit load/update action.
  * [x] Schedule provider-only items now expose mapped `title_id` when available; mapped items open detail, unresolved items show an explicit load action via `sync.fetch_and_process`.
  * [x] Catalog provider-only items expose mapped `title_id` when available; unresolved items show an explicit load action via `sync.fetch_and_process`.
  * De-duplicate loaded DB titles and AniMedia cache entries by provider external id first; normalized title/code fallback remains a future hardening item.
* [x] Keep full AniMedia loading explicit.
  * `get_by_title()` is used only for title detail, manual update, or a background job that loads missing/selected titles.
  * Follow-up: add/adjust job flow for "load/update AniMedia title" so slow HTML parsing is visible as a job, not hidden inside list refresh.
* [ ] Keep AniLiberty weekly schedule and AniMedia feed separate in backend semantics.
  * AniLiberty has real day-based schedule.
  * AniMedia is a feed/catalog with optional meta date, not a strict day schedule.

### UI

* [x] Schedule screen can show one combined list, but entries must keep provider-specific meaning.
  * AniLiberty entries: grouped/filtered by day.
  * AniMedia entries: shown as a feed/new-titles block or unified list row with provider/source labels.
* [x] Add basic filters to the schedule screen.
  * [x] Provider: all / AniLiberty / AniMedia.
  * [x] Text search by title.
  * [x] Loaded/unloaded state for AniMedia lightweight items.
  * [ ] Optional year/type/status filters when the lightweight provider item or mapped DB title has those fields.
* [x] Add "show all AniMedia titles" action/screen.
  * Display lightweight AniMedia catalog from `get_all_titles`.
  * Mix with already-loaded DB titles without duplicates.
  * Add filters for AniMedia catalog: text query, loaded/unloaded, year/type/status when available, provider/source.
* [ ] Main screen: normalize title discovery/add controls.
  * [x] Existing DB search/browse использует главное поле поиска.
  * [x] Empty search result может явно загрузить запрос из AniLiberty или AniMedia через `sync.search_and_process`.
  * [x] Provider controls поддерживают уточнённый provider query, fallback по external id и загрузку до 3 кандидатов.
  * [x] Provider controls доступны не только в empty-state, но и при частичных DB-результатах по непустому запросу.
  * [ ] Заменить hardcoded provider buttons на provider capability metadata, когда backend начнёт это отдавать.
  * [x] Добавить кнопку случайного тайтла AniLiberty через `sync.random_and_process`.
  * [x] Добавить отдельный "load by external id" affordance, если обычный текстовый поиск станет неоднозначным.
* [x] Main screen: add a compact "recently loaded titles" block.
  * Use DB-loaded titles, sorted by creation/update timestamp.
  * `titles.search` supports `sort=recent`; UI shows a small `Недавно загружено` rail on the main screen.
  * [ ] Follow-up: add a link/action to the full catalog/search view for more.
* [x] Main screen: add a separate `need_to_see` block.
  * Reuse `TitleCardDTO` state so favorite/watched/rating badges stay consistent with the main catalog.
  * `titles.search` supports `need_to_see=true` for request-local watchlist queries.

---

## 🟡 FUTURE — Full Playback / Mini Browser Layer

**Current scope:** KMP UI is intentionally a light client for pre-production. It can launch external players/browsers and manage catalog/detail/schedule/history flows, but it does not yet own video playback or embedded web playback.

**Later target:** add a full playback layer on top of the stabilized backend/UI.

* [ ] Integrated video player.
  * HLS/direct stream playback.
  * Playlist playback.
  * Opening from selected episode or continuing from last watched episode.
  * Skip opening/ending/credits awareness.
  * Screenshot saving.
  * Subtitle support.
  * Local downloaded video playback.
* [ ] Embedded mini browser for provider web-player links.
  * Open non-HLS web-player pages inside the app.
  * Keep fallback to external browser when embedded browser is unavailable.
* [ ] Stream proxy/caching layer.
  * Route playback through local proxy when needed.
  * Cache/normalize stream access.
  * Preserve provider-specific headers/redirect behaviour where required.
* [ ] Playback state integration.
  * Persist watch progress.
  * Update watched/title state immediately in UI.
  * Keep playlists, screenshots, subtitles, and local files under stable runtime data directories.

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

## 🟡 TODO — UI Build / Tooling

### Gradle 9.0 deprecation warnings

**Симптом:** сборка завершается с предупреждением:
```
Deprecated Gradle features were used in this build,
making it incompatible with Gradle 9.0.
```

**Текущие версии:**

| Компонент | Версия |
|-----------|--------|
| Gradle | 8.9 (`gradle-wrapper.properties`) |
| AGP (Android Gradle Plugin) | 8.5.2 |
| Kotlin / KMP | 2.0.21 |
| Compose Multiplatform | 1.7.1 |
| `navigation-compose` | 2.8.0-alpha10 |

**Вероятные источники предупреждений:**

* **AGP 8.5.2** — основной виновник. AGP 8.5.x использует `Project.getConvention()` и другие API, удалённые в Gradle 9.0. Сборка будет ломаться при переходе на Gradle 9.0.
* **`enableFeaturePreview("TYPESAFE_PROJECT_ACCESSORS")`** в `settings.gradle.kts` — функциональность стала стабильной в Gradle 8.x; сама строка `enableFeaturePreview` может генерировать предупреждение о том, что preview больше не нужен.
* **`navigation-compose = "2.8.0-alpha10"`** — alpha-зависимость; следует перейти на стабильный релиз.

**Шаги фикса:**

* [ ] Запустить `./gradlew :composeApp:assembleDebug --warning-mode all 2>&1 | grep -i deprecat` — увидеть точный список предупреждений со стек-трейсом.
* [ ] Обновить AGP с `8.5.2` до последней стабильной, совместимой с Gradle 8.9 (рекомендуется `8.7.x` или `8.8.x`). Обновить в `libs.versions.toml`: `agp = "8.7.3"` (или актуальный).
* [ ] Удалить `enableFeaturePreview("TYPESAFE_PROJECT_ACCESSORS")` из `settings.gradle.kts` если Gradle сообщает, что оно устарело.
* [ ] Обновить `navigation-compose` с `2.8.0-alpha10` до стабильного релиза (`2.8.x` stable).
* [ ] Перепроверить сборку: `./gradlew :composeApp:compileKotlinDesktop :composeApp:assembleDebug` — должно завершаться без deprecation warnings.
* [ ] Опционально: обновить Gradle wrapper с `8.9` до `8.12` (последний стабильный), чтобы получить поддержку новых AGP/KMP версий.

**Риск без фикса:** при обновлении Gradle до 9.0 (например, через auto-update в Android Studio) сборка сломается без предупреждения.

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


