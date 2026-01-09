# app/qt/controllers/system.py
from __future__ import annotations


class SystemController:
    def __init__(self, db_manager, state_service, logger):
        self.db = db_manager
        self.state = state_service
        self.logger = logger

    def get_current_template_and_state(self):
        st = self.state.load_state() or {}
        name = st.get("template_name", "default")
        if isinstance(name, str) and name.startswith('"') and name.endswith('"'):
            name = name.strip('"')
        return name, st

    def list_templates(self):
        return [t.strip() for t in (self.db.get_available_templates() or [])]

    def switch_template(self, name: str):
        _, st = self.get_current_template_and_state()
        st["template_name"] = name
        self.state.save_state(st)

    def add_studio(self, studio_name: str, title_ids: list[int]):
        self.db.save_studio_to_db(title_ids, studio_name)

    def trash_titles(self, csv_ids: str):
        return self.db.soft_delete_titles(csv_ids)

    def optimize_db(self):
        return self.db.optimize_db()

    def get_deleted_titles_log(self, limit: int = 300, offset: int = 0):
        return self.db.get_deleted_titles_log(limit=limit, offset=offset)

    def get_deleted_titles_log_item(self, log_id: int):
        return self.db.get_deleted_titles_log_item(log_id)

    def get_deleted_titles(self, batch_size: int = 300, offset: int = 0):
        # DeletedWindow.refresh()
        return self.db.get_deleted_titles(batch_size=batch_size, offset=offset)

    def restore_titles(self, ids: list[int]):
        # DeletedWindow.restore()
        return self.db.restore_titles(ids)

    def purge_titles(self, csv_ids: str):
        # DeletedWindow.purge()
        return self.db.purge_titles(csv_ids)
