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


