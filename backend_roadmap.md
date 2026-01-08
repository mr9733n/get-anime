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

# 3) Фиксация прогресса + TLDR.md для нового чата

Ниже готовый “боевой” `tldr.md` — копируй как есть:

````md
# Backend (DB-only) JSON Tool — TLDR

## Что это
Standalone backend для Anime каталога.
One-shot режим: stdin -> обработка -> stdout -> exit.
Никаких импортов Qt/mpv/vlc. State только в SQLite + файлы (playlists).

## Запуск
```powershell
'{"op":"titles.search","params":{"query":"sakamoto"}}' |
python -m app.transport.json_tool.backend_tool --db .\db\anime_player.db
````

## Протокол

Request:

```json
{"op":"...","params":{...}}
```

Response:

```json
{"ok":true,"result":{...},"error":null}
```

## Реализовано (актуально)

### titles.search

Params:

* query: string (required)
* provider: string (optional)
  Result:
* title_ids: [int]
* providers: [string]

### titles.get

Params:

* title_id: int OR
* title_ids: [int]
  Result:
* titles: [TitleDetailsDTO...]

TitleDetailsDTO включает episodes[*] и host_for_player.
EpisodeDTO содержит поля hls_* и hls_*_abs (absolute URLs через host_for_player).

### titles.list_episodes

Params:

* title_id: int OR
* title_ids: [int]
  Result:
* episodes: [EpisodeDTO...] OR
* episodes_by_title: { "<title_id>": [EpisodeDTO...] }

### streams.get

Params:

* title_id: int
* episode_number: int
  Result:
* stream: StreamInfoDTO
  URL уже абсолютные (https://{host_for_player}+path)

### playlist.compose

Params:

* title_id: int
* quality: best|fhd|hd|sd (optional)
  Result:
* path: string (.m3u)

### playlist.compose_multi

Params:

* title_ids: [int] (required)
* quality: best|fhd|hd|sd (optional)
* mode: by_title|preview|latest|continue (optional)
* name: string (optional)
* preview_count: int (optional, для preview)
* user_id: int (optional, для continue; default 42)
  Result:
* path: string (.m3u)

Modes:

* by_title: все эпизоды по тайтлам (сначала тайтл1, потом тайтл2)
* preview: первые N эпизодов каждого тайтла (preview_count)
* latest: последний эпизод каждого тайтла (по номеру)
* continue: следующий непосмотренный эпизод по history/progress (через ProgressRepo)

## Архитектура

* transport: app/transport/json_tool/backend_tool.py + handlers registry
* core: dto + controllers (titles/streams/playlists)
* infra: db repos (progress_repo), adapters/repositories
* bootstrap: standalone deps wiring


