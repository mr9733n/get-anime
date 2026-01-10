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

---

## 🟡 NEXT — Write-path (process → save)

**Цель:** любые данные от провайдера (включая расписание) попадают в БД **только** через единый `process`-канал,
где выполняются проверки/нормализация/мерж (и только потом `save`).

### Planned

* [ ] Новый backend-op: `process.provider_payload` (или `sync.apply`)
  * `params`: `{ provider_code, payload, mode }`
* [ ] Core: `ProcessController` + use-case `ApplyProviderPayload`
  * Контроллер принимает нормализованный input
  * Дергает use-case
  * Use-case вызывает write-port
* [ ] Infra: write-port (обёртка над существующим `db.process_*` / `storage.process`)
  * Core **не видит** `db_manager` / storage напрямую
  * Один канал записи = база для schedule и новых провайдеров

**Definition of Done:**

* запись в БД из backend происходит через `process` (одна точка входа)
* UI/Sync-код может вызывать только этот op для применения provider payload

## 🟡 NEXT — Связанные сущности Title

**Цель:** сделать `TitleDetailsDTO` действительно полным.

### Planned

* [ ] Ratings
* [ ] Watch history (read-only)
* [ ] Production studio
* [ ] Team members
* [ ] Franchises

📌 Правило:

> никаких heavy-join
> только batched read-порты

---

## 🟡 DTO-оптимизация под UI

* [ ] `TitleCardDTO` (облегчённый)
* [ ] Разделение:

  * list-view → `TitleCardDTO`
  * detail-view → `TitleDetailsDTO`
* [ ] Опциональный `compact=true`

---

## 🟡 Schedule / Providers (Unified pipeline)

**Цель:** не “умный контроллер под одного провайдера”, а общий pipeline через нормализованный `ScheduleItem`.

### Planned

* [ ] DTO/модель `ScheduleItemNormalized`
  * `provider_code`, `external_title_id`
  * `air_dt` (datetime в TZ проекта)
  * `episode_number` / `episode_label`
  * `poster_url`, `title_url`
  * `raw` (fallback)
* [ ] Парсер AniMedia → `ScheduleItemNormalized`
  * “Сегодня/Вчера/7-01-2026, 16:00” → datetime
* [ ] Маппинг AniLiberty schedule → тот же формат
* [ ] `process.schedule.upsert(items)` (через write-path!)
  * resolve `external_title_id -> title_id` через `TitleProviderMap`
  * сохранить schedule
  * если title ещё нет: create partial title или отметить unresolved

**Итог:**

* `schedule.get` = DB-only
* `schedule.sync` = provider → normalize → process → save



* [ ] `schedule.get` (DB-only)
* [ ] Schedule порт
* [ ] AniLiberty (через provider)
* [ ] AniMedia (через cache)
* [ ] Lazy enrich при открытии тайтла

---

## 🟡 Combined Titles (Preview → Job)

**Цель:** подготовить “один тайтл — много источников” без спешки с миграциями: сначала отладка правил через preview,
потом отдельный job для записи результата.

### Planned

* [ ] `titles.combine.preview`
  * вход: `title_id` или `code`
  * выход:
    * кандидаты `title_ids`
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


