import os
import io
import sys
import shutil
import argparse

from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.tables import Base, TitleTeamRelation, TeamMember, TitleGenreRelation, \
    Genre, FranchiseRelease, Franchise, Schedule, Rating, History, Poster, \
    Episode, Torrent, ProductionStudio, Template, AppState

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
base_dir = os.path.join(ROOT_DIR, "midnight")
log_path = os.path.join(ROOT_DIR, "logs")
build_dir = os.path.join(ROOT_DIR, 'dist/AnimePlayer')
db_dir1 = os.path.join(ROOT_DIR, 'db')
db_dir2 = os.path.join(build_dir, 'db')
DB_PATH1 = os.path.join(db_dir1, 'anime_player.db')
DB_PATH2 = os.path.join(db_dir2, 'anime_player.db')
RESULT_PATH = os.path.join(log_path, "find_duplicates_result.txt")


def backup_database(db_path):
    """Creates a backup of the database."""
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


def select_database(auto_choice=None):
    """
    Allows user to select which database to use.

    Args:
        auto_choice (str, optional): Automatically use this choice ('1' for development, '2' for production)

    Returns:
        str: Database path
    """
    # Check if both database paths exist
    path1_exists = os.path.exists(DB_PATH1)
    path2_exists = os.path.exists(DB_PATH2)

    if not path1_exists and not path2_exists:
        print("❌ Error: No database files found!")
        print(f"Development path: {DB_PATH1}")
        print(f"Production path: {DB_PATH2}")
        sys.exit(1)

    # Show database options
    print("\n=== Database Selection ===")
    print(f"1. Development DB: {DB_PATH1}" + (" [EXISTS]" if path1_exists else " [NOT FOUND]"))
    print(f"2. Production DB: {DB_PATH2}" + (" [EXISTS]" if path2_exists else " [NOT FOUND]"))

    # Set default to production (choice '2')
    default_choice = '2'

    # Get user choice or use auto_choice
    if auto_choice in ['1', '2']:
        db_choice = auto_choice
        print(f"Using {'Development' if db_choice == '1' else 'Production'} database (auto-selected)")
    else:
        # Change the prompt to indicate the default
        while True:
            db_choice = input(f"Please select database (1/2, default: {default_choice}): ").strip()
            if db_choice == '':  # Empty input means use default
                db_choice = default_choice
                print(f"Using default (Production) database")
            if db_choice in ['1', '2']:
                break
            print("Invalid choice. Please enter 1 or 2.")

    # Set database path based on choice
    if db_choice == '1':
        if not path1_exists:
            print(f"⚠️ Warning: Development database not found at {DB_PATH1}")
            if path2_exists and input("Use production database instead? (y/n): ").lower() == 'y':
                db_path = DB_PATH2
                print(f"Using production database: {DB_PATH2}")
            else:
                print("Operation cancelled.")
                sys.exit(1)
        else:
            db_path = DB_PATH1
            print(f"Using development database: {DB_PATH1}")
    else:  # db_choice == '2'
        if not path2_exists:
            print(f"⚠️ Warning: Production database not found at {DB_PATH2}")
            if path1_exists and input("Use development database instead? (y/n): ").lower() == 'y':
                db_path = DB_PATH1
                print(f"Using development database: {DB_PATH1}")
            else:
                print("Operation cancelled.")
                sys.exit(1)
        else:
            db_path = DB_PATH2
            print(f"Using production database: {DB_PATH2}")

    return db_path

# TITLE TEAM RELATION TABLE

def find_duplicates_in_title_team_relation(session):
    """Finds duplicates in the title_team_relation table."""
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

        # Get the team_member name
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
    """Fixes duplicates in the title_team_relation table."""
    if not duplicates:
        print("No duplicates to fix in title_team_relation.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            relation_ids = [int(id_str) for id_str in dup['relation_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all relations and sort by date to find the newest
                relations = session.query(TitleTeamRelation).filter(
                    TitleTeamRelation.id.in_(relation_ids)
                ).order_by(TitleTeamRelation.last_updated.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = relations[0].id
                delete_ids = [rel.id for rel in relations[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = relation_ids[0]
                delete_ids = relation_ids[1:]

            # Delete duplicates
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

    print(f"Total fixed duplicates in title_team_relation: {fixed_count}")


# TITLE GENRE RELATION TABLE

def find_duplicates_in_title_genre_relation(session):
    """Finds duplicates in the title_genre_relation table."""
    query = text("""
    SELECT title_id, genre_id, COUNT(*) as count, 
           GROUP_CONCAT(id) as relation_ids,
           GROUP_CONCAT(last_updated) as update_dates
    FROM title_genre_relation
    GROUP BY title_id, genre_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        title_id = row[0]
        genre_id = row[1]
        count = row[2]
        relation_ids = row[3].split(',')
        update_dates = row[4].split(',')

        # Get the genre name
        genre = session.query(Genre).filter_by(genre_id=genre_id).first()
        genre_name = genre.name if genre else "Unknown"

        duplicates.append({
            'title_id': title_id,
            'genre_id': genre_id,
            'genre_name': genre_name,
            'count': count,
            'relation_ids': relation_ids,
            'update_dates': update_dates
        })

    return duplicates


def fix_duplicates_in_title_genre_relation(session, duplicates, keep_latest=True):
    """Fixes duplicates in the title_genre_relation table."""
    if not duplicates:
        print("No duplicates to fix in title_genre_relation.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            relation_ids = [int(id_str) for id_str in dup['relation_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all relations and sort by date to find the newest
                relations = session.query(TitleGenreRelation).filter(
                    TitleGenreRelation.id.in_(relation_ids)
                ).order_by(TitleGenreRelation.last_updated.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = relations[0].id
                delete_ids = [rel.id for rel in relations[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = relation_ids[0]
                delete_ids = relation_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(TitleGenreRelation).filter(
                    TitleGenreRelation.id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for title_id: {dup['title_id']}, genre: {dup['genre_name']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for title_id: {dup['title_id']}, genre: {dup['genre_name']}: {e}")

    print(f"Total fixed duplicates in title_genre_relation: {fixed_count}")


# FRANCHISE RELEASES TABLE

def find_duplicates_in_franchise_releases(session):
    """Finds duplicates in the franchise_releases table."""
    query = text("""
    SELECT franchise_id, title_id, ordinal, COUNT(*) as count, 
           GROUP_CONCAT(id) as relation_ids,
           GROUP_CONCAT(last_updated) as update_dates
    FROM franchise_releases
    GROUP BY franchise_id, title_id, ordinal
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        franchise_id = row[0]
        title_id = row[1]
        ordinal = row[2]
        count = row[3]
        relation_ids = row[4].split(',') if row[4] else []
        update_dates = row[5].split(',') if row[5] else []

        # Get the franchise name
        franchise = session.query(Franchise).filter_by(id=franchise_id).first()
        franchise_name = franchise.franchise_name if franchise else "Unknown"

        duplicates.append({
            'franchise_id': franchise_id,
            'title_id': title_id,
            'ordinal': ordinal,
            'franchise_name': franchise_name,
            'count': count,
            'relation_ids': relation_ids,
            'update_dates': update_dates
        })

    return duplicates


def fix_duplicates_in_franchise_releases(session, duplicates, keep_latest=True):
    """Fixes duplicates in the franchise_releases table."""
    if not duplicates:
        print("No duplicates to fix in franchise_releases.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            relation_ids = [int(id_str) for id_str in dup['relation_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all relations and sort by date to find the newest
                relations = session.query(FranchiseRelease).filter(
                    FranchiseRelease.id.in_(relation_ids)
                ).order_by(FranchiseRelease.last_updated.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = relations[0].id
                delete_ids = [rel.id for rel in relations[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = relation_ids[0]
                delete_ids = relation_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(FranchiseRelease).filter(
                    FranchiseRelease.id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for franchise: {dup['franchise_name']}, title_id: {dup['title_id']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for franchise: {dup['franchise_name']}, title_id: {dup['title_id']}: {e}")

    print(f"Total fixed duplicates in franchise_releases: {fixed_count}")


# SCHEDULE TABLE

def find_duplicates_in_schedule(session):
    """Finds duplicates in the schedule table."""
    query = text("""
    SELECT day_of_week, title_id, COUNT(*) as count
    FROM schedule
    GROUP BY day_of_week, title_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        day_of_week = row[0]
        title_id = row[1]
        count = row[2]

        duplicates.append({
            'day_of_week': day_of_week,
            'title_id': title_id,
            'count': count
        })

    return duplicates


def fix_duplicates_in_schedule(session, duplicates, keep_latest=True):
    """Fixes duplicates in the schedule table."""
    if not duplicates:
        print("No duplicates to fix in schedule.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Keep only one record for each day_of_week and title_id combination
            # Since schedule uses a composite primary key (day_of_week, title_id),
            # we can't directly delete by ID. We need to fetch all duplicates first.
            schedules = session.query(Schedule).filter_by(
                day_of_week=dup['day_of_week'],
                title_id=dup['title_id']
            ).order_by(Schedule.last_updated.desc() if keep_latest else Schedule.last_updated.asc()).all()

            # Keep the first record (either newest or oldest based on keep_latest)
            # Delete the rest
            for schedule in schedules[1:]:
                session.delete(schedule)

            session.commit()
            fixed_count += len(schedules) - 1
            print(
                f"Fixed {len(schedules) - 1} duplicates for day_of_week: {dup['day_of_week']}, title_id: {dup['title_id']}")

        except Exception as e:
            session.rollback()
            print(f"Error fixing duplicates for day_of_week: {dup['day_of_week']}, title_id: {dup['title_id']}: {e}")

    print(f"Total fixed duplicates in schedule: {fixed_count}")


# RATINGS TABLE

def find_duplicates_in_ratings(session):
    """Finds duplicates in the ratings table."""
    query = text("""
    SELECT title_id, rating_name, COUNT(*) as count, 
           GROUP_CONCAT(rating_id) as rating_ids,
           GROUP_CONCAT(last_updated) as update_dates
    FROM ratings
    GROUP BY title_id, rating_name
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        title_id = row[0]
        rating_name = row[1]
        count = row[2]
        rating_ids = row[3].split(',')
        update_dates = row[4].split(',')

        duplicates.append({
            'title_id': title_id,
            'rating_name': rating_name,
            'count': count,
            'rating_ids': rating_ids,
            'update_dates': update_dates
        })

    return duplicates


def fix_duplicates_in_ratings(session, duplicates, keep_latest=True):
    """Fixes duplicates in the ratings table."""
    if not duplicates:
        print("No duplicates to fix in ratings.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            rating_ids = [int(id_str) for id_str in dup['rating_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all ratings and sort by date to find the newest
                ratings = session.query(Rating).filter(
                    Rating.rating_id.in_(rating_ids)
                ).order_by(Rating.last_updated.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = ratings[0].rating_id
                delete_ids = [rating.rating_id for rating in ratings[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = rating_ids[0]
                delete_ids = rating_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(Rating).filter(
                    Rating.rating_id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for title_id: {dup['title_id']}, rating_name: {dup['rating_name']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for title_id: {dup['title_id']}, rating_name: {dup['rating_name']}: {e}")

    print(f"Total fixed duplicates in ratings: {fixed_count}")


# HISTORY TABLE

def find_duplicates_in_history(session):
    """Finds duplicates in the history table."""
    query = text("""
    SELECT user_id, title_id, episode_id, torrent_id, COUNT(*) as count, 
           GROUP_CONCAT(id) as history_ids,
           GROUP_CONCAT(last_watched_at) as watch_dates
    FROM history
    GROUP BY user_id, title_id, episode_id, torrent_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        user_id = row[0]
        title_id = row[1]
        episode_id = row[2]
        torrent_id = row[3]
        count = row[4]
        history_ids = row[5].split(',')
        watch_dates = row[6].split(',') if row[6] else []

        duplicates.append({
            'user_id': user_id,
            'title_id': title_id,
            'episode_id': episode_id,
            'torrent_id': torrent_id,
            'count': count,
            'history_ids': history_ids,
            'watch_dates': watch_dates
        })

    return duplicates


def fix_duplicates_in_history(session, duplicates, keep_latest=True):
    """Fixes duplicates in the history table."""
    if not duplicates:
        print("No duplicates to fix in history.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            history_ids = [int(id_str) for id_str in dup['history_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all history records and sort by date to find the newest
                histories = session.query(History).filter(
                    History.id.in_(history_ids)
                ).order_by(History.last_watched_at.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = histories[0].id
                delete_ids = [h.id for h in histories[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = history_ids[0]
                delete_ids = history_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(History).filter(
                    History.id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for user_id: {dup['user_id']}, title_id: {dup['title_id']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for user_id: {dup['user_id']}, title_id: {dup['title_id']}: {e}")

    print(f"Total fixed duplicates in history: {fixed_count}")


# POSTERS TABLE

def find_duplicates_in_posters(session):
    """Finds duplicates in the posters table."""
    query = text("""
    SELECT title_id, COUNT(*) as count, 
           GROUP_CONCAT(poster_id) as poster_ids,
           GROUP_CONCAT(last_updated) as update_dates
    FROM posters
    GROUP BY title_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        title_id = row[0]
        count = row[1]
        poster_ids = row[2].split(',')
        update_dates = row[3].split(',')

        duplicates.append({
            'title_id': title_id,
            'count': count,
            'poster_ids': poster_ids,
            'update_dates': update_dates
        })

    return duplicates


def fix_duplicates_in_posters(session, duplicates, keep_latest=True):
    """Fixes duplicates in the posters table."""
    if not duplicates:
        print("No duplicates to fix in posters.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            poster_ids = [int(id_str) for id_str in dup['poster_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all posters and sort by date to find the newest
                posters = session.query(Poster).filter(
                    Poster.poster_id.in_(poster_ids)
                ).order_by(Poster.last_updated.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = posters[0].poster_id
                delete_ids = [poster.poster_id for poster in posters[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = poster_ids[0]
                delete_ids = poster_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(Poster).filter(
                    Poster.poster_id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for title_id: {dup['title_id']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for title_id: {dup['title_id']}: {e}")

    print(f"Total fixed duplicates in posters: {fixed_count}")


# EPISODES TABLE

def find_duplicates_in_episodes(session):
    """Finds duplicates in the episodes table."""
    query = text("""
    SELECT title_id, episode_number, COUNT(*) as count, 
           GROUP_CONCAT(episode_id) as episode_ids,
           GROUP_CONCAT(created_timestamp) as timestamps
    FROM episodes
    GROUP BY title_id, episode_number
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        title_id = row[0]
        episode_number = row[1]
        count = row[2]
        episode_ids = row[3].split(',')
        timestamps = row[4].split(',') if row[4] else []

        duplicates.append({
            'title_id': title_id,
            'episode_number': episode_number,
            'count': count,
            'episode_ids': episode_ids,
            'timestamps': timestamps
        })

    return duplicates


def fix_duplicates_in_episodes(session, duplicates, keep_latest=True):
    """Fixes duplicates in the episodes table."""
    if not duplicates:
        print("No duplicates to fix in episodes.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            episode_ids = [int(id_str) for id_str in dup['episode_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all episodes and sort by date to find the newest
                episodes = session.query(Episode).filter(
                    Episode.episode_id.in_(episode_ids)
                ).order_by(Episode.created_timestamp.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = episodes[0].episode_id
                delete_ids = [ep.episode_id for ep in episodes[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = episode_ids[0]
                delete_ids = episode_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(Episode).filter(
                    Episode.episode_id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for title_id: {dup['title_id']}, episode: {dup['episode_number']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for title_id: {dup['title_id']}, episode: {dup['episode_number']}: {e}")

    print(f"Total fixed duplicates in episodes: {fixed_count}")


# TORRENTS TABLE

def find_duplicates_in_torrents(session):
    """Finds duplicates in the torrents table."""
    query = text("""
    SELECT title_id, hash, COUNT(*) as count, 
           GROUP_CONCAT(torrent_id) as torrent_ids,
           GROUP_CONCAT(uploaded_timestamp) as timestamps
    FROM torrents
    GROUP BY title_id, hash
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        title_id = row[0]
        hash_value = row[1]
        count = row[2]
        torrent_ids = row[3].split(',')
        timestamps = row[4].split(',') if row[4] else []

        duplicates.append({
            'title_id': title_id,
            'hash': hash_value,
            'count': count,
            'torrent_ids': torrent_ids,
            'timestamps': timestamps
        })

    return duplicates


def fix_duplicates_in_torrents(session, duplicates, keep_latest=True):
    """Fixes duplicates in the torrents table."""
    if not duplicates:
        print("No duplicates to fix in torrents.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            torrent_ids = [int(id_str) for id_str in dup['torrent_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all torrents and sort by date to find the newest
                torrents = session.query(Torrent).filter(
                    Torrent.torrent_id.in_(torrent_ids)
                ).order_by(Torrent.uploaded_timestamp.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = torrents[0].torrent_id
                delete_ids = [t.torrent_id for t in torrents[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = torrent_ids[0]
                delete_ids = torrent_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(Torrent).filter(
                    Torrent.torrent_id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for title_id: {dup['title_id']}, hash: {dup['hash']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for title_id: {dup['title_id']}, hash: {dup['hash']}: {e}")

    print(f"Total fixed duplicates in torrents: {fixed_count}")


# FRANCHISES TABLE

def find_duplicates_in_franchises(session):
    """Finds duplicates in the franchises table."""
    query = text("""
    SELECT title_id, franchise_id, COUNT(*) as count, 
           GROUP_CONCAT(id) as franchise_ids,
           GROUP_CONCAT(last_updated) as update_dates
    FROM franchises
    GROUP BY title_id, franchise_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        title_id = row[0]
        franchise_id = row[1]
        count = row[2]
        ids = row[3].split(',')
        update_dates = row[4].split(',') if row[4] else []

        duplicates.append({
            'title_id': title_id,
            'franchise_id': franchise_id,
            'count': count,
            'franchise_ids': ids,
            'update_dates': update_dates
        })

    return duplicates


def fix_duplicates_in_franchises(session, duplicates, keep_latest=True):
    """Fixes duplicates in the franchises table."""
    if not duplicates:
        print("No duplicates to fix in franchises.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            franchise_ids = [int(id_str) for id_str in dup['franchise_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all franchises and sort by date to find the newest
                franchises = session.query(Franchise).filter(
                    Franchise.id.in_(franchise_ids)
                ).order_by(Franchise.last_updated.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = franchises[0].id
                delete_ids = [f.id for f in franchises[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = franchise_ids[0]
                delete_ids = franchise_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(Franchise).filter(
                    Franchise.id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for title_id: {dup['title_id']}, franchise_id: {dup['franchise_id']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for title_id: {dup['title_id']}, franchise_id: {dup['franchise_id']}: {e}")

    print(f"Total fixed duplicates in franchises: {fixed_count}")


# PRODUCTION STUDIOS TABLE

def find_duplicates_in_production_studios(session):
    """Finds duplicates in the production_studios table."""
    query = text("""
    SELECT title_id, COUNT(*) as count, 
           GROUP_CONCAT(name) as studio_names,
           GROUP_CONCAT(last_updated) as update_dates
    FROM production_studios
    GROUP BY title_id
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        title_id = row[0]
        count = row[1]
        studio_names = row[2].split(',')
        update_dates = row[3].split(',') if row[3] else []

        duplicates.append({
            'title_id': title_id,
            'count': count,
            'studio_names': studio_names,
            'update_dates': update_dates
        })

    return duplicates


def fix_duplicates_in_production_studios(session, duplicates, keep_latest=True):
    """Fixes duplicates in the production_studios table."""
    if not duplicates:
        print("No duplicates to fix in production_studios.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Since title_id is the primary key, we need to handle this differently
            # Get all studios with this title_id
            studios = session.query(ProductionStudio).filter_by(
                title_id=dup['title_id']
            ).order_by(ProductionStudio.last_updated.desc() if keep_latest else ProductionStudio.last_updated.asc()).all()

            # Keep the first studio (either newest or oldest based on keep_latest)
            # Delete the rest
            for studio in studios[1:]:
                session.delete(studio)

            session.commit()
            fixed_count += len(studios) - 1
            print(f"Fixed {len(studios) - 1} duplicates for title_id: {dup['title_id']}")

        except Exception as e:
            session.rollback()
            print(f"Error fixing duplicates for title_id: {dup['title_id']}: {e}")

    print(f"Total fixed duplicates in production_studios: {fixed_count}")


# TEMPLATES TABLE

def find_duplicates_in_templates(session):
    """Finds duplicates in the templates table."""
    query = text("""
    SELECT name, COUNT(*) as count, 
           GROUP_CONCAT(id) as template_ids,
           GROUP_CONCAT(created_at) as creation_dates
    FROM templates
    GROUP BY name
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        name = row[0]
        count = row[1]
        template_ids = row[2].split(',')
        creation_dates = row[3].split(',') if row[3] else []

        duplicates.append({
            'name': name,
            'count': count,
            'template_ids': template_ids,
            'creation_dates': creation_dates
        })

    return duplicates


def fix_duplicates_in_templates(session, duplicates, keep_latest=True):
    """Fixes duplicates in the templates table."""
    if not duplicates:
        print("No duplicates to fix in templates.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Convert string IDs to integers
            template_ids = [int(id_str) for id_str in dup['template_ids']]

            # Determine which records to delete
            if keep_latest:
                # Get all templates and sort by date to find the newest
                templates = session.query(Template).filter(
                    Template.id.in_(template_ids)
                ).order_by(Template.created_at.desc()).all()

                # Keep the newest record, delete the rest
                keep_id = templates[0].id
                delete_ids = [t.id for t in templates[1:]]
            else:
                # Keep the first record, delete the rest
                keep_id = template_ids[0]
                delete_ids = template_ids[1:]

            # Delete duplicates
            if delete_ids:
                session.query(Template).filter(
                    Template.id.in_(delete_ids)
                ).delete(synchronize_session=False)

                session.commit()
                fixed_count += len(delete_ids)
                print(
                    f"Fixed {len(delete_ids)} duplicates for template name: {dup['name']}")

        except Exception as e:
            session.rollback()
            print(
                f"Error fixing duplicates for template name: {dup['name']}: {e}")

    print(f"Total fixed duplicates in templates: {fixed_count}")


# APP_STATE TABLE

def find_duplicates_in_app_state(session):
    """Finds duplicates in the app_state table."""
    query = text("""
    SELECT key, COUNT(*) as count, 
           GROUP_CONCAT(created_at) as creation_dates
    FROM app_state
    GROUP BY key
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
    """)

    result = session.execute(query)
    duplicates = []

    for row in result:
        key = row[0]
        count = row[1]
        creation_dates = row[2].split(',') if row[2] else []

        duplicates.append({
            'key': key,
            'count': count,
            'creation_dates': creation_dates
        })

    return duplicates


def fix_duplicates_in_app_state(session, duplicates, keep_latest=True):
    """Fixes duplicates in the app_state table."""
    if not duplicates:
        print("No duplicates to fix in app_state.")
        return

    fixed_count = 0
    for dup in duplicates:
        try:
            # Since key is the primary key, handle this case differently
            # Get all app_state entries with this key
            app_states = session.query(AppState).filter_by(
                key=dup['key']
            ).order_by(AppState.created_at.desc() if keep_latest else AppState.created_at.asc()).all()

            # Keep the first entry (either newest or oldest based on keep_latest)
            # Delete the rest
            for app_state in app_states[1:]:
                session.delete(app_state)

            session.commit()
            fixed_count += len(app_states) - 1
            print(f"Fixed {len(app_states) - 1} duplicates for key: {dup['key']}")

        except Exception as e:
            session.rollback()
            print(f"Error fixing duplicates for key: {dup['key']}: {e}")

    print(f"Total fixed duplicates in app_state: {fixed_count}")


def run_table_check(session, table_name, find_function, output_file=None):
    """Helper function to run a specific table check and return detailed results."""
    duplicates = find_function(session)
    if output_file:
        output_file.write(f"\n--- Checking {table_name} table ---\n")
        output_file.write(f"Found {len(duplicates)} sets of duplicates in {table_name} table.\n")
    return duplicates


def main(auto_fix=False, keep_latest=True, selected_tables=None, db_choice=None, skip_backup=False):
    """Main function to run duplication checking and fixing.

    Args:
        auto_fix (bool): Whether to automatically fix duplicates without confirmation
        keep_latest (bool): Whether to keep the latest record (True) or the oldest (False)
        selected_tables (list): List of table names to check, or None for all tables
    """
    db_path = select_database(db_choice)
    database_url = f"sqlite:///{db_path}"

    # Get command line arguments if provided
    args = sys.argv[1:] if hasattr(sys, 'argv') else []
    if '--auto-fix' in args:
        auto_fix = True
    if '--keep-oldest' in args:
        keep_latest = False

    # Create a backup
    if not skip_backup:
        if not backup_database(db_path):
            print("Error creating backup. Aborting.")
            return
    else:
        print("Skipping database backup as requested.")

    # Connect to the database
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    output = io.StringIO()
    original_stdout = sys.stdout

    sys.stdout = output
    try:
        print("=== DUPLICATE DETECTION STARTED ===")

        # Dictionary to store all duplicate records
        all_duplicates = {}

        # Define all tables and their corresponding functions
        all_tables = {
            'title_team_relation': find_duplicates_in_title_team_relation,
            'title_genre_relation': find_duplicates_in_title_genre_relation,
            'franchise_releases': find_duplicates_in_franchise_releases,
            'schedule': find_duplicates_in_schedule,
            'ratings': find_duplicates_in_ratings,
            'history': find_duplicates_in_history,
            'posters': find_duplicates_in_posters,
            'episodes': find_duplicates_in_episodes,
            'torrents': find_duplicates_in_torrents,
            'franchises': find_duplicates_in_franchises,
            'production_studios': find_duplicates_in_production_studios,
            'templates': find_duplicates_in_templates,
            'app_state': find_duplicates_in_app_state
        }

        # Filter tables if selected_tables is provided
        if selected_tables:
            tables_to_check = {k: v for k, v in all_tables.items() if k in selected_tables}
            if not tables_to_check:
                print(
                    f"Warning: None of the provided tables ({', '.join(selected_tables)}) were valid. Checking all tables.")
                tables_to_check = all_tables
        else:
            tables_to_check = all_tables

        # Find duplicates in each table
        for table_name, find_function in tables_to_check.items():
            print(f"\n--- Checking {table_name} table ---")
            duplicates = find_function(session)
            all_duplicates[table_name] = duplicates
            print(f"Found {len(duplicates)} sets of duplicates in {table_name} table.")

        # Check if any duplicates were found
        total_duplicates = sum(len(dups) for dups in all_duplicates.values())
        if total_duplicates == 0:
            print("\nNo duplicates found in any tables.")
            return

        # Print summary of duplicates
        print("\n=== DUPLICATE SUMMARY ===")
        for table, duplicates in all_duplicates.items():
            if duplicates:
                print(f"{table}: {len(duplicates)} sets of duplicates")
                # Show first 5 duplicates for each table
                for i, dup in enumerate(duplicates[:5], 1):
                    if table == 'title_team_relation':
                        print(
                            f"  {i}. title_id: {dup['title_id']}, team_member: {dup['team_member_name']}, count: {dup['count']}")
                    elif table == 'title_genre_relation':
                        print(f"  {i}. title_id: {dup['title_id']}, genre: {dup['genre_name']}, count: {dup['count']}")
                    elif table == 'franchise_releases':
                        print(
                            f"  {i}. franchise: {dup['franchise_name']}, title_id: {dup['title_id']}, count: {dup['count']}")
                    elif table == 'schedule':
                        print(
                            f"  {i}. day_of_week: {dup['day_of_week']}, title_id: {dup['title_id']}, count: {dup['count']}")
                    elif table == 'ratings':
                        print(
                            f"  {i}. title_id: {dup['title_id']}, rating_name: {dup['rating_name']}, count: {dup['count']}")
                    elif table == 'history':
                        print(f"  {i}. user_id: {dup['user_id']}, title_id: {dup['title_id']}, count: {dup['count']}")
                    elif table == 'posters':
                        print(f"  {i}. title_id: {dup['title_id']}, count: {dup['count']}")

                if len(duplicates) > 5:
                    print(f"  ... and {len(duplicates) - 5} more.")

        sys.stdout = original_stdout
        print(f"Found {total_duplicates} total sets of duplicates across all tables.")

        # Ask for confirmation to fix duplicates (unless auto_fix is True)
        fix_choice = 'y' if auto_fix else input("Do you want to fix these duplicates? (y/n): ").strip().lower()
        sys.stdout = output
        print(
            f"{'Auto-fixing' if auto_fix else 'User chose to ' + ('fix' if fix_choice == 'y' else 'not fix')} duplicates.")

        if fix_choice == 'y':
            if not auto_fix:
                sys.stdout = original_stdout
                keep_latest_input = input(
                    "Keep the latest record for each duplicate? (y/n, default: y): ").strip().lower()
                keep_latest = keep_latest_input != 'n'  # If not 'n', then True
                sys.stdout = output
            print(f"Will keep {'latest' if keep_latest else 'first'} records.")

            # Map table names to fix functions
            fix_functions = {
                'title_team_relation': fix_duplicates_in_title_team_relation,
                'title_genre_relation': fix_duplicates_in_title_genre_relation,
                'franchise_releases': fix_duplicates_in_franchise_releases,
                'schedule': fix_duplicates_in_schedule,
                'ratings': fix_duplicates_in_ratings,
                'history': fix_duplicates_in_history,
                'posters': fix_duplicates_in_posters,
                'episodes': fix_duplicates_in_episodes,
                'torrents': fix_duplicates_in_torrents,
                'franchises': fix_duplicates_in_franchises,
                'production_studios': fix_duplicates_in_production_studios,
                'templates': fix_duplicates_in_templates,
                'app_state': fix_duplicates_in_app_state
            }

            # Fix duplicates in each table
            print("\n=== FIXING DUPLICATES ===")

            fixed_count = 0
            for table_name, duplicates in all_duplicates.items():
                if duplicates and table_name in fix_functions:
                    print(f"\n--- Fixing {table_name} duplicates ---")
                    fix_functions[table_name](session, duplicates, keep_latest)
                    fixed_count += len(duplicates)

            print("\nDuplicate fixing completed for all tables.")
        else:
            print("Operation cancelled.")

    except Exception as e:
        print(f"Error during duplicate processing: {e}")
    finally:
        # Restore standard stdout in any case
        sys.stdout = original_stdout

        # Get the accumulated output
        result_text = output.getvalue()

        # Print the results to screen
        print("\n--- Processing Results ---")
        print(result_text)

        try:
            # Try to save results to file
            with open(RESULT_PATH, 'w', encoding='utf-8') as f:
                f.write(result_text)
            print(f"\n✅ Results saved to {RESULT_PATH}")
        except Exception as file_error:
            print(f"❌ Error when saving results to file: {file_error}")
            print(f"File path: {RESULT_PATH}")

            # Try to create a file in the current directory as a fallback
            try:
                fallback_path = os.path.join(os.getcwd(), "find_duplicates_result.txt")
                with open(fallback_path, 'w', encoding='utf-8') as f:
                    f.write(result_text)
                print(f"✅ Results saved to fallback file: {fallback_path}")
            except Exception as fallback_error:
                print(f"❌ Unable to save to fallback file: {fallback_error}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find and fix duplicate records in the anime_player database.')
    parser.add_argument('--auto-fix', action='store_true', help='Automatically fix duplicates without confirmation')
    parser.add_argument('--keep-oldest', action='store_true', help='Keep oldest records instead of latest')
    parser.add_argument('--output', type=str, help='Custom output file path')
    parser.add_argument('--tables', type=str, help='Comma-separated list of tables to check (default: all)')
    parser.add_argument('--no-backup', action='store_true', help='Skip database backup')
    parser.add_argument('--db', type=str, choices=['1', '2'], help='Database to use (1=Development, 2=Production)')
    args = parser.parse_args()

    if args.output:
        RESULT_PATH = args.output

    selected_tables = args.tables.split(',') if args.tables else None
    main(auto_fix=args.auto_fix, keep_latest=not args.keep_oldest,
         selected_tables=selected_tables, db_choice=args.db, skip_backup=args.no_backup)