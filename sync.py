import os
import logging
import subprocess
import sys
import requests
from tqdm import tqdm
from pyzbar.pyzbar import decode
from PIL import Image
import argparse

# Logging configuration
logging.basicConfig(
    filename="merged_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)
logger = logging.getLogger("Sync")

def download_file_with_progress(url, output_path):
    """Download a file from a URL with a progress bar."""
    try:
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            logger.error(f"Error downloading file: {response.status_code} - {response.reason}")
            return

        total_size = int(response.headers.get('content-length', 0))
        with open(output_path, 'wb') as f, tqdm(
                desc="Downloading",
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
        ) as bar:
            for chunk in response.iter_content(1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    bar.update(len(chunk))
        logger.info(f"File successfully downloaded to {output_path}")
    except Exception as e:
        logger.error(f"Error during file download: {e}")


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
    logger.info("Running merge_utility.exe")
    command = ["merge_utility.exe"]

    with open("merged_log.txt", "a") as log_file:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # Real-time output reading
        for line in process.stdout:
            sys.stdout.write(line)  # Print to console
            log_file.write(line)  # Write to log file
            log_file.flush()  # Immediate saving to the file

        process.wait()  # Wait for the process to finish


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download file and execute merge utility.")
    parser.add_argument("--url", type=str, help="URL to download the file from.")
    parser.add_argument("--qrcode", action="store_true", help="Use the QR code from temp/qrcode.png.")

    args = parser.parse_args()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(base_dir, "temp")
    print(f"{base_dir} : {temp_dir}")
    try:
        # Determine the URL
        if args.url:
            url = args.url
        elif args.qrcode:
            qr_path = os.path.join(temp_dir, "qrcode.png")
            print(f"QR Code path: {qr_path}")

            # Check if file exists
            if not os.path.exists(qr_path):
                print("Contents of temp directory:", os.listdir(temp_dir))
                raise FileNotFoundError(f"File {qr_path} not found in {temp_dir}. Ensure the file exists.")

            # Check if the file is valid
            try:
                with open(qr_path, 'rb') as f:
                    Image.open(f).verify()
                print("QR code file is a valid image.")
            except Exception as e:
                print(f"QR code file is invalid or corrupted: {e}")
                raise

            # Decode the QR code
            logger.info(f"Reading QR code from file: {qr_path}")
            url = decode_qr_code(qr_path)
        else:
            raise ValueError("You must specify either --url or --qrcode.")

        # File download
        output_file = os.path.join(temp_dir, "downloaded.db")
        logger.info(f"Starting file download from URL: {url}")

        import asyncio

        download_file_with_progress(url, output_file)

        # Run merge utility
        run_merge_utility()

    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"Error: {e}")
