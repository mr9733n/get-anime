# api_client.py
import json
import os
import time
import requests
import logging

class APIClient:
    def __init__(self, base_url, api_version, logger=None):
        self.base_url = base_url
        self.api_version = api_version
        self.logger = logger or logging.getLogger(__name__)

    def send_request(self, endpoint, params=None):
        url = f"https://api.{self.base_url}/{self.api_version}/{endpoint}"
        try:
            start_time = time.time()
            response = requests.get(url, params=params)
            response.raise_for_status()
            end_time = time.time()
            data = response.json()
            utils_folder = 'utils'
            if not os.path.exists(utils_folder):
                os.makedirs(utils_folder)
                self.logger.debug(f"Created 'utils' folder.")
            utils_json = os.path.join(utils_folder, 'response.json')

            with open(utils_json, 'w', encoding='utf-8') as file:
                file.write(response.text)
            num_items = len(response.text) if response.text else 0
            self.logger.debug(f"Successful API call to URL: {url}, "
                            f"Time taken: {end_time - start_time:.2f} seconds, "
                            f"Response size: {num_items} bytes.")
            return data
        except requests.exceptions.HTTPError as http_err:
            error_message = f"HTTP error occurred: {http_err} - URL: {url} - Params: {params}"
            self.logger.error(error_message)
            return {'error': error_message}
        except requests.exceptions.RequestException as req_err:
            error_message = f"Request exception: {req_err} - URL: {url} - Params: {params}"
            self.logger.error(error_message)
            return {'error': error_message}
        except Exception as e:
            error_message = f"An unexpected error occurred: {e} - URL: {url} - Params: {params}"
            self.logger.error(error_message)
            return {'error': error_message}

    def get_schedule(self, day):
        endpoint = "title/schedule"
        params = {'days': day}
        return self.send_request(endpoint, params)

    def search_by_title(self, search_text):
        endpoint = "title/search"
        params = {'search': search_text}
        return self.send_request(endpoint, params)

    def get_random_title(self):
        endpoint = "title/random"
        data = self.send_request(endpoint)
        if 'error' in data:
            return data
        wrapped_data = {
            "list": [data],
            "pagination": {
                "pages": 1,
                "current_page": 1,
                "items_per_page": 1,
                "total_items": 1
            }
        }
        return wrapped_data
