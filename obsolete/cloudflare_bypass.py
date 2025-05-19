# cloudflare_bypass.py - Simple Working Version
import os
import json
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class CloudflareBypass:
    def __init__(self, storage_dir='cf_state'):
        self.storage_dir = storage_dir
        self.cookies_file = Path(storage_dir) / 'cookies.json'
        os.makedirs(storage_dir, exist_ok=True)
        self.cookies = self._load_cookies()

    def _load_cookies(self):
        """Load cookies from file if it exists."""
        if self.cookies_file.exists():
            try:
                with open(self.cookies_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading cookies: {e}")
        return []

    def _save_cookies(self, cookies):
        """Save cookies to file."""
        try:
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies, f)
            return True
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")
            return False

    def get_cookies_for_requests(self):
        """Convert cookies to format suitable for requests library."""
        cookies_dict = {}
        for cookie in self.cookies:
            if 'name' in cookie and 'value' in cookie:
                cookies_dict[cookie['name']] = cookie['value']
        return cookies_dict

    def bypass_cloudflare(self, url, manual_interaction=True):
        """
        Simple Cloudflare bypass.
        """
        logger.info(f"Starting Cloudflare bypass for URL: {url}")

        # Extract main domain - we'll use this instead of the image URL
        main_domain = "https://anilibria.tv"

        try:
            with sync_playwright() as p:
                # Launch the browser
                browser = p.chromium.launch(headless=False)

                # Create context
                context = browser.new_context()

                # Create page
                page = context.new_page()

                # Navigate to main site first
                logger.info(f"Navigating to main site: {main_domain}")
                page.goto(main_domain)

                # Show instructions
                print("\n==== CLOUDFLARE BYPASS ====")
                print("1. Solve any CAPTCHA or challenge that appears")
                print("2. Make sure you can see the main website content")
                print("3. When you can access the site normally, return here")
                input("\nPress Enter after completing the challenge...\n")

                # Wait a moment
                time.sleep(2)

                # Get cookies
                cookies = context.cookies()
                logger.info(f"Collected {len(cookies)} cookies")

                # Save cookies
                self._save_cookies(cookies)
                self.cookies = cookies

                # Close browser
                browser.close()

                # Return success if we got any cookies
                return len(cookies) > 0

        except Exception as e:
            logger.error(f"Error during Cloudflare bypass: {e}")
            return False

    def get_cookies(self, url=None, force_refresh=False):
        """Get cookies, forcing a refresh if requested."""
        if force_refresh and url:
            self.bypass_cloudflare(url)
        return self.get_cookies_for_requests()