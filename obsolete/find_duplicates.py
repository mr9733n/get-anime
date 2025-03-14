import os
import io
import sys
import shutil
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.tables import Base, TitleTeamRelation, TeamMember


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
base_dir = os.path.join(ROOT_DIR, "midnight")
log_path = os.path.join(ROOT_DIR, "logs")
build_dir = os.path.join(ROOT_DIR, 'dist/AnimePlayer')
# db_dir = os.path.join(build_dir, 'db')
db_dir = os.path.join(ROOT_DIR, 'db')
db_path = os.path.join(db_dir, 'anime_player.db')
DATABASE_URL = f"sqlite:///{db_path}"
RESULT_PATH = os.path.join(log_path, "find_duplicates_result.txt")


def backup_database():
    """Создает резервную копию базы данных."""
    source_db_path = db_path
    backup_folder = os.path.join(os.path.expanduser("~"), "Desktop", "db")

    os.makedirs(backup_folder, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file_name = f"anime_player_{timestamp}.db"
    backup_path = os.path.join(backup_folder, backup_file_name)

    try:
        if os.path.exists(source_db_path):
            shutil.copy2(source_db_path, backup_path)
            print(f"✅ Database backup saved: {backup_path}")
            return True
        else:
            print(f"⚠️ Database file not found: {source_db_path}")
            return False
    except Exception as e:
        print(f"❌ Error copying DB: {e}")
        return False


def find_duplicates_in_title_team_relation(session):
    """Находит дубликаты в таблице связей title_team_relation."""
    # Запрос для поиска дубликатов: группировка по title_id и team_member_id
    # с подсчетом количества записей
    query = text("""
    SELECT title_id, team_member_id, COUNT(*) as count, 
           GROUP_CONCAT(id) as relation_ids,
           GROUP_CONCAT(last_updated) as update_dates
    FROM title_team_relation
    GROUP BY title_id, team_member_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        title_id = row[0]
        team_member_id = row[1]
        count = row[2]
        relation_ids = row[3].split(',')
        update_dates = row[4].split(',')

        # Получаем имя team_member
        team_member = session.query(TeamMember).filter_by(id=team_member_id).first()
        team_member_name = team_member.name if team_member else "Unknown"

        duplicates.append({
            'title_id': title_id,
            'team_member_id': team_member_id,
            'team_member_name': team_member_name,
            'count': count,
            'relation_ids': relation_ids,
            'update_dates': update_dates
        })

    return duplicates


def fix_duplicates_in_title_team_relation(session, duplicates, keep_latest=True):
    """Исправляет дубликаты в таблице title_team_relation."""
    if not duplicates:
        print("No duplicates to fix.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Преобразуем строковые ID в целочисленные
            relation_ids = [int(id_str) for id_str in dup['relation_ids']]

            # Определяем, какие записи удалить
            if keep_latest:
                # Получаем все связи и сортируем по дате, чтобы найти самую новую
                relations = session.query(TitleTeamRelation).filter(
                    TitleTeamRelation.id.in_(relation_ids)
                ).order_by(TitleTeamRelation.last_updated.desc()).all()

                # Оставляем самую новую запись, удаляем остальные
                keep_id = relations[0].id
                delete_ids = [rel.id for rel in relations[1:]]
            else:
                # Оставляем первую запись, удаляем остальные
                keep_id = relation_ids[0]
                delete_ids = relation_ids[1:]

            # Удаляем дубликаты
            if delete_ids:
                session.query(TitleTeamRelation).filter(
                    TitleTeamRelation.id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for title_id: {dup['title_id']}, team_member: {dup['team_member_name']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for title_id: {dup['title_id']}, team_member: {dup['team_member_name']}: {e}")

    print(f"Total fixed duplicates: {fixed_count}")


def main():
    """Основная функция для запуска проверки и исправления дубликатов."""
    # Создаем резервную копию
    if not backup_database():
        print("Error creating backup. Aborting.")
        return

    # Подключаемся к базе данных
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    output = io.StringIO()
    original_stdout = sys.stdout

    sys.stdout = output
    try:
        print("Starting duplicate detection in title_team_relation table...")
        # Находим дубликаты
        duplicates = find_duplicates_in_title_team_relation(session)

        if not duplicates:
            print("No duplicates found in title_team_relation table.")
            return

        print(f"Found {len(duplicates)} sets of duplicates:")
        for i, dup in enumerate(duplicates[:10], 1):  # Показываем первые 10
            print(f"{i}. title_id: {dup['title_id']}, team_member: {dup['team_member_name']}, count: {dup['count']}")

        if len(duplicates) > 10:
            print(f"... and {len(duplicates) - 10} more.")

        sys.stdout = original_stdout
        print(f"Found {len(duplicates)} sets of duplicates in title_team_relation table.")

        # Запрашиваем подтверждение
        choice = input("Do you want to fix these duplicates? (y/n): ").strip().lower()
        sys.stdout = output
        print(f"User chose to {'fix' if choice == 'y' else 'not fix'} duplicates.")

        if choice == 'y':
            sys.stdout = original_stdout
            keep_latest = input("Keep the latest record for each duplicate? (y/n, default: y): ").strip().lower()
            keep_latest = keep_latest != 'n'  # Если не 'n', то True
            sys.stdout = output
            print(f"User chose to keep {'latest' if keep_latest else 'first'} records.")
            fix_duplicates_in_title_team_relation(session, duplicates, keep_latest)
            print("Duplicate fixing completed.")
        else:
            print("Operation cancelled.")

    except Exception as e:
        print(f"Error during duplicate processing: {e}")
    finally:
        # Восстанавливаем стандартный stdout в любом случае
        sys.stdout = original_stdout

        # Получаем накопленный вывод
        result_text = output.getvalue()

        # Выводим содержимое результатов на экран
        print("\n--- Processing Results ---")
        print(result_text)

        try:
            # Пытаемся сохранить результаты в файл
            with open(RESULT_PATH, 'w', encoding='utf-8') as f:
                f.write(result_text)
            print(f"\n✅ Результаты сохранены в {RESULT_PATH}")
        except Exception as file_error:
            print(f"❌ Ошибка при сохранении результатов в файл: {file_error}")
            print(f"Путь к файлу: {RESULT_PATH}")

            # Пробуем создать файл в текущей директории как запасной вариант
            try:
                fallback_path = os.path.join(os.getcwd(), "find_duplicates_result.txt")
                with open(fallback_path, 'w', encoding='utf-8') as f:
                    f.write(result_text)
                print(f"✅ Результаты сохранены в резервный файл: {fallback_path}")
            except Exception as fallback_error:
                print(f"❌ Невозможно сохранить даже в резервный файл: {fallback_error}")

        # Закрываем соединение с БД и буфер
        session.close()
        output.close()


if __name__ == "__main__":
    main()