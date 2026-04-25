## v0.3.8.45 — Write-Path Correctness + Job-Flow + Test Coverage

**Дата:** 2026-04-26
**Статус:** stable

Пять независимых изменений: критический фикс write-path, верификация episode upsert стратегии, регрессионные тесты для AniMedia query routing, тесты для ScheduleController, и новая job-flow система для неблокирующего `titles.update`.

---

### 1. Критический фикс: `StorageProcessWritePort` — title_id из tuple

**Симптом:** после успешного `process_titles()` episodes и torrents сохранялись с `title_id = NULL`, постер никогда не ставился в очередь.

**Корень:** `ProcessManager.process_titles()` возвращает `(ok: bool, title_id: int)` — tuple, не dict. `StorageProcessWritePort` не извлекал `title_id` из него.

**Фикс (`backend/infra/db/process_write_port_storage.py`):**

- Добавлен `_unpack_process_titles(res)` — обрабатывает tuple / dict / scalar fallback.
- `title_id` инжектируется в shallow-copy payload перед вызовом `process_episodes` / `process_torrents` — иначе FK в БД был NULL.
- При падении `process_titles` → `process_episodes` не вызывается.
- `ok_flag` из tuple корректно проставляется в `ApplyProviderPayloadResult.ok`.
- Payload вызывающего не мутируется.

---

### 2. Episode upsert — верификация стратегии identity

Зафиксирована и протестирована стратегия upsert эпизодов:

- **Natural key:** `(title_id, episode_number)` — стабильный provider key, не зависит от `uuid`.
- Верифицированы оба формата `player.list`: AniLiberty (Python list) и AniMedia (dict `{"1": {...}, "2": {...}}`).
- Эпизоды без ключа `hls` (pending/unreleased) пропускаются.
- `skips` сериализуется в JSON-строки.
- `created_timestamp` (unix float) → `datetime(tz=utc)`, `0` → epoch.
- `process_episodes` идемпотентен: повторный вызов с тем же payload всегда даёт тот же count `save_episode` вызовов.

---

### 3. AniMedia: query routing и fallback order

**Регрессия (`TitlesUpdateController`):**

- Тайтл без AniMedia provider link не должен уходить в adapter с `query=<local_title_id>` (баг: `story=2002` в URL).
- Фикс уже был в коде; добавлены тесты-регрессоры, которые это гарантируют навсегда.

**Дополнение — `_fallback_query` теперь проверяет `alternative_name`:**

Порядок: `name_en` → `name_ru` → `code` → `alternative_name` → dict `names` → `name`. Numeric `title_id` никогда не возвращается.

**Legacy bare-id rebuild:**

`"2002"` (без `@@`) → автоматически `"2002@@One Punch Man"` через `_fallback_query`. Дальше `AniMediaPayloadSource` принимает compound token как обычно.

---

### 4. ScheduleController — тесты

Новый тест-файл покрывает три области:

| Область | Тестов | Что проверяет |
|---------|--------|--------------|
| Day / week mapping | 7 | `day=N` forwarded verbatim; `day=None` / omitted → full-week fetch |
| Unresolved titles | 8 | Partial resolve, ok flag остаётся True при unresolved, unknown provider → `ok=False`, source exception → `ok=False`, `fetched_missing=0` без флага |
| Retry after lazy fetch | 6 | Все unresolved fetched+retried, partial fetch, без двойного upsert когда ничего не fetched, flaky fn не ломает остальные, graceful no-op без `fetch_title_fn` |
| `schedule_get` pass-through | 1 | Результат из read port возвращается как есть |

---

### 5. Job-flow: `titles.update.start` / `jobs.get`

Новая система фоновых задач для неблокирующего provider update.

#### Новые JSON-операции

| Op | Параметры | Описание |
|----|-----------|---------|
| `titles.update.start` | `title_ids, provider_code?, mode?, max_results?` | Запустить update в фоне, вернуть `job_id` сразу |
| `jobs.get` | `job_id` | Получить текущий статус задачи |

#### `titles.update.start` ответ (немедленный)

```json
{"ok": true, "result": {"job_id": "a1b2c3d4-...", "status": "queued"}}
```

#### `jobs.get` ответ

```json
{
  "ok": true,
  "result": {
    "job": {
      "job_id": "a1b2c3d4-...",
      "op": "titles.update",
      "status": "done",
      "error": null,
      "started_at": "2026-04-26T12:00:00+00:00",
      "finished_at": "2026-04-26T12:00:03+00:00",
      "progress": null,
      "result": {"ok": true, "applied": [...], "skipped": 0, "error": null}
    }
  }
}
```

#### Жизненный цикл задачи

```
queued → running → done
                 → error   (при исключении в update_titles)
```

#### Реализация

- `backend/core/jobs/job_store.py` — `JobStatus` dataclass + `JobStore` (thread-safe dict + lock, deepcopy params).
- `h_titles_update_start` — создаёт job, запускает daemon `threading.Thread(asyncio.run(...))`, возвращает немедленно.
- `h_jobs_get` — lookup по `job_id`, сериализует поля вручную (ISO timestamps).
- `StandaloneBackend.jobs = JobStore()` + `FakeBackend.jobs = JobStore()` в conftest.
- `titles.update` (старый sync-handler) сохранён — используется для JSON-tool single-shot режима.

---

### Тесты

| Файл | Тестов | Что проверяет |
|------|--------|--------------|
| `test_provider_integration.py` | 24 | `_unpack_process_titles` (7 unit), StubStorage behavioural (14), real-DB smoke (3, auto-skip) |
| `test_episode_upsert.py` | 22 | ProcessManager.process_episodes с MockSaveManager — natural key, HLS mapping, skips JSON, idempotency |
| `test_titles_update_controller.py` | 28 | `_pick_external_id_from_links`, `_fallback_query`, `update_titles` routing (AniMedia/AniLiberty, no-link, legacy bare-id, alternative_name) |
| `test_schedule_controller.py` | 22 | Day/week forwarding, unresolved, lazy fetch retry, error paths |
| `test_json_handlers_jobs.py` | 25 | `JobStore` unit (9), `titles.update.start` (8), `jobs.get` (6), error path (1) |
| `conftest.py` | — | Исправлен `FakeTitlesController`: добавлены `year/genre/status_filter/type_filter` kwargs |

**Итого тестов:** 194 passed, 3 skipped (real-DB, auto-skip при broken SQLAlchemy).

---

### Definition of Done

- [x] Write-path корректно извлекает `title_id` из `process_titles()` tuple
- [x] `process_episodes` / `process_torrents` получают правильный FK (больше не NULL)
- [x] Episode identity strategy `(title_id, episode_number)` зафиксирована тестами
- [x] AniMedia query routing покрыт regression-тестами (не `story=<local_id>`)
- [x] `alternative_name` используется как fallback query
- [x] ScheduleController: day/week mapping, unresolved, retry — всё покрыто тестами
- [x] Неблокирующий `titles.update.start` + `jobs.get` добавлены в HANDLERS

---

## v0.3.8.44 — Provider Runtime Fixes + UI State Contracts

**Дата:** 2026-04-25
**Статус:** stable candidate

Срез фиксов после проверки Kotlin Multiplatform UI против HTTP-backend и live-provider сценариев.

---

### 1. Runtime / Packaging

- Обновлена backend runtime-документация: для standalone/HTTP запуска обязательны `storage/`, `utils/`, `providers/`.
- Добавлена fail-fast диагностика в `build_backend()`: путь к DB должен указывать на существующую директорию; отсутствие runtime imports логируется warning.
- Добавлены PyInstaller specs:
  - `make_bin/specs/backend_http.spec`
  - `make_bin/specs/backend_tool.spec`

---

### 2. Posters

- Подключён `PosterJobAdapter` поверх существующего `PosterManager`.
- Provider sync/update теперь может ставить постеры в background queue после успешного сохранения payload.
- HTTP `/poster/{title_id}` переведён на request-local SQLAlchemy session, чтобы массовые параллельные запросы постеров не ломали shared identity map.
- `server.py` теперь учитывает `poster_path_original`, что исправляет AniMedia-тitles, где medium/small пустые.

---

### 3. Provider Fixes

- AniLiberty schedule sync получил lightweight path: один API-запрос расписания без N дополнительных fetch/enrich запросов по каждому тайтлу.
- AniMedia HTTP timeout вынесен в `Settings.animedia_http_timeout_s` и увеличен до 90 секунд по умолчанию. Это нужно для медленного HTML/BeautifulSoup flow, где provider update работает заметно дольше API-провайдеров.
- AniMedia update/search больше не использует локальный numeric `title_id` как search query; для legacy provider links строится token `<external_id>@@<title_name>`.
- Исправлен повторный title update с AniLiberty: `episodes.uuid` больше не перезаписывается провайдерским UUID при update существующих episode rows.

---

### 4. Watch History / UI State Contract

- `history.mark_all_watched` теперь корректно работает при `episode_ids=None`: backend резолвит все серии тайтла и возвращает реальный affected count.
- `get_all_episodes_watched_status()` теперь сравнивает количество watched episodes с реальным числом episodes у тайтла. Раньше `true` мог возвращаться по неполному набору history rows.
- HTTP normalizer для `titles.get` отдаёт `ratings`, `franchises`, `all_episodes_watched`, `watched_episode_count`.
- HTTP normalizer для card-view отдаёт `rating_name`, `rating_value`, `is_watched`, `all_episodes_watched`, `need_to_see` для UI badges.
- Добавлен regression test `tests/backend/test_history_storage.py`.

---

### 5. Playlist Path

- Backend playlist storage возвращает абсолютный путь к `.m3u8`.
- Playlist directory создаётся при старте storage adapter, что убирает зависимость от текущего CWD UI-процесса.

---

### 6. Storage Session Concurrency

- `DatabaseManager`, `GetManager`, `SaveManager`, `DeleteManager`, `TemplateManager`, `PlaceholderManager`, `StateManager` переведены с общего SQLAlchemy `Session` на sessionmaker factory.
- Каждый storage method теперь открывает отдельный `with self.Session() as session`, что убирает гонку `identity map is no longer valid` при параллельных HTTP/UI запросах.
- Исправлены прямые infra consumers новой session factory: `SqlAlchemyTitlesPort` и `SqlAlchemyProgressRepo` теперь также используют `Session()`. Это чинит `titles.search`/filtered search после перехода на factory.
- Добавлен regression test на параллельные `get_titles_from_db` через один `DatabaseManager`.

---

### 7. Slow Provider Update Timeout

- KMP HTTP client теперь ждёт backend request до 5 минут (`request/socket timeout = 300s`) для долгих операций provider update.
- `titles.update` остаётся синхронным completion-событием: UI получает `Done` только после завершения provider fetch + save. Отдельная async job/event-система оставлена как follow-up, если понадобится запускать update в фоне без удержания HTTP request.
- В roadmap добавлен follow-up на нормальный job-flow (`titles.update.start` → `job_id`, polling status/result, progress стадии для AniMedia). Timeout признан временной мерой.

---

### Проверки

- `py_compile backend\transport\http\server.py storage\database_manager.py storage\delete.py storage\get.py storage\save.py storage\utils.py`
- `pytest tests\backend\test_history_storage.py tests\backend\test_json_handlers_history.py tests\backend\test_storage_session_scope.py -q` → 20 passed
- `:composeApp:compileKotlinDesktop` → BUILD SUCCESSFUL

---

## v0.3.8.43 — Bugs Found During Testing (UI + HTTP Server)

**Дата:** 2026-04-24
**Статус:** stable

Обнаружены при тестировании нового Kotlin Multiplatform UI против HTTP-бэкенда.
Все 9 багов исправлены.

---

## v0.3.8.42 — History Write Operations + Pagination Metadata

**Дата:** 2026-04-24
**Статус:** stable

UI-prerequisites milestone: все write-операции пользователя и метаданные пагинации реализованы до начала разработки UI.

---

### 1. History Write Operations

Три новых JSON-операции для записи пользовательских действий.

#### Новые JSON-операции

| Op | Параметры | Описание |
|----|-----------|---------|
| `history.mark_watched` | `title_id, episode_id?, is_watched, user_id?` | Отметить эпизод просмотренным / снять |
| `history.mark_all_watched` | `title_id, is_watched, episode_ids?, user_id?` | Отметить все эпизоды тайтла |
| `history.set_need_to_see` | `title_id, need_to_see, user_id?` | Добавить / убрать из "хочу посмотреть" |

#### Ответы (typed DTOs)

```json
// history.mark_watched
{"ok": true, "result": {"result": {"ok": true, "title_id": 10, "episode_id": 5, "is_watched": true, "error": null}}}

// history.mark_all_watched
{"ok": true, "result": {"result": {"ok": true, "title_id": 20, "is_watched": true, "episodes_affected": 12, "error": null}}}

// history.set_need_to_see
{"ok": true, "result": {"result": {"ok": true, "title_id": 15, "need_to_see": true, "error": null}}}
```

#### Архитектура (Hex)

```
handler (transport)
  → HistoryController.mark_watched(user_id, title_id, episode_id, is_watched)
    → IHistoryWritePort.mark_watched(...)   [Core port]
      → SqlAlchemyHistoryWritePort           [Infra]
        → db.save_watch_status(...)
```

Ошибки порта перехватываются в контроллере — возвращается `ok=False, error=str(exc)` без crash.

#### Новые файлы

| Файл | Назначение |
|------|-----------|
| `backend/core/dto/history.py` | `MarkWatchedResult`, `MarkAllWatchedResult`, `NeedToSeeResult` |
| `backend/core/ports/history_write.py` | `IHistoryWritePort` Protocol |
| `backend/core/controllers/history_controller.py` | `HistoryController` |
| `backend/infra/db/history_write_sqlalchemy.py` | `SqlAlchemyHistoryWritePort` |

---

### 2. Pagination Metadata в `titles.search`

#### Расширенный ответ

```json
{
  "ok": true,
  "result": {
    "titles": [...],
    "view": "card",
    "total_count": 42,
    "offset": 0,
    "limit": 50,
    "has_more": false
  }
}
```

| Поле | Описание |
|------|---------|
| `total_count` | Общее число совпадений для данного query |
| `has_more` | `(offset + len(titles)) < total_count` |
| `offset` | Текущее смещение |
| `limit` | Текущий лимит |

#### Как сделано

- `ITitlesPort` → добавлен `count_search_titles(query: str) -> int`
- `SqlAlchemyTitlesPort.count_search_titles()` — переиспользует `get_titles_search_query()`, считает `len(rows)` в Python
- `TitlesController.count_titles(query)` — делегат к порту
- `h_titles_search` — вызывает `backend.titles.count_titles(query)`, добавляет поля в ответ

---

### Тесты

| Файл | Тестов | Что проверяет |
|------|--------|--------------|
| `test_json_handlers_history.py` | 16 | `mark_watched` (6), `mark_all_watched` (5), `set_need_to_see` (5) |

**Итого тестов:** 50 (было 41)

---

### Definition of Done

- [x] Пользователь может отмечать эпизоды просмотренными
- [x] Пользователь может управлять вотч-листом
- [x] `titles.search` возвращает метаданные пагинации для infinite scroll / page controls
- [x] Backend полностью готов к разработке multiplatform UI (Desktop + Android TV)

---

## v0.3.8.41 — Schedule Pipeline, DTO Policies, Full TitleDetailsDTO

**Дата:** 2026-04-24
**Статус:** stable

Три самостоятельных milestone — Связанные сущности, DTO-оптимизация, Schedule — завершены в рамках одного цикла разработки.

---

### 1. Связанные сущности Title (`TitleDetailsDTO` полный)

**Цель:** `TitleDetailsDTO` должен содержать все связанные данные, без lazy-ORM вызовов вне сессии.

#### Новые поля DTO

| Поле | Тип | Источник |
|------|-----|---------|
| `ratings` | `list[RatingDTO]` | `_pref_ratings` |
| `history_records` | `list[HistoryDTO]` | `_pref_history_records` |
| `production_studio` | `ProductionStudioDTO \| None` | `_pref_production_studio_obj` |
| `team_members` | `list[TeamMemberDTO]` | `_pref_team_members` |

#### Как сделано

- `storage/get.py`: 4 новых метода (`get_team_members_from_db`, `get_ratings_list_from_db`, `get_history_records_from_db`, `get_production_studio_obj_from_db`)
- `storage/database_manager.py`: делегаты к `get_manager`
- `storage/queries/title_enricher.py`: устанавливает `_pref_*` атрибуты на ORM объектах перед закрытием сессии
- `backend/core/controllers/titles_controller.py`: читает `_pref_*`, конвертирует в DTO

**Правило:** никаких heavy-join — только batched read-порты.

---

### 2. DTO-оптимизация: `TitleViewMode` policy

**Цель:** облегчённый ответ для list/search-view без N+1 запросов. Заменить boolean flag `compact` на политику.

#### `TitleViewMode(str, Enum)`

| Значение | DTO | Описание |
|----------|-----|---------|
| `"full"` (default) | `TitleDetailsDTO` | Полные данные, все связанные сущности |
| `"card"` | `TitleCardDTO` | Облегчённый: без episodes, torrents, team_members, history, franchises |

#### Изменения

- `backend/core/dto/titles.py`: `TitleViewMode`, `TitleCardDTO`
- `backend/transport/json_tool/handlers.py`: `_parse_view_mode()` — graceful fallback на `FULL` для неизвестных значений
- Enricher CARD mode: пропускает per-episode/per-torrent N+1 циклы
- JSON-параметр: `"view": "card"` / `"view": "full"`
- Ответ содержит `"view": "<значение>"`

**Принцип:** не boolean флаги — политики (enum).

---

### 3. Schedule / Providers (Unified Pipeline)

**Цель:** общий pipeline для расписания через нормализованный `ScheduleItemNormalized`, независимо от провайдера.

#### Новые JSON-операции

| Op | Параметры | Описание |
|----|-----------|---------|
| `schedule.get` | `day: int` | Расписание из БД по дню (1=Пн … 7=Вс) |
| `schedule.sync` | `provider_code, day?, fetch_unresolved?` | Провайдер → нормализация → upsert в БД |

#### `schedule.sync` ответ

```json
{
  "ok": true,
  "result": {
    "ok": true,
    "provider_code": "aniliberty",
    "fetched": 14,
    "upserted": 12,
    "unresolved": 2,
    "fetched_missing": 2,
    "error": null
  }
}
```

#### Lazy enrich (`fetch_unresolved: true`)

Если `external_title_id` не найден в `TitleProviderMap` (тайтл ещё не в БД):
1. Вызывает `pipeline.fetch_and_process(provider_code, external_id)` — сохраняет тайтл
2. Повторяет upsert для только что сохранённых тайтлов
3. `fetched_missing` — счётчик подтянутых тайтлов

#### Архитектура

```
Provider schedule source
    ↓ list[ScheduleItemNormalized]
IScheduleWritePort.upsert_schedule()
    ↓ resolve external_title_id → title_id (batch, TitleProviderMap)
    ↓ save_schedule(day_of_week, title_id)
    → ScheduleUpsertResult(upserted, unresolved, unresolved_items)
```

#### Новые файлы

| Файл | Назначение |
|------|-----------|
| `backend/core/dto/schedule.py` | `ScheduleItemNormalized`, `ScheduleEntryDTO`, `ScheduleUpsertResult`, `ScheduleSyncResult` |
| `backend/core/ports/schedule_port.py` | `IScheduleReadPort`, `IScheduleWritePort`, `IProviderScheduleSource` |
| `backend/core/controllers/schedule_controller.py` | `ScheduleController` |
| `backend/infra/db/schedule_sqlalchemy.py` | DB реализации портов |
| `backend/infra/providers/animedia_schedule_source.py` | AniMedia: async→sync, парсер дат |
| `backend/infra/providers/aniliberty_schedule_source.py` | AniLiberty: по дню или вся неделя |
| `backend/adapters/animedia_provider.py` | `AniMediaProviderAdapter` (sync facade + async proxies) |

#### `AniMediaProviderAdapter`

Симметричен `AniLibertyProviderAdapter`. Sync методы (`search`, `get_details`, `get_schedule`) + async proxies (`get_by_title`, `get_new_titles`) для совместимости с `AniMediaPayloadSource` и `AniMediaScheduleSource`.

Особенность: AniMedia не имеет endpoint "fetch by ID" — `get_details()` принимает `@@token` формат (`"20693@@One Punch Man"`).

#### `ProvidersFactory.build_all()`

Строит `payload_sources` + `schedule_sources` из одних и тех же экземпляров адаптеров (shared state / cache).

#### Внешняя инъекция

```python
backend = build_backend(
    db_path="...",
    aniliberty_api_adapter=al_adapter,
    animedia_api_adapter=am_adapter,   # new
)
```

---

### Тесты

| Файл | Тестов | Что проверяет |
|------|--------|--------------|
| `test_json_handlers_schedule.py` | 7 | `schedule.get`, `schedule.sync`, `fetch_unresolved` |
| `test_schedule_normalizers.py` | 7 | Парсер дат AniMedia ("Сегодня/Вчера/DD-MM-YYYY, HH:MM") |
| `test_json_handlers_titles.py` | +4 | `TitleViewMode` card/full, defaults, unknown fallback |

**Итого тестов:** 41 (было 26)

---

### Definition of Done

- [x] Расписание читается из БД (`schedule.get`)
- [x] Расписание синхронизируется от AniLiberty и AniMedia (`schedule.sync`)
- [x] Нераспознанные тайтлы подтягиваются автоматически (`fetch_unresolved`)
- [x] Оба провайдера симметрично обёрнуты адаптерами
- [x] `TitleDetailsDTO` содержит все связанные сущности
- [x] Облегчённый `TitleCardDTO` без N+1 запросов
- [x] Boolean flags заменены на enum-политики

---

## v0.3.8.40 — Pretty code

**Дата:** 2026-01-10
**Статус:** stable baseline

- Backend переведён на controller-based sync / update
- Добавлен BackendContext (дефолты, user_id из config)
- Handlers готовы к переходу на RequestContext (частично)
- Titles.update / sync.search_and_process стабилизированы
- Юнит-тесты покрывают handlers и sync

---

## v0.3.8.40 — Unified Sync & Update Pipeline

**Дата:** 2026-01-09
**Статус:** stable baseline

### Основные изменения

#### Архитектура

* Backend окончательно выделен в **standalone-библиотеку**
* JSON-tool (`stdin → stdout`) зафиксирован как единственный транспорт
* Backend и контроллеры **stateless**
* Контроллеры **не работают с БД напрямую**, только через порты
* Вся запись в БД проходит через **единый write-path (`process`)**

#### Controllers

Добавлены и стабилизированы:

* `SyncController`

  * `search_external_ids`
  * `fetch_payload`
  * `fetch_and_process`
  * `search_and_process`
* `TitlesUpdateController`

  * `titles.update`
  * обновление по `provider_links`
  * приоритет `external_id`, fallback на `query`

#### Providers

* Унифицирован pipeline для AniLiberty и AniMedia
* Поиск по `query` теперь корректно поддерживает N кандидатов
* Обновление тайтлов работает **без знания external_id со стороны UI**

#### Titles

* `titles.search`
* `titles.get` (single / batch)
* `titles.list_episodes`
* Полный `TitleDetailsDTO`:

  * episodes с абсолютными HLS URL
  * posters / previews
  * provider_links
  * user prefs (history / need_to_see / watched)
* Enrichment вынесен в infra

#### Streams / Playlists

* `streams.get`
* `playlist.compose`
* `playlist.compose_multi`
* Контракты стабилизированы, JSON унифицирован

---

### Тесты

* Добавлены unit-tests для:

  * json handlers
  * sync pipeline
  * provider adapters
* Тесты изолированы от БД через FakeBackend
* Архитектурные инварианты зафиксированы тестами

---

### Технические улучшения

* Удалены дубли:

  * `titles_search_full`
* Убраны lazy-ORM вызовы из core
* URL-логика централизована в `backend/core/utils/urls.py`
* Провайдеры инициализируются централизованно (bootstrap-слой)

---

### ️ Известные ограничения

* Нет heavy-join’ов
* Нет async-jobs / очередей
* Нет write-операций напрямую из контроллеров
* Нет Web API (только JSON-tool)

---

### Definition of Done

* Backend стабилен
* Sync + Update работают
* Архитектура зафиксирована
* Можно продолжать развитие **без рефакторинга основы**

---

## v0.3.8.39 — Titles Read Stabilization

**Дата:** 2026-01-08

* Стабилизация `titles.search / titles.get`
* Вынесение enrich в infra
* Absolute URLs для streams / assets
* Очистка core от DB-логики

---

## До v0.3.8.39 (legacy)

* Backend был частью Qt-приложения
* Смешение UI / DB / providers
* Нестабильные entry-points

---


