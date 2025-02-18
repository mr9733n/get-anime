import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.tables import Title  # предполагается, что модель Title определена в модуле core.tables

FILE_PATH = "title_ids.txt"

base_dir = os.path.dirname(os.path.abspath(__file__))
db_dir = os.path.join(base_dir, 'db')
db_path = os.path.join(db_dir, 'anime_player.db')
DATABASE_URL = f"sqlite:///{db_path}"


def read_file_title_ids(file_path):
    """
    Считывает идентификаторы из файла.
    Ожидается, что каждая строка имеет формат:
      "https://anilibria.tv/release/zenshuu.html -> 9874"
    Возвращает множество title_id в виде чисел.
    """
    title_ids = set()
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден.")
        return title_ids

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "->" in line:
                parts = line.split("->")
                if len(parts) == 2:
                    tid_str = parts[1].strip()
                    try:
                        tid = int(tid_str)
                        title_ids.add(tid)
                    except ValueError:
                        print(f"Не удалось преобразовать {tid_str} в число")
    return title_ids


def get_db_title_ids(database_url):
    """
    Подключается к базе данных SQLite, выполняет запрос к таблице Title
    и возвращает множество title_id из базы.
    """
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    db_ids = set()
    try:
        results = session.query(Title.title_id).all()
        db_ids = {tid for (tid,) in results}
    except Exception as e:
        print("Ошибка при запросе из базы данных:", e)
    finally:
        session.close()
    return db_ids


def main():
    # Считываем title_id из файла
    file_ids = read_file_title_ids(FILE_PATH)
    print("Title IDs из файла:", sorted(file_ids))

    # Получаем title_id из базы данных
    db_ids = get_db_title_ids(DATABASE_URL)
    print("Title IDs из базы данных:", sorted(db_ids))

    # Вычисляем разницу
    in_file_not_db = file_ids - db_ids
    in_db_not_file = db_ids - file_ids

    print("Есть в файле, но отсутствуют в базе:", sorted(in_file_not_db))
    print("Есть в базе, но отсутствуют в файле:", sorted(in_db_not_file))


if __name__ == "__main__":
    main()
