# Проверочные команды (PowerShell)

## titles.search

```powershell
'{"op":"titles.search","params":{"query":"sakamoto"}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

## titles.get (single)

```powershell
'{"op":"titles.get","params":{"title_id":2128}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

## titles.get (batch)

```powershell
'{"op":"titles.get","params":{"title_ids":[2128,2129]}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

## titles.list_episodes (single)

```powershell
'{"op":"titles.list_episodes","params":{"title_id":2128}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

## titles.list_episodes (batch)

```powershell
'{"op":"titles.list_episodes","params":{"title_ids":[2128,2129]}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

## streams.get (у тебя уже работает — проверка регресса)

```powershell
'{"op":"streams.get","params":{"title_id":2128,"episode_number":1}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

## playlist.compose_multi (by_title)

```powershell
'{"op":"playlist.compose_multi","params":{"title_ids":[2128,2129],"quality":"best","mode":"by_title","name":"pack_2128_2129"}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

## playlist.compose_multi (preview)

```powershell
'{"op":"playlist.compose_multi","params":{"title_ids":[2128,2129],"quality":"best","mode":"preview","preview_count":1,"name":"preview_pack"}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

## playlist.compose_multi (continue)

```powershell
'{"op":"playlist.compose_multi","params":{"title_ids":[2128,2129],"quality":"best","mode":"continue","user_id":42,"name":"continue_pack"}}' |
python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

---

## 1️⃣ Проверка поиска кандидатов (read-side)

### AniLiberty — поиск external_id

```powershell
'{
  "op":"sync.search_external_ids",
  "params":{
    "provider_code":"aniliberty",
    "query":"One Punch Man",
    "max_results":10
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ожидание: список числовых id (не пустой).

---

### AniMedia — поиск external_id

```powershell
'{
  "op":"sync.search_external_ids",
  "params":{
    "provider_code":"animedia",
    "query":"One Punch Man",
    "max_results":10
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ожидание: несколько токенов / id (не один).

---

## 2️⃣ Проверка fetch payload (без сохранения)

### AniLiberty — получить payload по query

```powershell
'{
  "op":"sync.fetch_payload",
  "params":{
    "provider_code":"aniliberty",
    "query":"One Punch Man",
    "max_results":5
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ожидание: dict с title / episodes / player и т.д.

---

### AniMedia — получить payload по query

```powershell
'{
  "op":"sync.fetch_payload",
  "params":{
    "provider_code":"animedia",
    "query":"One Punch Man",
    "max_results":5
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ожидание: один payload (первый найденный).

---

## 3️⃣ Проверка сохранения одного тайтла

### AniLiberty — сохранить первый найденный

```powershell
'{
  "op":"sync.fetch_and_process",
  "params":{
    "provider_code":"aniliberty",
    "query":"One Punch Man",
    "mode":"title",
    "max_results":1
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ожидание:

* `storage_result: [true, <title_id>]`
* без ошибок SQLAlchemy

---

### AniMedia — сохранить первый найденный

```powershell
'{
  "op":"sync.fetch_and_process",
  "params":{
    "provider_code":"animedia",
    "query":"One Punch Man",
    "mode":"title",
    "max_results":1
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

---

## 4️⃣ Массовый search + save (ключевой сценарий)

### AniLiberty — несколько тайтлов

```powershell
'{
  "op":"sync.search_and_process",
  "params":{
    "provider_code":"aniliberty",
    "query":"One Punch Man",
    "mode":"title",
    "max_results":10,
    "limit":5
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ожидание:

* `applied` длиной `limit`
* без `no_candidates`
* без SQLAlchemy warning/error

---

### AniMedia — несколько тайтлов

```powershell
'{
  "op":"sync.search_and_process",
  "params":{
    "provider_code":"animedia",
    "query":"One Punch Man",
    "mode":"title",
    "max_results":10,
    "limit":5
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

---

## 5️⃣ Проверка, что тайтлы реально в БД

### Поиск в локальной БД

```powershell
'{
  "op":"titles.search",
  "params":{
    "query":"One Punch Man"
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

---

### Получить конкретный title

```powershell
'{
  "op":"titles.get",
  "params":{
    "title_id":10089
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

(замени `10089` на любой id из предыдущих результатов)

---

## 6️⃣_toggle-тесты (опционально, но полезно)

### Повторный запуск (идемпотентность)

```powershell
'{
  "op":"sync.search_and_process",
  "params":{
    "provider_code":"aniliberty",
    "query":"One Punch Man",
    "mode":"title",
    "max_results":10,
    "limit":3
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ок, делаем: **добавляем новые команды** в твой чек-лист  и затем **правим тесты под контроллеры** (раз handlers теперь зовут `backend.sync.*` и `backend.titles_update.*`).

## 1) Новые команды для проверки update

Добавь в `backend_checks.md` новые секции (в конец, после sync):

### ✅ titles.update (strict provider_code)

```powershell
# Обновить выбранные тайтлы строго через конкретный провайдер.
# Если у тайтла нет provider_link для этого provider_code — он будет SKIP (не будет угадывать).

'{
  "op":"titles.update",
  "params":{
    "title_ids":[10089,10322,10323],
    "provider_code":"animedia",
    "mode":"title",
    "max_results":10
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

### ✅ titles.update (auto: по provider_links из БД)

```powershell
# Обновить выбранные тайтлы по тем provider_links, которые уже записаны в БД.
# (т.е. сам выберет провайдеры и external_id из provider_links)

'{
  "op":"titles.update",
  "params":{
    "title_ids":[10089,10322,10323],
    "mode":"title",
    "max_results":10
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

### ✅ titles.update (one title, показать наглядно)

```powershell
'{
  "op":"titles.update",
  "params":{
    "title_ids":[10089],
    "mode":"title_full",
    "max_results":10
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

### ❌ titles.update (негативный)

```powershell
'{
  "op":"titles.update",
  "params":{
    "title_ids":[]
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ожидание: `{"ok": false, "error": "title_ids must be a non-empty list[int]"}`

---

### Авто-обновление “как в UI” (без provider_code)

Проверяет, что берём `provider_links` и оттуда `external_title_id`:

```powershell
'{
  "op":"titles.update",
  "params":{
    "title_ids":[10089],
    "mode":"title"
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

Ожидаемо: `applied` не пустой, `skipped=0`.

### Принудительно конкретным провайдером

Проверяет выбор линка по provider_code:

```powershell
'{
  "op":"titles.update",
  "params":{
    "title_ids":[10089],
    "provider_code":"animedia",
    "mode":"title_full",
    "max_results":5
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```

### Негативный тест: провайдер указан, но маппинга нет → должен уйти в query-fallback

Например, провайдер “aniliberty”, а тайтл связан только с “animedia” — тогда `external_id` не найдётся, но возьмём `query` из `name_en/name_ru`:

```powershell
'{
  "op":"titles.update",
  "params":{
    "title_ids":[10089],
    "provider_code":"aniliberty",
    "mode":"title",
    "max_results":5
  }
}' | python -m backend.transport.json_tool.backend_tool --db .\db\anime_player.db
```


