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


