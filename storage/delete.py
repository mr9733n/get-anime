import json
import logging

from typing import Any
from datetime import timezone, datetime
from sqlalchemy.orm import sessionmaker

from storage.tables import Title, DeletedTitleLog


class DeleteManager:
    def __init__(self, engine):
        self.logger = logging.getLogger(__name__)
        self.Session = sessionmaker(bind=engine)()

    @staticmethod
    def _safe_dt(v):
        try:
            return v.isoformat() if v else None
        except Exception:
            return str(v)

    def _build_snapshot(self, t: Title) -> dict:
        """
        Строит безопасный snapshot:
        - колонки Title
        - ключевые поля детей (без BLOB/сырых файлов)
        """
        title_cols = {c.name: getattr(t, c.name) for c in t.__table__.columns}
        for k, v in list(title_cols.items()):
            if hasattr(v, "isoformat"):
                title_cols[k] = self._safe_dt(v)

        snap = {
            "title": title_cols,
            "children": {
                "episodes": [
                    {
                        "episode_id": e.episode_id,
                        "episode_number": e.episode_number,
                        "uuid": getattr(e, "uuid", None),
                        "name": getattr(e, "name", None),
                    }
                    for e in getattr(t, "episodes", []) or []
                ],
                "torrents": [
                    {
                        "torrent_id": x.torrent_id,
                        "episodes_range": getattr(x, "episodes_range", None),
                        "quality": getattr(x, "quality", None),
                        "resolution": getattr(x, "resolution", None),
                        "size_string": getattr(x, "size_string", None),
                        "url": getattr(x, "url", None),
                        "uploaded_timestamp": self._safe_dt(getattr(x, "uploaded_timestamp", None)),
                    }
                    for x in getattr(t, "torrents", []) or []
                ],
                "posters": [
                    {
                        "poster_id": p.poster_id,
                        "hash_value": getattr(p, "hash_value", None),
                        "medium_hash": getattr(p, "medium_hash", None),
                        "thumb_hash": getattr(p, "thumb_hash", None),
                        "last_updated": self._safe_dt(getattr(p, "last_updated", None)),
                        "medium_updated_at": self._safe_dt(getattr(p, "medium_updated_at", None)),
                        "thumb_updated_at": self._safe_dt(getattr(p, "thumb_updated_at", None)),
                    }
                    for p in getattr(t, "posters", []) or []
                ],
                "history": [
                    {
                        "id": h.id,
                        "user_id": getattr(h, "user_id", None),
                        "episode_id": getattr(h, "episode_id", None),
                        "torrent_id": getattr(h, "torrent_id", None),
                        "is_watched": getattr(h, "is_watched", None),
                        "is_download": getattr(h, "is_download", None),
                        "need_to_see": getattr(h, "need_to_see", None),
                        "last_watched_at": self._safe_dt(getattr(h, "last_watched_at", None)),
                        "last_download_at": self._safe_dt(getattr(h, "last_download_at", None)),
                    }
                    for h in getattr(t, "history", []) or []
                ],
                "provider_links": [
                    {
                        "provider_id": m.provider_id,
                        "external_title_id": m.external_title_id,
                    }
                    for m in getattr(t, "provider_links", []) or []
                ],
                "production_studio": (
                    {
                        "name": getattr(getattr(t, "production_studio", None), "name", None),
                        "last_updated": self._safe_dt(getattr(getattr(t, "production_studio", None), "last_updated", None)),
                    }
                    if getattr(t, "production_studio", None) is not None
                    else None
                ),
                "genres": [
                    {
                        "relation_id": rel.id,
                        "genre_id": rel.genre_id,
                        "genre_name": getattr(getattr(rel, "genre", None), "name", None),
                        "last_updated": self._safe_dt(getattr(rel, "last_updated", None)),
                    }
                    for rel in getattr(t, "genres", []) or []
                ],
                "team_members": [
                    {
                        "relation_id": rel.id,
                        "team_member_id": rel.team_member_id,
                        "name": getattr(getattr(rel, "team_member", None), "name", None),
                        "role": getattr(getattr(rel, "team_member", None), "role", None),
                        "last_updated": self._safe_dt(getattr(rel, "last_updated", None)),
                    }
                    for rel in getattr(t, "team_members", []) or []
                ],
                "franchises": [
                    {
                        "release_id": fr.id,
                        "franchise_id": fr.franchise_id,
                        "franchise_db_id": getattr(getattr(fr, "franchise", None), "id", None),
                        "franchise_key": getattr(getattr(fr, "franchise", None), "franchise_id", None),
                        "franchise_name": getattr(getattr(fr, "franchise", None), "franchise_name", None),
                        "code": getattr(fr, "code", None),
                        "ordinal": getattr(fr, "ordinal", None),
                        "name_ru": getattr(fr, "name_ru", None),
                        "name_en": getattr(fr, "name_en", None),
                        "name_alternative": getattr(fr, "name_alternative", None),
                        "ext_fr_id": getattr(fr, "ext_fr_id", None),
                        "ext_fr_rel_id": getattr(fr, "ext_fr_rel_id", None),
                        "ext_rel_id": getattr(fr, "ext_rel_id", None),
                        "last_updated": self._safe_dt(getattr(fr, "last_updated", None)),
                    }
                    for fr in getattr(t, "franchises", []) or []
                ],
            },
        }

        snap["counts"] = {
            "episodes": len(snap["children"]["episodes"]),
            "torrents": len(snap["children"]["torrents"]),
            "posters": len(snap["children"]["posters"]),
            "history": len(snap["children"]["history"]),
            "provider_links": len(snap["children"]["provider_links"]),
            "genres": len(snap["children"]["genres"]),
            "team_members": len(snap["children"]["team_members"]),
            "franchises": len(snap["children"]["franchises"]),
        }
        return snap

    def soft_delete_titles(self, title_ids_input, reason="soft_delete") -> dict:
        if isinstance(title_ids_input, str):
            parts = title_ids_input.split(",")
            title_ids = [int(p.strip()) for p in parts if p.strip().isdigit()]
        elif isinstance(title_ids_input, (list, tuple)):
            title_ids = []
            for x in title_ids_input:
                if isinstance(x, int):
                    title_ids.append(x)
                elif isinstance(x, str) and x.strip().isdigit():
                    title_ids.append(int(x))
        elif isinstance(title_ids_input, int):
            title_ids = [title_ids_input]
        else:
            raise ValueError(f"Unsupported type for title_ids_input: {type(title_ids_input)}")

        if not title_ids:
            return {"deleted": [], "not_found": []}

        deleted = []
        not_found = []

        with self.Session as session:
            titles = session.query(Title).filter(Title.title_id.in_(title_ids)).all()
            found_ids = {t.title_id for t in titles}
            not_found = [tid for tid in title_ids if tid not in found_ids]

            now = datetime.now(timezone.utc)
            for t in titles:
                t.is_deleted = True
                t.deleted_at = now

            session.commit()
            return {"deleted": list(found_ids), "not_found": not_found}

    def delete_titles(self, title_ids_input) -> dict[str, list[Any]] | None:
        """
        Удаляет один или несколько тайтлов.
        Принимает:
            - строку вида "123, 456,789"
            - список строк/чисел ["123", "456"]
            - одно число 123

        Возвращает:
            {
                "deleted": [список удалённых title_id],
                "not_found": [список id, которых нет в БД],
            }
        """
        if isinstance(title_ids_input, str):
            parts = title_ids_input.split(",")
            title_ids = [int(p.strip()) for p in parts if p.strip().isdigit()]
        elif isinstance(title_ids_input, (list, tuple)):
            title_ids = []
            for x in title_ids_input:
                if isinstance(x, int):
                    title_ids.append(x)
                elif isinstance(x, str) and x.strip().isdigit():
                    title_ids.append(int(x))
        elif isinstance(title_ids_input, int):
            title_ids = [title_ids_input]
        else:
            raise ValueError(f"Unsupported type for title_ids_input: {type(title_ids_input)}")

        if not title_ids:
            return {"deleted": [], "not_found": []}

        deleted = []
        not_found = []

        with self.Session as session:
            titles = (
                session.query(Title)
                .filter(Title.title_id.in_(title_ids))
                .filter(Title.is_deleted == True)
                .all()
            )

            found_ids = {t.title_id for t in titles}
            not_found = [tid for tid in title_ids if tid not in found_ids]

            try:
                for t in titles:
                    snap = self._build_snapshot(t)
                    session.add(
                        DeletedTitleLog(
                            title_id=t.title_id,
                            title_name_ru=getattr(t, "name_ru", None),
                            title_code=getattr(t, "code", None),
                            deleted_at=datetime.now(timezone.utc),
                            reason="manual_delete",
                            snapshot_json=json.dumps(snap, ensure_ascii=False),
                            counts_json=json.dumps(snap.get("counts", {}), ensure_ascii=False),
                        )
                    )
                    session.delete(t)

                session.commit()
                deleted = list(found_ids)

            except Exception as e:
                session.rollback()
                self.logger.error(f"Error deleting titles {title_ids}: {e}")
                raise

        return {"deleted": deleted, "not_found": not_found}