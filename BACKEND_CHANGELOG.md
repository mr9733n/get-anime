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


