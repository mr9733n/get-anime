import ctypes
import hashlib
import os
import logging

logger = logging.getLogger(__name__)

def verify_library(file_path, expected_hash):
    """Проверяет хэш библиотеки."""
    try:
        with open(file_path, "rb") as file:
            file_hash = hashlib.sha256(file.read()).hexdigest()
            if file_hash != expected_hash:
                raise ValueError("!!!HASH WAS NOT EQUAL. DLL CAN BE MALICIOUS!!!")
        logger.info(f"Library hash verified successfully: {file_path}")
    except FileNotFoundError:
        raise FileNotFoundError(f"Library file not found: {file_path}")
    except ValueError as e:
        logger.error(e)
        raise

def load_library(lib_dir, lib_name):
    """Загружает указанную библиотеку и проверяет её."""
    lib_path = os.path.abspath(lib_dir)
    lib_file_path = os.path.join(lib_path, lib_name)

    if not os.path.exists(lib_file_path):
        raise FileNotFoundError(f"{lib_name} not found in {lib_path}.")

    try:
        ctypes.CDLL(lib_file_path)
        logger.info(f"{lib_name} successfully loaded from {lib_path}.")
        return lib_file_path
    except OSError as e:
        raise RuntimeError(f"Error loading {lib_name} from {lib_path}: {e}")
