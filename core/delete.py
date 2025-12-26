import logging
from sqlalchemy.orm import sessionmaker
from core.tables import Title


class DeleteManager:
    def __init__(self, engine):
        self.logger = logging.getLogger(__name__)
        self.Session = sessionmaker(bind=engine)()

    def delete_titles(self, title_ids_input) -> dict:
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
                .all()
            )

            found_ids = {t.title_id for t in titles}
            not_found = [tid for tid in title_ids if tid not in found_ids]

            try:
                for t in titles:
                    session.delete(t)

                session.commit()
                deleted = list(found_ids)

            except Exception as e:
                session.rollback()
                self.logger.error(f"Error deleting titles {title_ids}: {e}")
                raise

        return {
            "deleted": deleted,
            "not_found": not_found,
        }