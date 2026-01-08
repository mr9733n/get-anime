# Backend TL;DR — Anime / Media Catalog

## Цель
Сделать **standalone backend** без Qt/UI:
- one-shot (stdin → JSON → stdout → exit)
- stateless в памяти
- state только в БД и файловом кэше
- используется существующая логика (providers / storage / utils)

Qt-приложение **не трогаем** — оно замороженный клиент.

---

## Принципы (обязательные)

- ❌ Нет Qt / mpv / vlc импортов
- ❌ Нет in-memory state между запросами
- ✅ Backend = библиотека
- ✅ JSON-tool = транспорт поверх backend
- ✅ Core не знает про transport / UI

---

## Архитектура

```

core        — use-cases, DTO, ports
infra       — DB, providers, cache, posters
bootstrap   — сбор зависимостей (без Qt)
transport   — stdin/stdout JSON

````

---

## State

Хранится ТОЛЬКО в infra:
- SQLite (через текущий storage)
- JSON cache (animedia)
- файлы постеров / плейлистов

---

## Backend API (MVP)

Поддерживаем операции:

- `titles.search`
- `titles.fetch`
- `titles.get`
- `schedule.get`
- `streams.get`
- `playlist.compose`

---

## JSON protocol

### Request
```json
{
  "op": "titles.search",
  "params": {
    "query": "naruto",
    "provider": "aniliberty"
  }
}
````

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

## DTO

* Только для транспорта
* `dataclasses`
* ORM наружу не выходит

Минимум:

* TitleCardDTO
* TitleDetailsDTO
* ScheduleItemDTO
* StreamInfoDTO
* PlaylistDTO

---

## Providers

* Каждый провайдер — отдельный модуль
* Регистрируется через `ProviderRegistry`
* Core не меняется при добавлении нового

---

## Постеры

* Скачивание — infra
* Backend может инициировать
* Очереди / jobs — потом

---

## БД

* SQLite (через текущий storage)
* ORM только в infra
* Core работает через абстракции

---

## Definition of Done

* backend_tool.py работает без Qt
* работает:

  * поиск
  * загрузка тайтла
  * расписание
  * плейлист
* JSON стабилен
* backend собирается в standalone бинарник без Qt/mpv/vlc
* Qt может не запускаться вообще

---

## Старт работ

1. bootstrap
2. transport skeleton
3. `titles.search`

---


