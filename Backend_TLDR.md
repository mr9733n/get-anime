# Backend TL;DR — Anime / Media Catalog (Canonical)

## Назначение

Standalone backend для Anime-каталога.

**Формат работы:**

* one-shot: `stdin → JSON → stdout → exit`
* stateless в памяти
* состояние хранится только в infra (БД / файлы)
* используется существующая логика providers / storage / utils

Qt-приложение **не трогаем** — это замороженный клиент.

---

## Базовые принципы (обязательные)

* ❌ Нет Qt / mpv / vlc импортов
* ❌ Нет in-memory state между запросами
* ❌ Контроллеры не знают про БД / Session / ORM
* ✅ Backend = библиотека
* ✅ JSON-tool = транспорт поверх backend
* ✅ Core не знает про transport / UI
* ✅ Вся работа с БД — через порты

---

## Архитектура (фактическая, на текущий момент)

```
transport (json_tool)
   ↓
controllers (TitlesController, StreamsController, PlaylistsController)
   ↓
ports (ITitlesPort, ITitlesEnricherPort, …)
   ↓
infra (SqlAlchemy*Port)
   ↓
storage / SQLAlchemy / SQLite
```

### Роли слоёв

* **core**

  * controllers
  * DTO
  * ports
  * utils (чистые функции, без IO)

* **infra**

  * DB / SQLAlchemy
  * providers
  * cache
  * постеры / плейлисты
  * реализация портов

* **transport**

  * stdin/stdout JSON
  * маппинг `op → controller`

---

## State

Хранится **только в infra**:

* SQLite (через существующий storage)
* JSON cache (animedia)
* файлы постеров
* файлы плейлистов

Backend и контроллеры stateless.

---

## Порты (актуально)

### `ITitlesPort`

Единая точка чтения тайтлов:

* `get_titles(...)`
* `search_title_ids(query, limit, offset)`
* `search_title_ids_with_providers(query)`
  (для `titles_ids.search`)
* `get_provider_links_map(title_ids)`
  (batched, read-only)

### `ITitlesEnricherPort`

* `enrich_titles(titles, user_id)`
* Контроллер **не знает**, как именно происходит enrich
* Вся логика enrichment живёт в infra

---

## Controllers (состояние на сейчас)

### `TitlesController`

* ❌ нет `self._db`
* ❌ нет `Session`
* ❌ нет `storage.*`
* ✅ только порты + utils

Удалено:

* `titles_search_full` (дублировал `titles_search`)
* любые lazy-load обращения к ORM

Рабочий поток:

```
search → title_ids → get_titles → enrich → DTO
```

---

## URL-логика (зафиксировано)

Вся логика сосредоточена в:

```
backend/core/utils/urls.py
```

### Разделение ответственности

**Stream URLs (HLS):**

* источник: `host_for_player` (из БД)
* сборка: `make_base_url(host_for_player)`

**Assets URLs (preview / posters / torrents):**

* источник: `config.ini` (по провайдеру)
* сборка: `abs_asset_url(...)`

Контроллеры **не выбирают хосты** и не знают про конфиг напрямую.

---

## DTO

DTO — только транспортный слой, ORM наружу не выходит.

### Ключевые DTO

* `TitleDetailsDTO`

  * episodes

    * `hls_*`
    * `hls_*_abs`
    * `preview_abs`
  * `poster_path_small / medium / original` (absolute, asset-host)
  * `torrents[].url` (absolute)
  * `provider_links`
  * пользовательские prefs из enricher

* `TitleCardDTO` (для списков, позже)

* `ScheduleItemDTO`

* `StreamInfoDTO`

* `PlaylistDTO`

---

## Backend API (фактически реализовано)

Поддерживаются операции:

* `titles.search`
* `titles.get` (single / batch)
* `titles.list_episodes`
* `streams.get`
* `playlist.compose`
* `playlist.compose_multi`

---

## JSON protocol

### Request

```json
{
  "op": "titles.search",
  "params": {
    "query": "naruto"
  }
}
```

### Response

```json
{
  "ok": true,
  "result": {},
  "error": null
}
```

* one-shot
* параллельность — на стороне клиента

---

## Проверено вручную

```powershell
'{"op":"titles.search","params":{"query":"sakamoto"}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db

'{"op":"titles.get","params":{"title_id":2128}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

---

## Что сознательно НЕ делали

* ❌ не добавляли heavy-joined методы в `get_titles_from_db`
* ❌ не трогали Qt-код
* ❌ не грузили все relationship сразу

Вместо этого:

* узкие batched-get через порты
* контролируем объём данных
* полностью избегаем detached lazy-load

---

## Definition of Done (текущая стадия)

* backend_tool.py работает без Qt
* работают:

  * поиск
  * загрузка тайтла
  * эпизоды
  * стримы
  * плейлисты
* JSON стабилен
* backend можно собирать в standalone-бинарник без Qt/mpv/vlc

---

## Текущий статус

✅ Backend стабилен
✅ Архитектура вычищена
✅ Нет дублирования логики
✅ Можно продолжать развитие без техдолга

---

## Как начинать новый чат

Достаточно вставить:

> **Контекст:**
> Standalone backend для Anime-каталога.
> Controllers полностью переведены на порты (`ITitlesPort`, `ITitlesEnricherPort`).
> Прямых вызовов БД из контроллеров нет.
> URL-логика вынесена в `backend/core/utils/urls.py` (stream vs assets).
> `titles_search_full` удалён как дубликат.
> Backend стабилен, JSON-tool работает.
> Хочу продолжить развитие backend-слоя.

---

## Возможные следующие шаги (не зафиксировано)

* порты для `ratings / history / production_studio`
* event / job-очередь для постеров
* compact DTO для list-view
* кеширование `search → title_ids`

---

