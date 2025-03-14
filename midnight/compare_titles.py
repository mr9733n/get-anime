import os
import re
import io
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.tables import Title, Poster


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
base_dir = os.path.join(ROOT_DIR, "midnight")
log_path = os.path.join(ROOT_DIR, "logs")
FILE_PATH = os.path.join(log_path, "title_ids.txt")
RESULT_PATH = os.path.join(log_path, "compare_result.txt")
build_dir = os.path.join(ROOT_DIR, 'dist/AnimePlayer')
db_dir = os.path.join(build_dir, 'db')
db_path = os.path.join(db_dir, 'anime_player.db')
DATABASE_URL = f"sqlite:///{db_path}"


def read_file_title_ids_with_posters(file_path):
    """
    Считывает идентификаторы и пути постеров из файла.
    Ожидается, что каждая строка имеет формат:
      "https://anilibria.tv/release/zenshuu.html -> 9874 -> poster_name.jpg"
    Возвращает словарь {title_id: poster_path}
    """
    title_ids_with_posters = {}
    if not os.path.exists(file_path):
        print(f"Файл {file_path} не найден.")
        return title_ids_with_posters

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "->" in line:
                parts = line.split("->")
                if len(parts) >= 3:
                    title_id_part = parts[1].strip()
                    poster_path = parts[2].strip()
                    match = re.search(r'\d+', title_id_part)
                    if match:
                        tid_str = match.group(0)
                        try:
                            tid = int(tid_str)
                            title_ids_with_posters[tid] = poster_path
                        except ValueError:
                            print(f"Не удалось преобразовать {tid_str} в число")
                    else:
                        print(f"Не удалось найти числовой ID в строке: {line}")

    return title_ids_with_posters


def get_db_posters_info(database_url):
    """
    Подключается к базе данных SQLite, выполняет запрос к таблице Title
    и возвращает словарь {title_id: poster_path_original}
    """
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    db_posters = {}
    try:
        results = session.query(Title.title_id, Title.poster_path_original).all()
        for tid, poster_path in results:
            if poster_path:
                match = re.search(r'([^/]+)$', poster_path)
                if match:
                    db_posters[tid] = match.group(1)
                else:
                    db_posters[tid] = poster_path
    except Exception as e:
        print("Ошибка при запросе из базы данных:", e)
    finally:
        session.close()
    return db_posters


def check_titles_without_posters(database_url):
    """
    Проверяет, какие тайтлы не имеют загруженных постеров в базе данных.
    Возвращает список кортежей (title_id, code, name_en)
    """
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    missing_posters = []

    try:
        query = session.query(
            Title.title_id,
            Title.code,
            Title.name_en
        ).outerjoin(
            Poster,
            Title.title_id == Poster.title_id
        ).filter(
            Poster.poster_id == None
        )
        missing_posters = [(title.title_id, title.code, title.name_en) for title in query.all()]

    except Exception as e:
        print(f"Ошибка при проверке тайтлов без постеров: {e}")
    finally:
        session.close()

    return missing_posters


def extract_title_id_from_poster_path(poster_path):
    """
    Извлекает title_id из пути к постеру.
    Args:
        poster_path (str): Полный путь к постеру
    Returns:
        int or None: Извлеченный title_id или None, если извлечение не удалось
    """
    if not poster_path:
        return None
    path_parts = poster_path.split('/')
    for part in reversed(path_parts):
        try:
            potential_title_id = int(part)
            return potential_title_id
        except ValueError:
            continue
    return None


def verify_poster_path_title_id(database_url):
    """
    Проверяет соответствие title_id в пути постера с actual title_id.

    Returns:
        dict: Словарь несоответствий, где ключ - title_id из базы,
              а значение - title_id из пути постера
    """
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    mismatched_ids = {}
    try:
        results = session.query(Title.title_id, Title.poster_path_original).filter(
            Title.poster_path_original.isnot(None)).all()

        for db_title_id, poster_path in results:
            if poster_path:
                extracted_title_id = extract_title_id_from_poster_path(poster_path)

                if extracted_title_id is not None and extracted_title_id != db_title_id:
                    mismatched_ids[db_title_id] = extracted_title_id

    except Exception as e:
        print(f"Ошибка при проверке путей постеров: {e}")
    finally:
        session.close()
    return mismatched_ids


def main():
    output = io.StringIO()
    original_stdout = sys.stdout

    try:
        sys.stdout = output

        file_data = read_file_title_ids_with_posters(FILE_PATH)
        print(f"🔍 Получено {len(file_data)} записей из файла")
        db_data = get_db_posters_info(DATABASE_URL)
        print(f"🗄️ Получено {len(db_data)} записей из базы данных")

        file_ids = set(file_data.keys())
        db_ids = set(db_data.keys())
        in_file_not_db = file_ids - db_ids
        in_db_not_file = db_ids - file_ids

        print("\n📋 Сравнение идентификаторов:")
        print(f"✖ Идентификаторы в файле, отсутствующие в базе:     {sorted(in_file_not_db)}")
        print(f"✖ Идентификаторы в базе, отсутствующие в файле:     {sorted(in_db_not_file)}")

        mismatches = verify_poster_path_title_id(DATABASE_URL)

        if mismatches:
            print(f"\n❗ Несоответствия title_id в пути постера:")
            for db_title_id, path_title_id in mismatches.items():
                print(f"   ◆ В базе: {db_title_id}, В пути постера: {path_title_id}")
        else:
            print(f"\n✅ Несоответствий title_id в пути постера не найдено")

        common_ids = file_ids.intersection(db_ids)
        different_posters = []
        same_posters = []

        for tid in common_ids:
            file_poster = file_data[tid]
            db_poster = db_data[tid]
            if file_poster != db_poster:
                different_posters.append((tid, file_poster, db_poster))
            else:
                same_posters.append(tid)

        print(f"\n📊 Статистика постеров:")
        print(f"   ✓ Тайтлы с одинаковыми постерами:     {len(same_posters)}")
        print(f"   ✗ Тайтлы с разными постерами:         {len(different_posters)}")

        if different_posters:
            print("\n❗ Тайтлы с разными постерами:")
            for i, (tid, file_poster, db_poster) in enumerate(different_posters):
                print(f"   ◆ {tid}: Файл: {file_poster}, БД: {db_poster}")

        missing_posters = check_titles_without_posters(DATABASE_URL)
        print(f"\n⚠️ Количество тайтлов без загруженных постеров: {len(missing_posters)}")

        if missing_posters:
            print("\n❌ Тайтлы без загруженных постеров:")
            for i, (title_id, title_code, title_name) in enumerate(missing_posters):
                print(f"   ◆ {title_id}: {title_code} - {title_name}")

            missing_title_ids = [title_id for title_id, _, _ in missing_posters]
            print(f"\n📝 Список title_id без постеров:")
            print(f"   {sorted(missing_title_ids)}")

        sys.stdout = original_stdout

        result_text = output.getvalue()
        with open(RESULT_PATH, 'w', encoding='utf-8') as f:
            f.write(result_text)

        print(f"\n✅ Результаты сохранены в {RESULT_PATH}")

    except Exception as e:
        sys.stdout = original_stdout
        print(f"❌ Произошла ошибка: {e}")
    finally:
        output.close()


if __name__ == "__main__":
    main()
