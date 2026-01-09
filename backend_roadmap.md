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

## 🟡 Schedule / Providers

* [ ] `schedule.get` (DB-only)
* [ ] Schedule порт
* [ ] AniLiberty (через provider)
* [ ] AniMedia (через cache)
* [ ] Lazy enrich при открытии тайтла

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


