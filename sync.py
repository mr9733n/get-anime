# sync.py

import os
import ctypes
import logging
import platform
import subprocess
import sys
import requests
from tqdm import tqdm
from pyzbar.pyzbar import decode
from PIL import Image
import argparse

LOG_FILE_NAME = "merged_log.txt"
ORIG_DB_NAME = "anime_player.db"
QRCODE_FILE_NAME = "qrcode.png"
DOWNLOAD_DB_NAME = "downloaded.db"
MERGE_UTILITITY_NAME = "merge_utility.exe"
TEMP_FOLDER_NAME = "temp"
DYLD_NAME = "DYLD_LIBRARY_PATH"
DYLD_LIBRARY_MAC_PATH = "/opt/homebrew/lib"
LIBRARY_MAC_PATH = "/opt/homebrew/lib/libzbar.dylib"
DYLD_LIBRARY_LINUX_PATH = "/usr/lib"
LIBRARY_LINUX_PATH = "/usr/lib/libzbar.so"

# Logging configuration
logging.basicConfig(
    filename=LOG_FILE_NAME,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger("Sync")

def configure_platform():
    """Настраивает окружение в зависимости от операционной системы."""
    platform_name = platform.system()
    paths = {
        "Windows": None,
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

def download_file_with_progress(url, output_path, timeout=600):
    """Download a file from a URL with a progress bar."""
    try:
        logger.info(f"Checking URL availability: {url}")
        response = requests.head(url, timeout=timeout)
        if response.status_code != 200:
            logger.error(f"URL check failed: {response.status_code} - {response.reason}")
            raise ValueError(f"Cannot access URL: {url}")

        logger.info(f"Starting download from {url} to {output_path}.")
        response = requests.get(url, stream=True, timeout=timeout)
        total_size = int(response.headers.get('content-length', 0))

        with open(output_path, 'wb') as f, tqdm(
            desc="Downloading",
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(1024):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))

        filesize = os.path.getsize(output_path)
        logger.info(f"File successfully downloaded to {output_path}[{filesize}].")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during file download: {e}")
        raise


def decode_qr_code(file_path):
    """Reads a QR code from an image and returns the text."""
    try:
        image = Image.open(file_path)
        decoded_objects = decode(image)
        if not decoded_objects:
            raise ValueError("QR code not found or could not be read.")
        return decoded_objects[0].data.decode('utf-8')
    except Exception as e:
        logger.error(f"Error reading QR code: {e}")
        raise


def run_merge_utility():
    """Runs merge_utility.exe."""
    if not os.path.exists(MERGE_UTILITITY_NAME):
        raise FileNotFoundError(f"Merge utility {MERGE_UTILITITY_NAME} not found.")
    logger.info(f"Running {MERGE_UTILITITY_NAME}.")
    command = [MERGE_UTILITITY_NAME]

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download file and execute merge utility.")
    parser.add_argument("--url", type=str, help="URL to download the file from.")
    parser.add_argument("--qrcode", action="store_true", help="Use the QR code from temp/qrcode.png.")

    args = parser.parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(base_dir, TEMP_FOLDER_NAME)

    try:
        print("Anime Player Sync App version 0.0.0.1")
        print(f"Downloads '{ORIG_DB_NAME}' from cloud and save to '{temp_dir}' folder")
        print(f"Then run merge utility {MERGE_UTILITITY_NAME}")
        print(f"Base folder: {base_dir}")
        configure_platform()

        validate_args(args)

        # Определение URL
        url = args.url if args.url else decode_qr_code(os.path.join(temp_dir, QRCODE_FILE_NAME))

        # Скачивание файла
        output_file = os.path.join(temp_dir, DOWNLOAD_DB_NAME)
        download_file_with_progress(url, output_file)

        # Запуск утилиты слияния
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