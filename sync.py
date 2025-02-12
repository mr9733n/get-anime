# sync.py
import ast
import json
import os
import ctypes
import logging
import platform
import subprocess
import sys
import time
import requests
import argparse

from logging.handlers import RotatingFileHandler
from tqdm import tqdm
from pyzbar.pyzbar import decode
from PIL import Image


# Constants
ORIG_DB_NAME = "anime_player.db"
QRCODE_FILE_NAME = "qrcode.png"
DOWNLOAD_DB_NAME = "downloaded.db"
MERGE_UTILITY_NAME = "merge_utility.exe"
TEMP_FOLDER_NAME = "temp"
DYLD_NAME = "DYLD_LIBRARY_PATH"
DYLD_LIBRARY_MAC_PATH = "/opt/homebrew/lib"
LIBRARY_MAC_PATH = "/opt/homebrew/lib/libzbar.dylib"
DYLD_LIBRARY_LINUX_PATH = "/usr/lib"
LIBRARY_LINUX_PATH = "/usr/lib/libzbar.so"
LOG_FOLDER_NAME = "logs"
LOG_FILE_NAME = "merged_log.txt"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Logging configuration
log_dir = os.path.join(BASE_DIR, LOG_FOLDER_NAME)
os.makedirs(log_dir, exist_ok=True)  # Создаёт папку для логов, если её нет
LOG_FILE = os.path.join(log_dir, LOG_FILE_NAME)
# Configure logging
file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.info(f"Anime Player Sync App version 0.0.0.1")

def configure_platform():
    """Настраивает окружение в зависимости от операционной системы."""
    platform_name = platform.system()
    paths = {
        "Windows": {"library": None, "env_var": None, "env_path": None},  # Windows не требует zbar

        "Darwin": {"library": LIBRARY_MAC_PATH, "env_var": DYLD_NAME, "env_path": DYLD_LIBRARY_MAC_PATH},
        "Linux": {"library": LIBRARY_LINUX_PATH, "env_var": DYLD_NAME, "env_path": DYLD_LIBRARY_LINUX_PATH},
    }

    config = paths.get(platform_name)
    if not config:
        logger.error(f"Unsupported platform: {platform_name}")
        raise ImportError(f"Unsupported platform: {platform_name}")

    try:
        if config["env_path"]:
            os.environ[config["env_var"]] = config["env_path"]
            logger.info(f"Setting environment variable {config['env_var']} to {config['env_path']}.")
        if config["library"]:
            ctypes.CDLL(config["library"])
            logger.info(f"Successfully loaded library: {config['library']}.")
    except OSError as e:
        logger.error(f"Failed to load library for {platform_name}: {e}")
        raise ImportError(f"Cannot load library for {platform_name}: {e}")
    return platform_name

def download_file_with_progress(import_url, output_path, import_file_size=None, timeout=600, retries=3):
    """Download a file from a URL with a progress bar and retries."""
    for attempt in range(retries):
        try:
            logger.info(f"Attempt {attempt + 1} to download file from {import_url}.")

            response = requests.get(import_url, stream=True, timeout=timeout)
            if response.status_code != 200:
                logger.error(f"Failed to download file: {response.status_code} - {response.reason}")
                raise ValueError(f"Cannot access URL: {import_url}")

            total_size = import_file_size or int(response.headers.get('content-length', 0))
            logger.info(f"Total file size: {total_size} bytes.")

            with open(output_path, 'wb') as f, tqdm(
                desc=f"Downloading {os.path.basename(output_path)}",
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

            downloaded_file_size = os.path.getsize(output_path)
            if 0 < total_size != downloaded_file_size:
                logger.error(f"Incomplete download: {downloaded_file_size}/{total_size} bytes downloaded.")
                raise ValueError("Downloaded file is incomplete.")

            logger.info(f"File successfully downloaded to {output_path} [{downloaded_file_size} bytes].")
            return  # Exit the function after a successful download

        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"Error during file download: {e}")
            if attempt < retries - 1:
                logger.info("Retrying download in 5 seconds...")
                time.sleep(5)
            else:
                raise

    logger.error(f"Failed to download file after {retries} attempts.")
    raise RuntimeError("Maximum retry attempts exceeded.")


def decode_qr_code(file_path):
    """Reads a QR code from an image and returns the decoded JSON object."""
    try:
        image = Image.open(file_path)
        decoded_objects = decode(image)
        if not decoded_objects:
            raise ValueError("QR code not found or could not be read.")

        data = decoded_objects[0].data.decode('utf-8')
        logger.info(f"Decoded QR code data: {data}")

        # Attempt to parse as a Python dictionary
        try:
            python_data = ast.literal_eval(data)
            json_data = json.loads(json.dumps(python_data))  # Convert to JSON-compatible dict
            logger.info("Successfully decoded data from QR code.")
            return json_data
        except (SyntaxError, ValueError) as e:
            logger.error(f"QR code does not contain valid data: {e}")
            logger.debug(f"Decoded data that failed parsing: {data}")
            raise ValueError("QR code does not contain valid data.")
    except Exception as e:
        logger.error(f"Error reading QR code: {e}")
        raise

def run_merge_utility():
    """Runs merge_utility.exe."""
    if not os.path.exists(MERGE_UTILITY_NAME):
        raise FileNotFoundError(f"Merge utility {MERGE_UTILITY_NAME} not found.")
    expected_hash = "16548d4d62e31c43c2cd60980cb7cec70b3173a689513ccf1ee367ace2bf6b14"
    status = verify_file_hash(MERGE_UTILITY_NAME, expected_hash)
    print(f"Running {MERGE_UTILITY_NAME}. Verified: {status}.")
    logger.info(f"Running {MERGE_UTILITY_NAME}.")
    command = [MERGE_UTILITY_NAME]

    with open(LOG_FILE_NAME, "a") as log_file:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # Real-time output reading
        for line in process.stdout:
            sys.stdout.write(line)  # Print to console
            log_file.write(line)  # Write to log file
            log_file.flush()  # Immediate saving to the file

        process.wait()  # Wait for the process to finish

def validate_args(args):
    """Validates command-line arguments."""
    if not args.url and not args.qrcode:
        raise ValueError("You must specify either --url or --qrcode.")
    if args.qrcode:
        qr_path = os.path.join(temp_dir, QRCODE_FILE_NAME)
        if not os.path.exists(qr_path):
            raise FileNotFoundError(f"QR code file {qr_path} not found.")
    logger.info("Arguments validated successfully.")

import hashlib

def verify_file_hash(file_path, expected_hash):
    """Проверяет, совпадает ли хэш файла с ожидаемым."""
    try:
        hash_function = hashlib.sha256()  # Используем SHA-256 для проверки
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):  # Читаем файл частями
                hash_function.update(chunk)
        actual_hash = hash_function.hexdigest()
        if actual_hash != expected_hash:
            raise ValueError(f"Hash mismatch for {file_path}. Expected: {expected_hash}, got: {actual_hash}.")
        logger.info(f"File hash verified successfully for {file_path}.")
        return True
    except Exception as e:
        logger.error(f"Error verifying file hash for {file_path}: {e}")
        raise

if __name__ == "__main__":
    start_time = time.time()
    parser = argparse.ArgumentParser(description="Download file and execute merge utility.")
    parser.add_argument("--url", type=str, help="URL to download the file from.")
    parser.add_argument("--qrcode", action="store_true", help="Use the QR code from temp/qrcode.png.")

    args = parser.parse_args()
    temp_dir = os.path.join(BASE_DIR, TEMP_FOLDER_NAME)
    qr_code_path = os.path.join(temp_dir, QRCODE_FILE_NAME)

    try:
        print("Anime Player Sync App version 0.0.0.1")
        output_file = os.path.join(temp_dir, DOWNLOAD_DB_NAME)
        print(f"This utility downloads a temporary database to the folder: '{output_file}'")
        print(f"After downloading, it automatically launches the Merge Utility '{MERGE_UTILITY_NAME}' to merge the downloaded database into the main database.")
        print(f"Logs: {LOG_FILE}")
        print(f"Base folder: {BASE_DIR}")
        platform_name = configure_platform()
        print(f"Platform: {platform_name}")
        validate_args(args)
        print(f"Arguments: {args.__dict__}")


        if args.url:
            url = args.url
            download_file_with_progress(url, output_file)
        else:
            json_data = decode_qr_code(qr_code_path)
            if json_data:
                url = json_data.get('link')
                if not url:
                    raise ValueError("The QR code does not contain a valid download link.")
                file_size_bytes = json_data.get('size', 0)
                file_size_mb = file_size_bytes / (1024 * 1024)
                print(f"Extracted QR code URL: {url}")
                print(f"File size: {file_size_mb:.2f} MB")
            else:
                raise ValueError("Failed to decode QR code.")
            download_file_with_progress(url, output_file, import_file_size=file_size_bytes)
        print(f"Finished.")
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Execution time: {elapsed_time:.2f} seconds.")

        run_merge_utility()

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"Error: {e}")
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        print(f"Error: {e}")
    except ImportError as e:
        logger.error(f"Platform setup error: {e}")
        print(f"Error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"Error: {e}")
