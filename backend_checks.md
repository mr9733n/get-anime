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
