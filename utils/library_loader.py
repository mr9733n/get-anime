import ctypes
import hashlib
import os
import logging

logger = logging.getLogger(__name__)

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file."""
    hash_function = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_function.update(chunk)
        return hash_function.hexdigest().lower()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        logger.error(f"Error calculating file hash: {e}")
        return e

def verify_library(file_path, expected_hash):
    """Проверяет хэш библиотеки."""
    try:
        actual_hash =  calculate_file_hash(file_path)
        if actual_hash != expected_hash.lower():
            logger.error(f"Expected: {expected_hash}")
            logger.error(f"Actual: {actual_hash}")
            logger.critical("!!!HASH WAS NOT EQUAL. CAN BE MALICIOUS!!!")
            return False
        logger.info(f"Verified successfully: {file_path}")
        return True
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
