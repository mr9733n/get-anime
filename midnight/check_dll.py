import ctypes
import os
import hashlib
import logging
import vlc

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

LIB_DIR = os.path.join(ROOT_DIR, "libs")
LIB_NAME = "libvlc.dll"

def load_library(lib_name, lib_dir=LIB_DIR):
    """
    Загружает указанную библиотеку и возвращает путь к ней.
    Args:
        lib_name (str): Имя библиотеки (например, "libvlc.dll").
        lib_dir (str): Директория, где искать библиотеку.
    Returns:  str: Абсолютный путь к загруженной библиотеке.
    Raises:
        FileNotFoundError: Если библиотека не найдена.
        RuntimeError: Если библиотеку не удалось загрузить.
    """
    lib_path = os.path.abspath(lib_dir)
    lib_file_path = os.path.join(lib_path, lib_name)

    if not os.path.exists(lib_file_path):
        raise FileNotFoundError(f"{lib_name} not found in {lib_path}.")

    try:
        ctypes.CDLL(lib_file_path)
        logger.info(f"{lib_name} successfully loaded from {lib_path}.")
        return lib_file_path
    except OSError as e:
        raise RuntimeError(f"Error loading {lib_name}: {e}")

def calculate_sha256(file_location):
    """
    Вычисляет SHA256-хэш для указанного файла.
    Args:  file_path (str): Путь к файлу.
    Returns: str: Хэш файла в формате строки.
    Raises: FileNotFoundError: Если файл не найден.
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_location, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        logger.error(f"{file_location} not found!")
        return None
    except IOError as e:
        logger.error(f"Error reading file {file_location}: {e}")
        return None

def execute_library_specific_actions(lib_name):
    """
    Выполняет действия, специфичные для конкретной библиотеки.
    Args: lib_name (str): Имя библиотеки.
    Returns: None
    """
    if lib_name == "libvlc.dll":
        logger.info(f"python-vlc version: {vlc.__version__}")
        logger.info(f"libvlc version: {vlc.libvlc_get_version()}")
    else:
        logger.info(f"No specific actions defined for {lib_name}.")

if __name__ == "__main__":
    try:
        library_name = LIB_NAME
        file_path = load_library(library_name)

        execute_library_specific_actions(library_name)

        hash_value = calculate_sha256(file_path)
        if hash_value:
            logger.info(f"SHA256: {hash_value}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
