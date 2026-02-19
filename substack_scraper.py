import argparse
import json
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from time import sleep


import html2text
import markdown
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from tqdm import tqdm
from xml.etree import ElementTree as ET

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import SessionNotCreatedException, TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from urllib.parse import urlparse
from config import EMAIL, PASSWORD

USE_PREMIUM: bool = True  # Set to True if you want to login to Substack and convert paid for posts
BASE_SUBSTACK_URL: str = "https://www.thefitzwilliam.com/"  # Substack you want to convert to markdown
BASE_MD_DIR: str = "substack_md_files"  # Name of the directory we'll save the .md essay files
BASE_HTML_DIR: str = "substack_html_pages"  # Name of the directory we'll save the .html essay files
HTML_TEMPLATE: str = "author_template.html"  # HTML template to use for the author page
JSON_DATA_DIR: str = "data"
NUM_POSTS_TO_SCRAPE: int = 3  # Set to 0 if you want all posts


def extract_main_part(url: str) -> str:
    parts = urlparse(url).netloc.split('.')  # Parse the URL to get the netloc, and split on '.'
    if parts[0] == 'www':
        return parts[1] if len(parts) > 1 else parts[0]
    elif parts[0] == 'substack' and len(parts) > 1:
        # For substack.com URLs, use 'substack' as the name
        return 'substack'
    else:
        return parts[0]  # Return the main part of the domain


def generate_html_file(author_name: str) -> None:
    """
    Generates a HTML file for the given author.
    """
    if not os.path.exists(BASE_HTML_DIR):
        os.makedirs(BASE_HTML_DIR)

    # Read JSON data
    json_path = os.path.join(JSON_DATA_DIR, f'{author_name}.json')
    with open(json_path, 'r', encoding='utf-8') as file:
        essays_data = json.load(file)

    # Convert absolute paths to relative paths for the HTML viewer
    # HTML file is at: BASE_HTML_DIR/{author_name}.html
    html_output_path = os.path.join(BASE_HTML_DIR, f'{author_name}.html')
    html_output_dir = os.path.dirname(os.path.abspath(html_output_path))
    project_root = os.path.abspath('.')
    
    essays_data_with_relative_paths = []
    for essay in essays_data:
        essay_copy = essay.copy()
        # Convert absolute paths to relative paths
        if 'file_link' in essay_copy and essay_copy['file_link']:
            abs_md_path = os.path.abspath(essay_copy['file_link'])
            rel_md_path = os.path.relpath(abs_md_path, html_output_dir)
            essay_copy['file_link'] = rel_md_path.replace('\\', '/')  # Use forward slashes for web
        
        if 'html_link' in essay_copy and essay_copy['html_link']:
            abs_html_path = os.path.abspath(essay_copy['html_link'])
            rel_html_path = os.path.relpath(abs_html_path, html_output_dir)
            essay_copy['html_link'] = rel_html_path.replace('\\', '/')  # Use forward slashes for web
        
        essays_data_with_relative_paths.append(essay_copy)

    # Calculate relative path to assets folder
    assets_path = os.path.join(project_root, 'assets')
    assets_rel_path = os.path.relpath(assets_path, html_output_dir).replace('\\', '/')

    # Convert JSON data to a JSON string for embedding
    embedded_json_data = json.dumps(essays_data_with_relative_paths, ensure_ascii=False, indent=4)

    with open(HTML_TEMPLATE, 'r', encoding='utf-8') as file:
        html_template = file.read()

    # Replace asset paths with calculated relative paths
    # The template uses ../assets/ for both CSS and JS, so replace all occurrences
    html_template = html_template.replace('../assets/', f'{assets_rel_path}/')

    # Insert the JSON string into the script tag in the HTML template
    html_with_data = html_template.replace('<!-- AUTHOR_NAME -->', author_name).replace(
        '<script type="application/json" id="essaysData"></script>',
        f'<script type="application/json" id="essaysData">{embedded_json_data}</script>'
    )
    html_with_author = html_with_data.replace('author_name', author_name)

    # Write the modified HTML to a new file
    with open(html_output_path, 'w', encoding='utf-8') as file:
        file.write(html_with_author)


class BaseSubstackScraper(ABC):
    def __init__(self, base_substack_url: str, md_save_dir: str, html_save_dir: str, skip_url_fetch: bool = False):
        if not base_substack_url.endswith("/"):
            base_substack_url += "/"
        self.base_substack_url: str = base_substack_url

        self.writer_name: str = extract_main_part(base_substack_url)
        md_save_dir: str = f"{md_save_dir}/{self.writer_name}"

        self.md_save_dir: str = md_save_dir
        self.html_save_dir: str = f"{html_save_dir}/{self.writer_name}"

        if not os.path.exists(md_save_dir):
            os.makedirs(md_save_dir)
            print(f"Created md directory {md_save_dir}")
        if not os.path.exists(self.html_save_dir):
            os.makedirs(self.html_save_dir)
            print(f"Created html directory {self.html_save_dir}")

        self.keywords: List[str] = ["about", "archive", "podcast"]
        # Skip URL fetch if explicitly requested OR if base URL looks like a post URL
        if skip_url_fetch or "/home/post/" in base_substack_url or "/p/" in base_substack_url:
            self.post_urls: List[str] = []
        else:
            self.post_urls: List[str] = self.get_all_post_urls()

    def get_all_post_urls(self) -> List[str]:
        """
        Attempts to fetch URLs from sitemap.xml, falling back to feed.xml if necessary.
        """
        urls = self.fetch_urls_from_sitemap()
        if not urls:
            urls = self.fetch_urls_from_feed()
        return self.filter_urls(urls, self.keywords)

    def fetch_urls_from_sitemap(self) -> List[str]:
        """
        Fetches URLs from sitemap.xml.
        """
        sitemap_url = f"{self.base_substack_url}sitemap.xml"
        response = requests.get(sitemap_url)

        if not response.ok:
            print(f'Error fetching sitemap at {sitemap_url}: {response.status_code}')
            return []

        root = ET.fromstring(response.content)
        urls = [element.text for element in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        return urls

    def fetch_urls_from_feed(self) -> List[str]:
        """
        Fetches URLs from feed.xml.
        """
        print('Falling back to feed.xml. This will only contain up to the 22 most recent posts.')
        feed_url = f"{self.base_substack_url}feed.xml"
        response = requests.get(feed_url)

        if not response.ok:
            print(f'Error fetching feed at {feed_url}: {response.status_code}')
            return []

        root = ET.fromstring(response.content)
        urls = []
        for item in root.findall('.//item'):
            link = item.find('link')
            if link is not None and link.text:
                urls.append(link.text)

        return urls

    @staticmethod
    def filter_urls(urls: List[str], keywords: List[str]) -> List[str]:
        """
        This method filters out URLs that contain certain keywords
        """
        return [url for url in urls if all(keyword not in url for keyword in keywords)]

    @staticmethod
    def html_to_md(html_content: str) -> str:
        """
        This method converts HTML to Markdown
        """
        if not isinstance(html_content, str):
            raise ValueError("html_content must be a string")
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        return h.handle(html_content)

    @staticmethod
    def save_to_file(filepath: str, content: str) -> None:
        """
        This method saves content to a file. Can be used to save HTML or Markdown
        """
        if not isinstance(filepath, str):
            raise ValueError("filepath must be a string")

        if not isinstance(content, str):
            raise ValueError("content must be a string")

        if os.path.exists(filepath):
            print(f"File already exists: {filepath}")
            return

        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(content)

    @staticmethod
    def md_to_html(md_content: str) -> str:
        """
        This method converts Markdown to HTML
        """
        return markdown.markdown(md_content, extensions=['extra'])


    def save_to_html_file(self, filepath: str, content: str) -> None:
        """
        This method saves HTML content to a file with a link to an external CSS file.
        """
        if not isinstance(filepath, str):
            raise ValueError("filepath must be a string")

        if not isinstance(content, str):
            raise ValueError("content must be a string")

        # Calculate the relative path from the HTML file to the CSS file
        html_dir = os.path.dirname(filepath)
        css_path = os.path.relpath("./assets/css/essay-styles.css", html_dir)
        css_path = css_path.replace("\\", "/")  # Ensure forward slashes for web paths

        html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Markdown Content</title>
                <link rel="stylesheet" href="{css_path}">
            </head>
            <body>
                <main class="markdown-content">
                {content}
                </main>
            </body>
            </html>
        """

        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(html_content)

    @staticmethod
    def get_filename_from_url(url: str, filetype: str = ".md") -> str:
        """
        Gets the filename from the URL (the ending)
        """
        if not isinstance(url, str):
            raise ValueError("url must be a string")

        if not isinstance(filetype, str):
            raise ValueError("filetype must be a string")

        if not filetype.startswith("."):
            filetype = f".{filetype}"

        return url.split("/")[-1] + filetype

    @staticmethod
    def combine_metadata_and_content(title: str, subtitle: str, date: str, like_count: str, content) -> str:
        """
        Combines the title, subtitle, and content into a single string with Markdown format
        """
        if not isinstance(title, str):
            raise ValueError("title must be a string")

        if not isinstance(content, str):
            raise ValueError("content must be a string")

        metadata = f"# {title}\n\n"
        if subtitle:
            metadata += f"## {subtitle}\n\n"
        metadata += f"**{date}**\n\n"
        metadata += f"**Likes:** {like_count}\n\n"

        return metadata + content

    def extract_post_data(self, soup: BeautifulSoup) -> Tuple[str, str, str, str, str]:
        """
        Converts a Substack post soup to markdown, returning metadata and content.
        Returns (title, subtitle, like_count, date, md_content).
        """
        # Title (sometimes h2 if video present)
        title_element = soup.select_one("h1.post-title, h2")
        title = title_element.text.strip() if title_element else "Untitled"

        # Subtitle
        subtitle_element = soup.select_one("h3.subtitle")
        subtitle = subtitle_element.text.strip() if subtitle_element else ""

        # Date — try CSS selector first
        date = ""
        date_element = soup.select_one("div.pencraft.pc-reset.color-pub-secondary-text-hGQ02T")
        if date_element and date_element.text.strip():
            date = date_element.text.strip()

        # Fallback: JSON-LD metadata
        if not date:
            script_tag = soup.find("script", {"type": "application/ld+json"})
            if script_tag and script_tag.string:
                try:
                    metadata = json.loads(script_tag.string)
                    if "datePublished" in metadata:
                        date_str = metadata["datePublished"]
                        date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        date = date_obj.strftime("%b %d, %Y")
                except (json.JSONDecodeError, ValueError, KeyError):
                    pass

        if not date:
            date = "Date not found"

        # Like count
        like_count_element = soup.select_one("a.post-ufi-button .label")
        like_count = (
            like_count_element.text.strip()
            if like_count_element and like_count_element.text.strip().isdigit()
            else "0"
        )

        # Post content
        content_element = soup.select_one("div.available-content")
        content_html = str(content_element) if content_element else ""
        md = self.html_to_md(content_html)

        # Combine metadata + content
        md_content = self.combine_metadata_and_content(title, subtitle, date, like_count, md)

        return title, subtitle, like_count, date, md_content


    @abstractmethod
    def get_url_soup(self, url: str) -> str:
        raise NotImplementedError

    def save_essays_data_to_json(self, essays_data: list) -> None:
        """
        Saves essays data to a JSON file for a specific author.
        """
        data_dir = os.path.join(JSON_DATA_DIR)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        json_path = os.path.join(data_dir, f'{self.writer_name}.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
            essays_data = existing_data + [data for data in essays_data if data not in existing_data]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(essays_data, f, ensure_ascii=False, indent=4)

    def scrape_single_post(self, url: str) -> None:
        """
        Scrapes a single post URL and saves it as markdown and html files
        """
        try:
            md_filename = self.get_filename_from_url(url, filetype=".md")
            html_filename = self.get_filename_from_url(url, filetype=".html")
            md_filepath = os.path.join(self.md_save_dir, md_filename)
            html_filepath = os.path.join(self.html_save_dir, html_filename)

            if os.path.exists(md_filepath):
                print(f"File already exists: {md_filepath}")
                return

            print(f"Scraping post: {url}")
            soup = self.get_url_soup(url)
            if soup is None:
                print(f"Failed to get soup for {url}")
                return
                
            title, subtitle, like_count, date, md = self.extract_post_data(soup)
            self.save_to_file(md_filepath, md)

            # Convert markdown to HTML and save
            html_content = self.md_to_html(md)
            self.save_to_html_file(html_filepath, html_content)

            essays_data = [{
                "title": title,
                "subtitle": subtitle,
                "like_count": like_count,
                "date": date,
                "file_link": md_filepath,
                "html_link": html_filepath
            }]
            self.save_essays_data_to_json(essays_data=essays_data)
            print(f"Successfully scraped: {title}")
        except Exception as e:
            print(f"Error scraping post {url}: {e}")
            raise

    def scrape_posts(self, num_posts_to_scrape: int = 0) -> None:
        """
        Iterates over all posts and saves them as markdown and html files
        """
        essays_data = []
        count = 0
        total = num_posts_to_scrape if num_posts_to_scrape != 0 else len(self.post_urls)
        for url in tqdm(self.post_urls, total=total):
            try:
                md_filename = self.get_filename_from_url(url, filetype=".md")
                html_filename = self.get_filename_from_url(url, filetype=".html")
                md_filepath = os.path.join(self.md_save_dir, md_filename)
                html_filepath = os.path.join(self.html_save_dir, html_filename)

                if not os.path.exists(md_filepath):
                    soup = self.get_url_soup(url)
                    if soup is None:
                        total += 1
                        continue
                    title, subtitle, like_count, date, md = self.extract_post_data(soup)
                    self.save_to_file(md_filepath, md)

                    # Convert markdown to HTML and save
                    html_content = self.md_to_html(md)
                    self.save_to_html_file(html_filepath, html_content)

                    essays_data.append({
                        "title": title,
                        "subtitle": subtitle,
                        "like_count": like_count,
                        "date": date,
                        "file_link": md_filepath,
                        "html_link": html_filepath
                    })
                else:
                    print(f"File already exists: {md_filepath}")
            except Exception as e:
                print(f"Error scraping post: {e}")
            count += 1
            if num_posts_to_scrape != 0 and count == num_posts_to_scrape:
                break
        self.save_essays_data_to_json(essays_data=essays_data)
        generate_html_file(author_name=self.writer_name)


class SubstackScraper(BaseSubstackScraper):
    def __init__(self, base_substack_url: str, md_save_dir: str, html_save_dir: str, skip_url_fetch: bool = False):
        super().__init__(base_substack_url, md_save_dir, html_save_dir, skip_url_fetch=skip_url_fetch)

    def get_url_soup(self, url: str) -> Optional[BeautifulSoup]:
        """
        Gets soup from URL using requests
        """
        try:
            page = requests.get(url, headers=None)
            soup = BeautifulSoup(page.content, "html.parser")
            if soup.find("h2", class_="paywall-title"):
                print(f"Skipping premium article: {url}")
                return None
            return soup
        except Exception as e:
            raise ValueError(f"Error fetching page: {e}") from e


class PremiumSubstackScraper(BaseSubstackScraper):
    def __init__(
        self,
        base_substack_url: str,
        md_save_dir: str,
        html_save_dir: str,
        headless: bool = False,
        chrome_path: str = '',
        chrome_driver_path: str = '',
        user_agent: str = '',
        skip_url_fetch: bool = False,
        email: str = '',
        password: str = ''
    ) -> None:
        super().__init__(base_substack_url, md_save_dir, html_save_dir, skip_url_fetch=skip_url_fetch)

        # Use credentials passed directly (from GUI) or fall back to config values
        self.login_email = email or EMAIL
        self.login_password = password or PASSWORD

        options = ChromeOptions()
        # Anti-automation flags applied in all modes to reduce bot detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--window-size=1920,1080")

        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            if not user_agent:
                options.add_argument(
                    "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
        if chrome_path:
            options.binary_location = chrome_path
        if user_agent:
            options.add_argument(f"user-agent={user_agent}")
        options.add_argument("--disable-gpu")

        self.driver = None

        # Prefer explicit chromedriver path if provided
        if chrome_driver_path and os.path.exists(chrome_driver_path):
            service = ChromeService(executable_path=chrome_driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
        else:
            # Selenium Manager path (no webdriver_manager)
            try:
                self.driver = webdriver.Chrome(options=options)
            except SessionNotCreatedException as se:
                raise RuntimeError(
                    "Failed to start Chrome session (driver/browser mismatch).\n"
                    "Fix: update Chrome, then upgrade selenium, or pass --chrome-driver-path "
                    "to a matching chromedriver binary."
                ) from se

        # Remove navigator.webdriver property to avoid headless/bot detection
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        self.login()

    def login(self) -> None:
        """
        This method logs into Substack using Selenium
        """
        print("Opening Substack login page...")
        self.driver.get("https://substack.com/sign-in")
        print(f"Current URL: {self.driver.current_url}")
        
        # Wait for page to load
        wait = WebDriverWait(self.driver, 10)
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[@class='login-option substack-login__login-option']")))

        signin_with_password = self.driver.find_element(
            By.XPATH, "//a[@class='login-option substack-login__login-option']"
        )
        signin_with_password.click()
        sleep(2)

        # Wait for email/password fields
        wait.until(EC.presence_of_element_located((By.NAME, "email")))
        
        # Email and password
        email = self.driver.find_element(By.NAME, "email")
        password = self.driver.find_element(By.NAME, "password")
        email.clear()
        email.send_keys(self.login_email)
        password.clear()
        password.send_keys(self.login_password)

        # Brief pause before submit to appear more human-like
        sleep(1)

        # Find the submit button and click it.
        submit = self.driver.find_element(By.XPATH, "//*[@id=\"substack-login\"]/div[2]/div[2]/form/button")
        submit.click()
        
        # Wait for redirect after login (Substack can take several seconds)
        wait_long = WebDriverWait(self.driver, 25)
        try:
            # Success = no longer on sign-in page (redirected to home or elsewhere)
            wait_long.until(lambda d: "sign-in" not in d.current_url or self._has_visible_login_error(d))
            sleep(2)
        except TimeoutException:
            print("Warning: Login redirect timeout - checking current state...")

        # Only treat as failed if we're still on sign-in AND there's a visible error message
        if "sign-in" in self.driver.current_url and self.is_login_failed():
            raise Exception(
                "Login unsuccessful. Check email and password.\n"
                "If using headless, try with Headless unchecked (visible browser) in case of captcha."
            )
        if "sign-in" in self.driver.current_url:
            # Still on sign-in but no error container - might be captcha or slow redirect
            sleep(3)
            if "sign-in" in self.driver.current_url:
                raise Exception(
                    "Still on login page after submit. Try with Headless unchecked (visible browser) "
                    "in case Substack is showing a captcha."
                )
        
        print(f"Login successful! Current URL: {self.driver.current_url}")
        print("Ready to scrape posts...")

    def _has_visible_login_error(self, driver) -> bool:
        """True if the login error message is visible (wrong password etc.)."""
        try:
            el = driver.find_elements(By.ID, 'error-container')
            return len(el) > 0 and el[0].is_displayed()
        except Exception:
            return False

    def is_login_failed(self) -> bool:
        """
        Check for the presence of the 'error-container' to indicate a failed login attempt.
        """
        return self._has_visible_login_error(self.driver)

    def get_url_soup(self, url: str) -> BeautifulSoup:
        """
        Gets soup from URL using logged in selenium driver.
        Ensures we actually landed on the requested page (not redirected back to home/sign-in).
        """
        try:
            print(f"Navigating to: {url}")
            self.driver.get(url)
            sleep(2)
            current = self.driver.current_url
            print(f"Current URL after navigation: {current}")

            # If we were sent back to sign-in, session may have dropped
            if "sign-in" in current:
                raise ValueError(
                    "Browser was redirected to sign-in. Login may have expired or failed. "
                    "Try running again with Headless unchecked."
                )

            # Detect redirect to Substack home/inbox instead of the requested post.
            # This happens when Substack intercepts the navigation (e.g. session not fully
            # established, or the post requires a subscription the account doesn't have).
            current_path = urlparse(current).path.rstrip('/')
            target_path = urlparse(url).path.rstrip('/')
            _home_paths = ('', '/home', '/inbox', '/feed')
            if (current_path in _home_paths or
                    (current_path.startswith('/home') and '/post/' not in current_path)):
                if target_path not in _home_paths:
                    raise ValueError(
                        f"Redirected to {current} instead of the requested post.\n"
                        "This usually means the post requires a subscription the account "
                        "doesn't have, or the session hadn't fully established. Try again."
                    )

            # Wait for page to load - check for specific Substack post elements.
            # Intentionally excludes generic tags (e.g. <article>) that also appear on
            # the home/inbox page and would cause a false positive.
            wait = WebDriverWait(self.driver, 15)
            try:
                wait.until(lambda driver: (
                    len(driver.find_elements(By.CLASS_NAME, "post-title")) > 0 or
                    len(driver.find_elements(By.CLASS_NAME, "paywall-title")) > 0 or
                    len(driver.find_elements(By.CLASS_NAME, "available-content")) > 0
                ))
                print("Page loaded successfully")
            except TimeoutException:
                print(f"Warning: Timeout waiting for post content at {url}")
                print(f"Current page title: {self.driver.title}")
                # If we're on a generic Substack home/inbox, we didn't get the post
                if "/home" in current and "/post/" not in current and "p-" not in current:
                    raise ValueError(
                        "Landed on Substack home instead of the post. "
                        "Use the exact post URL (e.g. from your browser address bar)."
                    )
            
            sleep(2)
            return BeautifulSoup(self.driver.page_source, "html.parser")
        except ValueError:
            raise
        except Exception as e:
            print(f"Error navigating to {url}: {e}")
            print(f"Current URL: {self.driver.current_url if self.driver else 'No driver'}")
            raise ValueError(f"Error fetching page: {e}") from e


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape a Substack site.")
    parser.add_argument(
        "-u", "--url", type=str, help="The base URL of the Substack site to scrape."
    )
    parser.add_argument(
        "-d", "--directory", type=str, help="The directory to save scraped posts."
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=0,
        help="The number of posts to scrape. If 0 or not provided, all posts will be scraped.",
    )
    parser.add_argument(
        "-p",
        "--premium",
        action="store_true",
        help="Include -p in command to use the Premium Substack Scraper with selenium.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Include -h in command to run browser in headless mode when using the Premium Substack "
        "Scraper.",
    )
    parser.add_argument(
        "--chrome-path",
        type=str,
        default="",
        help='Optional: The path to the Chrome browser executable (i.e. "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").',
    )
    parser.add_argument(
        "--chrome-driver-path",
        type=str,
        default="",
        help='Optional: The path to the Chrome WebDriver executable (i.e. "/opt/homebrew/bin/chromedriver" or "/usr/local/bin/chromedriver").',
    )
    parser.add_argument(
        "--user-agent",
        type=str,
        default="",
        help="Optional: Specify a custom user agent for selenium browser automation. Useful for "
        "passing captcha in headless mode",
    )
    parser.add_argument(
        "--html-directory",
        type=str,
        help="The directory to save scraped posts as HTML files.",
    )
    parser.add_argument(
        "--single-post",
        type=str,
        help="Scrape a single post URL instead of all posts from a base URL. Use with --premium flag for paid posts.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.directory is None:
        args.directory = BASE_MD_DIR

    if args.html_directory is None:
        args.html_directory = BASE_HTML_DIR

    # Handle single post scraping
    if args.single_post:
        # For single post, we need a base URL to determine save directory
        # Extract base URL from the post URL or use a default
        post_url = args.single_post.strip()
        
        # Parse the URL to extract components
        parsed = urlparse(post_url)
        
        # Determine base URL based on URL structure
        if "/home/post/" in post_url or parsed.netloc == "substack.com":
            # This is a Substack internal URL (e.g., https://substack.com/home/post/p-182828153)
            # We'll use substack.com as base and create a generic directory
            base_url = "https://substack.com/"
        else:
            # Extract base URL from post URL (e.g., https://author.substack.com/p/post-name)
            base_url = f"{parsed.scheme}://{parsed.netloc}/"
        
        print(f"Scraping single post: {post_url}")
        print(f"Using base URL: {base_url}")
        
        if args.premium:
            scraper = PremiumSubstackScraper(
                base_url,
                headless=args.headless,
                md_save_dir=args.directory,
                html_save_dir=args.html_directory,
                chrome_path=args.chrome_path,
                chrome_driver_path=args.chrome_driver_path,
                user_agent=args.user_agent,
                skip_url_fetch=True  # Skip fetching all URLs since we're only scraping one
            )
            scraper.scrape_single_post(post_url)
        else:
            scraper = SubstackScraper(
                base_url,
                md_save_dir=args.directory,
                html_save_dir=args.html_directory,
                skip_url_fetch=True  # Skip fetching all URLs since we're only scraping one
            )
            scraper.scrape_single_post(post_url)
        return

    if args.url:
        # Check if URL looks like a post URL instead of a base URL
        if "/home/post/" in args.url or "/p/" in args.url:
            print("Warning: The URL provided looks like a post URL, not a base URL.")
            print("Did you mean to use --single-post instead of --url?")
            print(f"Attempting to scrape as single post: {args.url}")
            
            parsed = urlparse(args.url)
            if "/home/post/" in args.url or parsed.netloc == "substack.com":
                base_url = "https://substack.com/"
            else:
                base_url = f"{parsed.scheme}://{parsed.netloc}/"
            
            if args.premium:
                scraper = PremiumSubstackScraper(
                    base_url,
                    headless=args.headless,
                    md_save_dir=args.directory,
                    html_save_dir=args.html_directory,
                    chrome_path=args.chrome_path,
                    chrome_driver_path=args.chrome_driver_path,
                    user_agent=args.user_agent,
                    skip_url_fetch=True
                )
                scraper.scrape_single_post(args.url)
            else:
                scraper = SubstackScraper(
                    base_url,
                    md_save_dir=args.directory,
                    html_save_dir=args.html_directory,
                    skip_url_fetch=True
                )
                scraper.scrape_single_post(args.url)
        else:
            if args.premium:
                scraper = PremiumSubstackScraper(
                    args.url,
                    headless=args.headless,
                    md_save_dir=args.directory,
                    html_save_dir=args.html_directory,
                    chrome_path=args.chrome_path,
                    chrome_driver_path=args.chrome_driver_path,
                    user_agent=args.user_agent
                )
            else:
                scraper = SubstackScraper(
                    args.url,
                    md_save_dir=args.directory,
                    html_save_dir=args.html_directory
                )
            scraper.scrape_posts(args.number)

    else:  # Use the hardcoded values at the top of the file
        if USE_PREMIUM:
            scraper = PremiumSubstackScraper(
                base_substack_url=BASE_SUBSTACK_URL,
                md_save_dir=args.directory,
                html_save_dir=args.html_directory,
                chrome_path=args.chrome_path,
                chrome_driver_path=args.chrome_driver_path,
                user_agent=args.user_agent
            )
        else:
            scraper = SubstackScraper(
                base_substack_url=BASE_SUBSTACK_URL,
                md_save_dir=args.directory,
                html_save_dir=args.html_directory
            )
        scraper.scrape_posts(num_posts_to_scrape=NUM_POSTS_TO_SCRAPE)


if __name__ == "__main__":
    main()
