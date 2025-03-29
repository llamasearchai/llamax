#!/usr/bin/env python3
"""
Ultimate Llama PyPI Scraper v2.1

A comprehensive, elegant tool for scraping and organizing Python package information.
Enhanced with anti-detection mechanisms (using cloudscraper, optional pystealth, and browser automation),
beautiful visualizations, and a stylish Llama UI.
Supports both individual package names and PyPI user profile URLs.
"""

import os
import sys
import re
import json
import time
import shutil
import argparse
import logging
import tempfile
import zipfile
import tarfile
import random
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, urljoin
from typing import Dict, List, Any, Optional

# Advanced web scraping libraries
import requests
import cloudscraper
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Data processing and visualization
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from tabulate import tabulate

# CLI enhancements
from tqdm import tqdm
from colorama import init, Fore, Style
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn, SpinnerColumn
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel
from rich.box import ROUNDED
from yaspin import yaspin
from yaspin.spinners import Spinners
from pyfiglet import Figlet
from termcolor import colored
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import TerminalFormatter
from alive_progress import alive_bar
from blessed import Terminal

# Documentation generation
from mdutils.mdutils import MdUtils
from packaging import version as packaging_version

# GitHub integration (optional)
try:
    from github import Github, GithubException
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

# UI components (optional)
try:
    from textual.app import App
    from textual.widgets import Header, Footer
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False

# Advanced browser automation (optional)
try:
    import undetected_chromedriver as uc
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Optional stealth enhancements
try:
    import pystealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

# Initialize colorama for cross-platform colored terminal output
init()

# Terminal for UI enhancements
term = Terminal()

# Create rich console for pretty output
console = Console()

# Configure custom logger
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("llama_pypi_scraper")

# ASCII art for Llama logo
LLAMA_LOGO = r"""
                 ⟋|、
                (˚ˎ 。7  
                |、˜〵    Ultimate Llama PyPI Scraper v2.1
                じしˍ,)ノ  Elegant package analysis and organization
"""

# Global settings
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/llama_pypi_data")
TEMP_DIR = os.path.join(tempfile.gettempdir(), "llama_pypi_temp")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_WORKERS = 5
REQUEST_TIMEOUT = 30
REQUEST_RETRIES = 3
REQUEST_RETRY_DELAY = 1

# Color schemes for matplotlib
LLAMA_CMAP = {
    'purple': '#A982DF',
    'pink': '#F4B3ED',
    'blue': '#6DA9E4',
    'light_blue': '#8FC4F5',
    'green': '#9BE8A8',
    'yellow': '#F4EA9C',
    'red': '#F47983',
    'orange': '#F4C983',
    'gray': '#D0D0D0',
    'dark_gray': '#808080',
}

class UserAgentRotator:
    """Class to manage and rotate user agents to avoid detection."""
    
    def __init__(self):
        self.ua = UserAgent(browsers=['chrome', 'firefox', 'safari', 'edge'])
        self.custom_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
        ]
    
    def get_random_user_agent(self):
        """Return a random user agent string."""
        if random.random() < 0.7:
            try:
                return self.ua.random
            except Exception:
                return random.choice(self.custom_agents)
        else:
            return random.choice(self.custom_agents)

class AntiDetectionRequestSession:
    """Session class with anti-detection measures."""
    
    def __init__(self, use_cloudscraper=True):
        self.agent_rotator = UserAgentRotator()
        if use_cloudscraper:
            self.session = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'desktop': True
                }
            )
        else:
            self.session = requests.Session()
            retry_strategy = Retry(
                total=REQUEST_RETRIES,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        self.update_headers()
    
    def update_headers(self):
        """Update request headers with a random user agent and stealth measures."""
        user_agent = self.agent_rotator.get_random_user_agent()
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        })
        if STEALTH_AVAILABLE:
            try:
                pystealth.apply_stealth(self.session)
            except Exception as e:
                logger.debug(f"pystealth application failed: {e}")
    
    def get(self, url, **kwargs):
        self.update_headers()
        time.sleep(random.uniform(0.5, 2.0))
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        return self.session.get(url, **kwargs)
    
    def post(self, url, **kwargs):
        self.update_headers()
        time.sleep(random.uniform(0.5, 2.0))
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        return self.session.post(url, **kwargs)

class BrowserAutomation:
    """Browser automation with undetected-chromedriver."""
    
    def __init__(self):
        self.driver = None
    
    def initialize(self):
        if not SELENIUM_AVAILABLE:
            logger.warning("Selenium/undetected-chromedriver not available. Browser automation disabled.")
            return False
        try:
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            self.driver = uc.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False
    
    def fetch_with_browser(self, url):
        if not self.driver:
            if not self.initialize():
                return None
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Error fetching {url} with browser: {e}")
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

class PackageInfo:
    """Stores and processes package information."""
    
    def __init__(self, name: str):
        self.name = name
        self.version = "N/A"
        self.release_date = None
        self.description = ""
        self.author = ""
        self.author_email = ""
        self.license = ""
        self.dependencies = []
        self.dev_dependencies = []
        self.project_urls = {}
        self.github_url = None
        self.github_stats = {}
        self.all_versions = []
        self.classifiers = []
        self.downloads = {}
        self.package_files = []
        self.readme_content = ""
        self.source_analysis = {}
        self.metadata = {}
        self.pypi_json = {}
        self.error = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "release_date": self.release_date,
            "description": self.description,
            "author": self.author,
            "author_email": self.author_email,
            "license": self.license,
            "dependencies": self.dependencies,
            "dev_dependencies": self.dev_dependencies,
            "project_urls": self.project_urls,
            "github_url": self.github_url,
            "github_stats": self.github_stats,
            "all_versions": self.all_versions,
            "classifiers": self.classifiers,
            "downloads": self.downloads,
            "package_files": self.package_files,
            "metadata": self.metadata,
            "source_analysis": self.source_analysis
        }
    
    def from_pypi_json(self, data: Dict[str, Any]) -> None:
        self.pypi_json = data
        info = data.get("info", {})
        self.version = info.get("version", "N/A")
        self.description = info.get("summary", "No description available")
        self.author = info.get("author", "")
        self.author_email = info.get("author_email", "")
        self.license = info.get("license", "")
        self.project_urls = info.get("project_urls", {}) or {}
        self.classifiers = info.get("classifiers", [])
        if self.project_urls:
            for key in list(self.project_urls.keys()):
                if self.project_urls[key] is None:
                    del self.project_urls[key]
        requires_dist = info.get("requires_dist", [])
        if requires_dist:
            self.dependencies = self._parse_requirements(requires_dist)
        else:
            self.dependencies = ["No dependencies listed"]
        self.github_url = self._extract_github_url()
        self.all_versions = self._extract_all_versions(data)
        if self.version != "N/A":
            self.release_date = self._extract_release_date(data, self.version)
    
    def _parse_requirements(self, requires_dist: List[str]) -> List[str]:
        regular_deps = []
        dev_deps = []
        for req in requires_dist:
            if not req:
                continue
            if ";" in req:
                req_part, marker = req.split(";", 1)
                if any(dev_marker in marker.lower() for dev_marker in ["extra == 'dev'", "extra == 'test'", "extra == 'docs'"]):
                    dev_deps.append(req.strip())
                else:
                    regular_deps.append(req.strip())
            else:
                regular_deps.append(req.strip())
        self.dev_dependencies = dev_deps
        return regular_deps if regular_deps else ["No dependencies listed"]
    
    def _extract_github_url(self) -> Optional[str]:
        github_keys = ["GitHub", "Source", "Source Code", "Repository", "Code", "Homepage"]
        for key in github_keys:
            if key in self.project_urls and "github.com" in self.project_urls[key].lower():
                url = self.project_urls[key]
                url = url.split("?")[0].split("#")[0]
                return url
        for url in self.project_urls.values():
            if url and "github.com" in url.lower():
                url = url.split("?")[0].split("#")[0]
                return url
        return None
    
    def _extract_all_versions(self, data: Dict[str, Any]) -> List[str]:
        versions = list(data.get("releases", {}).keys())
        try:
            versions.sort(key=lambda x: packaging_version.parse(x), reverse=True)
        except Exception:
            versions.sort(key=lambda x: [int(p) if p.isdigit() else float('inf') for p in re.split(r'(\d+)', x)], reverse=True)
        return versions
    
    def _extract_release_date(self, data: Dict[str, Any], version: str) -> Optional[str]:
        releases = data.get("releases", {}).get(version, [])
        for release in releases:
            if "upload_time_iso_8601" in release:
                try:
                    return datetime.fromisoformat(release["upload_time_iso_8601"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
                except ValueError:
                    pass
        return None

class LlamaPyPIScraper:
    """Main class for scraping PyPI package information with anti-detection measures."""
    
    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR, temp_dir: str = TEMP_DIR, 
                 github_token: str = None, use_cloudscraper: bool = True,
                 use_browser_automation: bool = False):
        self.output_dir = output_dir
        self.temp_dir = temp_dir
        self.github_token = github_token or GITHUB_TOKEN
        self.use_cloudscraper = use_cloudscraper
        self.use_browser_automation = use_browser_automation
        self.session = AntiDetectionRequestSession(use_cloudscraper)
        self.browser = BrowserAutomation() if use_browser_automation else None
        self.github_client = self._init_github_client()
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)
    
    def _init_github_client(self) -> Optional[Any]:
        if not GITHUB_AVAILABLE or not self.github_token:
            return None
        try:
            return Github(self.github_token)
        except Exception as e:
            logger.warning(f"Failed to initialize GitHub client: {e}")
            return None
    
    def fetch_with_retry(self, url: str, method: str = "get", use_browser: bool = False, **kwargs) -> Optional[requests.Response]:
        if use_browser and self.browser:
            page_source = self.browser.fetch_with_browser(url)
            if page_source:
                mock_response = type('MockResponse', (), {
                    'text': page_source,
                    'status_code': 200,
                    'raise_for_status': lambda: None,
                    'json': lambda: json.loads(page_source) if page_source.strip().startswith('{') else None
                })
                return mock_response
        for attempt in range(REQUEST_RETRIES):
            try:
                if method.lower() == "get":
                    response = self.session.get(url, **kwargs)
                elif method.lower() == "post":
                    response = self.session.post(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt < REQUEST_RETRIES - 1:
                    logger.debug(f"Retry {attempt+1}/{REQUEST_RETRIES} for {url}: {e}")
                    time.sleep(REQUEST_RETRY_DELAY * (attempt + 1))
                    self.session.update_headers()
                else:
                    logger.error(f"Failed to fetch {url}: {e}")
                    return None
    
    def fetch_package_info(self, package_name: str) -> PackageInfo:
        package = PackageInfo(package_name)
        try:
            with yaspin(Spinners.bouncingBar, text=f"Fetching data for {package_name}...") as spinner:
                url = f"https://pypi.org/pypi/{package_name}/json"
                response = self.fetch_with_retry(url)
                if not response:
                    spinner.fail("💥")
                    package.error = f"Failed to fetch package information for {package_name}"
                    return package
                data = response.json()
                package.from_pypi_json(data)
                spinner.text = f"Fetching license info for {package_name}..."
                package.license = self.scrape_license(package_name, package.license)
                spinner.text = f"Fetching download stats for {package_name}..."
                package.downloads = self.fetch_download_stats(package_name)
                spinner.text = f"Fetching README for {package_name}..."
                package.readme_content = self.fetch_readme(package_name, package.version)
                if package.github_url:
                    spinner.text = f"Fetching GitHub stats for {package_name}..."
                    package.github_stats = self.fetch_github_stats(package.github_url)
                spinner.ok("✅")
            return package
        except Exception as e:
            package.error = f"Error: {str(e)}"
            logger.error(f"Error fetching {package_name}: {e}", exc_info=True)
            return package
    
    def scrape_license(self, package_name: str, license_info: str) -> str:
        if license_info and license_info != "UNKNOWN":
            return license_info
        try:
            url = f"https://pypi.org/project/{package_name}/"
            response = self.fetch_with_retry(url, use_browser=True)
            if not response:
                return "License not specified"
            soup = BeautifulSoup(response.text, "html.parser")
            license_tag = soup.find("span", string="License:")
            if license_tag and license_tag.find_next("p"):
                license_text = license_tag.find_next("p").text.strip()
                if license_text and license_text != "UNKNOWN":
                    return license_text
            classifiers = soup.select("a.sidebar-section__classifier")
            for classifier in classifiers:
                if "License ::" in classifier.text:
                    license_text = classifier.text.split("License :: ")[-1].strip()
                    if license_text and "UNKNOWN" not in license_text:
                        return license_text
            return "License not specified"
        except Exception as e:
            logger.debug(f"Error scraping license for {package_name}: {e}")
            return "License not specified"
    
    def fetch_download_stats(self, package_name: str) -> Dict[str, Any]:
        try:
            url = f"https://pypistats.org/api/packages/{package_name}/recent"
            response = self.fetch_with_retry(url)
            if not response:
                return {}
            data = response.json()
            return data.get("data", {})
        except Exception as e:
            logger.debug(f"Error fetching download stats for {package_name}: {e}")
            return {}
    
    def fetch_readme(self, package_name: str, version: str) -> str:
        try:
            url = f"https://pypi.org/project/{package_name}/{version}/"
            response = self.fetch_with_retry(url, use_browser=True)
            if not response:
                return "No README content available"
            soup = BeautifulSoup(response.text, "html.parser")
            description_div = soup.find("div", {"class": "project-description"})
            if description_div:
                return description_div.text
            return "No README content available"
        except Exception as e:
            logger.debug(f"Error fetching README for {package_name}: {e}")
            return "No README content available"
    
    def fetch_github_stats(self, github_url: str) -> Dict[str, Any]:
        if not github_url:
            return {}
        if self.github_client:
            try:
                path_parts = urlparse(github_url).path.strip("/").split("/")
                if len(path_parts) < 2:
                    return {}
                owner, repo = path_parts[:2]
                try:
                    repository = self.github_client.get_repo(f"{owner}/{repo}")
                    return {
                        "stars": repository.stargazers_count,
                        "forks": repository.forks_count,
                        "open_issues": repository.open_issues_count,
                        "watchers": repository.subscribers_count,
                        "last_updated": repository.updated_at.strftime("%Y-%m-%d") if repository.updated_at else None,
                        "created_at": repository.created_at.strftime("%Y-%m-%d") if repository.created_at else None,
                        "default_branch": repository.default_branch,
                        "language": repository.language,
                        "license": repository.get_license().license.name if repository.get_license() else None
                    }
                except Exception as e:
                    logger.debug(f"GitHub API error for {github_url}: {e}")
            except Exception:
                pass
        try:
            response = self.fetch_with_retry(github_url, use_browser=True)
            if not response:
                return {}
            soup = BeautifulSoup(response.text, "html.parser")
            stats = {}
            stars_element = soup.select_one("a.social-count[href$='/stargazers']")
            if stars_element:
                stars_text = stars_element.text.strip()
                stats["stars"] = int(stars_text.replace(",", ""))
            forks_element = soup.select_one("a.social-count[href$='/network/members']")
            if forks_element:
                forks_text = forks_element.text.strip()
                stats["forks"] = int(forks_text.replace(",", ""))
            language_element = soup.select_one("span.color-fg-default.text-bold.mr-1")
            if language_element:
                stats["language"] = language_element.text.strip()
            return stats
        except Exception as e:
            logger.debug(f"Error scraping GitHub stats for {github_url}: {e}")
            return {}
    
    def download_package_source(self, package_name: str, version: str) -> Optional[str]:
        try:
            with yaspin(Spinners.bouncingBar, text=f"Downloading source for {package_name} {version}...") as spinner:
                url = f"https://pypi.org/pypi/{package_name}/{version}/json"
                response = self.fetch_with_retry(url)
                if not response:
                    spinner.fail("💥")
                    return None
                data = response.json()
                urls = data.get("urls", [])
                source_url = None
                for url_data in urls:
                    if url_data.get("packagetype") == "sdist":
                        source_url = url_data.get("url")
                        break
                if not source_url:
                    spinner.fail("💥")
                    return None
                package_dir = os.path.join(self.temp_dir, f"{package_name}-{version}")
                os.makedirs(package_dir, exist_ok=True)
                download_path = os.path.join(package_dir, os.path.basename(source_url))
                response = self.fetch_with_retry(source_url, stream=True)
                if not response:
                    spinner.fail("💥")
                    return None
                with open(download_path, "wb") as f:
                    shutil.copyfileobj(response.raw, f)
                extract_dir = os.path.join(package_dir, "source")
                os.makedirs(extract_dir, exist_ok=True)
                if download_path.endswith(".tar.gz") or download_path.endswith(".tgz"):
                    with tarfile.open(download_path, "r:gz") as tar:
                        prefixes = set()
                        for member in tar.getmembers():
                            parts = member.name.split("/", 1)
                            if len(parts) > 1:
                                prefixes.add(parts[0])
                        common_prefix = list(prefixes)[0] if len(prefixes) == 1 else ""
                        tar.extractall(path=extract_dir)
                        spinner.ok("✅")
                        return os.path.join(extract_dir, common_prefix) if common_prefix else extract_dir
                elif download_path.endswith(".zip"):
                    with zipfile.ZipFile(download_path, "r") as zip_ref:
                        prefixes = set()
                        for member in zip_ref.namelist():
                            parts = member.split("/", 1)
                            if len(parts) > 1:
                                prefixes.add(parts[0])
                        common_prefix = list(prefixes)[0] if len(prefixes) == 1 else ""
                        zip_ref.extractall(path=extract_dir)
                        spinner.ok("✅")
                        return os.path.join(extract_dir, common_prefix) if common_prefix else extract_dir
                spinner.ok("✅")
                return extract_dir
        except Exception as e:
            logger.error(f"Error downloading source for {package_name}: {e}")
            return None
    
    def analyze_package_source(self, package_name: str, version: str) -> Dict[str, Any]:
        source_dir = self.download_package_source(package_name, version)
        if not source_dir:
            return {"error": "Failed to download package source"}
        try:
            with yaspin(Spinners.bouncingBar, text=f"Analyzing source code for {package_name}...") as spinner:
                analysis = {
                    "file_count": 0,
                    "file_types": {},
                    "total_lines": 0,
                    "code_lines": 0,
                    "comment_lines": 0,
                    "blank_lines": 0,
                    "package_structure": [],
                    "files": []
                }
                for root, dirs, files in os.walk(source_dir):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__", "tests", "test", "docs"]]
                    rel_path = os.path.relpath(root, source_dir)
                    if rel_path == ".":
                        rel_path = ""
                    for file in files:
                        if file.startswith(".") or file in ["setup.py", "setup.cfg", "pyproject.toml", "README.md", "LICENSE"]:
                            continue
                        file_path = os.path.join(root, file)
                        rel_file_path = os.path.join(rel_path, file) if rel_path else file
                        ext = os.path.splitext(file)[1].lower() or "no_extension"
                        analysis["file_types"].setdefault(ext, 0)
                        analysis["file_types"][ext] += 1
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                lines = f.readlines()
                            total_lines = len(lines)
                            code_lines = sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))
                            comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
                            blank_lines = total_lines - code_lines - comment_lines
                            analysis["total_lines"] += total_lines
                            analysis["code_lines"] += code_lines
                            analysis["comment_lines"] += comment_lines
                            analysis["blank_lines"] += blank_lines
                            analysis["files"].append({
                                "path": rel_file_path,
                                "extension": ext,
                                "total_lines": total_lines,
                                "code_lines": code_lines,
                                "comment_lines": comment_lines,
                                "blank_lines": blank_lines
                            })
                        except Exception as e:
                            logger.debug(f"Error analyzing file {file_path}: {e}")
                analysis["file_count"] = len(analysis["files"])
                analysis["package_structure"] = self._generate_package_structure(source_dir)
                spinner.ok("✅")
                return analysis
        except Exception as e:
            logger.error(f"Error analyzing source for {package_name}: {e}")
            return {"error": f"Error analyzing package source: {str(e)}"}
        finally:
            try:
                shutil.rmtree(os.path.dirname(source_dir), ignore_errors=True)
            except Exception:
                pass
    
    def _generate_package_structure(self, source_dir: str) -> List[Dict[str, Any]]:
        structure = []
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["__pycache__"]]
            rel_path = os.path.relpath(root, source_dir)
            if rel_path == ".":
                node = {"name": os.path.basename(source_dir), "path": "", "type": "directory", "children": []}
                for file in sorted(files):
                    if not file.startswith("."):
                        node["children"].append({
                            "name": file,
                            "path": file,
                            "type": "file",
                            "extension": os.path.splitext(file)[1]
                        })
                for dir_name in sorted(dirs):
                    node["children"].append({
                        "name": dir_name,
                        "path": dir_name,
                        "type": "directory",
                        "children": []
                    })
                structure.append(node)
                break
        return structure
    
    def generate_report(self, package: PackageInfo, output_format: str = "text") -> str:
        if output_format == "json":
            return self._generate_json_report(package)
        elif output_format == "markdown":
            return self._generate_markdown_report(package)
        elif output_format == "html":
            return self._generate_html_report(package)
        else:
            return self._generate_text_report(package)
    
    def _generate_text_report(self, package: PackageInfo) -> str:
        if package.error:
            return f"Error: {package.error}"
        from pyfiglet import Figlet
        report = []
        figlet = Figlet(font='slant')
        report.append(Fore.MAGENTA + figlet.renderText(package.name) + Fore.RESET)
        report.append(Fore.MAGENTA + "=" * 80 + Fore.RESET)
        report.append(Fore.CYAN + Style.BRIGHT + f"Package: {package.name} ({package.version})" + Style.RESET_ALL)
        report.append(Fore.MAGENTA + "=" * 80 + Fore.RESET)
        report.append("\n" + Fore.YELLOW + Style.BRIGHT + "📦 Basic Information" + Style.RESET_ALL)
        report.append(Fore.WHITE + f"Description: {package.description}" + Fore.RESET)
        report.append(Fore.WHITE + f"Author: {package.author}" + Fore.RESET)
        report.append(Fore.WHITE + f"Author Email: {package.author_email}" + Fore.RESET)
        report.append(Fore.WHITE + f"License: {package.license}" + Fore.RESET)
        report.append(Fore.WHITE + f"Release Date: {package.release_date or 'Unknown'}" + Fore.RESET)
        if package.project_urls:
            report.append("\n" + Fore.YELLOW + Style.BRIGHT + "🔗 Project URLs" + Style.RESET_ALL)
            for key, url in package.project_urls.items():
                report.append(Fore.WHITE + f"{key}: {url}" + Fore.RESET)
        if package.github_url:
            report.append("\n" + Fore.YELLOW + Style.BRIGHT + "🐙 GitHub Information" + Style.RESET_ALL)
            report.append(Fore.WHITE + f"Repository: {package.github_url}" + Fore.RESET)
            if package.github_stats:
                for key, value in package.github_stats.items():
                    if value is not None:
                        key_formatted = key.replace("_", " ").title()
                        report.append(Fore.WHITE + f"{key_formatted}: {value}" + Fore.RESET)
        report.append("\n" + Fore.YELLOW + Style.BRIGHT + "🔄 Dependencies" + Style.RESET_ALL)
        if package.dependencies and package.dependencies != ["No dependencies listed"]:
            for dep in package.dependencies:
                report.append(Fore.WHITE + f"• {dep}" + Fore.RESET)
        else:
            report.append(Fore.WHITE + "No dependencies listed" + Fore.RESET)
        if package.dev_dependencies:
            report.append("\n" + Fore.YELLOW + Style.BRIGHT + "🔧 Development Dependencies" + Style.RESET_ALL)
            for dep in package.dev_dependencies:
                report.append(Fore.WHITE + f"• {dep}" + Fore.RESET)
        if package.downloads:
            report.append("\n" + Fore.YELLOW + Style.BRIGHT + "📊 Download Statistics" + Style.RESET_ALL)
            for period, count in package.downloads.items():
                report.append(Fore.WHITE + f"{period}: {count}" + Fore.RESET)
        if package.all_versions:
            report.append("\n" + Fore.YELLOW + Style.BRIGHT + "🏷️ Version History" + Style.RESET_ALL)
            for i, version in enumerate(package.all_versions[:10]):
                report.append(Fore.WHITE + f"• {version}" + Fore.RESET)
            if len(package.all_versions) > 10:
                report.append(Fore.WHITE + f"... and {len(package.all_versions) - 10} more versions" + Fore.RESET)
        if package.source_analysis and "error" not in package.source_analysis:
            report.append("\n" + Fore.YELLOW + Style.BRIGHT + "📁 Source Analysis" + Style.RESET_ALL)
            report.append(Fore.WHITE + f"Total files: {package.source_analysis.get('file_count', 0)}" + Fore.RESET)
            report.append(Fore.WHITE + f"Total lines: {package.source_analysis.get('total_lines', 0)}" + Fore.RESET)
            report.append(Fore.WHITE + f"Code lines: {package.source_analysis.get('code_lines', 0)}" + Fore.RESET)
            report.append(Fore.WHITE + f"Comment lines: {package.source_analysis.get('comment_lines', 0)}" + Fore.RESET)
            report.append(Fore.WHITE + f"Blank lines: {package.source_analysis.get('blank_lines', 0)}" + Fore.RESET)
            if "file_types" in package.source_analysis:
                report.append("\n" + Fore.YELLOW + Style.BRIGHT + "File Types:" + Style.RESET_ALL)
                for ext, count in sorted(package.source_analysis["file_types"].items(), key=lambda x: x[1], reverse=True):
                    report.append(Fore.WHITE + f"• {ext}: {count}" + Fore.RESET)
        return "\n".join(report)
    
    def _generate_json_report(self, package: PackageInfo) -> str:
        return json.dumps(package.to_dict(), indent=2)
    
    def _generate_markdown_report(self, package: PackageInfo) -> str:
        from mdutils.mdutils import MdUtils
        if package.error:
            return f"# Error\n\n{package.error}"
        md = MdUtils(file_name="", title=f"{package.name} ({package.version})")
        md.new_header(level=1, title="Basic Information")
        md.new_paragraph(f"**Description:** {package.description}")
        md.new_paragraph(f"**Author:** {package.author}")
        md.new_paragraph(f"**Author Email:** {package.author_email}")
        md.new_paragraph(f"**License:** {package.license}")
        md.new_paragraph(f"**Release Date:** {package.release_date or 'Unknown'}")
        if package.project_urls:
            md.new_header(level=1, title="Project URLs")
            for key, url in package.project_urls.items():
                md.new_paragraph(f"**{key}:** [{url}]({url})")
        if package.github_url:
            md.new_header(level=1, title="GitHub Information")
            md.new_paragraph(f"**Repository:** [{package.github_url}]({package.github_url})")
            if package.github_stats:
                for key, value in package.github_stats.items():
                    if value is not None:
                        key_formatted = key.replace("_", " ").title()
                        md.new_paragraph(f"**{key_formatted}:** {value}")
        md.new_header(level=1, title="Dependencies")
        if package.dependencies and package.dependencies != ["No dependencies listed"]:
            for dep in package.dependencies:
                md.new_line(f"* {dep}")
        else:
            md.new_paragraph("No dependencies listed")
        if package.dev_dependencies:
            md.new_header(level=1, title="Development Dependencies")
            for dep in package.dev_dependencies:
                md.new_line(f"* {dep}")
        if package.downloads:
            md.new_header(level=1, title="Download Statistics")
            for period, count in package.downloads.items():
                md.new_paragraph(f"**{period}:** {count}")
        if package.all_versions:
            md.new_header(level=1, title="Version History")
            for version in package.all_versions[:10]:
                md.new_line(f"* {version}")
            if len(package.all_versions) > 10:
                md.new_paragraph(f"... and {len(package.all_versions) - 10} more versions")
        if package.source_analysis and "error" not in package.source_analysis:
            md.new_header(level=1, title="Source Analysis")
            md.new_paragraph(f"**Total files:** {package.source_analysis.get('file_count', 0)}")
            md.new_paragraph(f"**Total lines:** {package.source_analysis.get('total_lines', 0)}")
            md.new_paragraph(f"**Code lines:** {package.source_analysis.get('code_lines', 0)}")
            md.new_paragraph(f"**Comment lines:** {package.source_analysis.get('comment_lines', 0)}")
            md.new_paragraph(f"**Blank lines:** {package.source_analysis.get('blank_lines', 0)}")
            if "file_types" in package.source_analysis:
                md.new_header(level=2, title="File Types")
                for ext, count in sorted(package.source_analysis["file_types"].items(), key=lambda x: x[1], reverse=True):
                    md.new_line(f"* {ext}: {count}")
        return md.get_md_text()
    
    def _generate_html_report(self, package: PackageInfo) -> str:
        if package.error:
            return f"<h1>Error</h1><p>{package.error}</p>"
        markdown_report = self._generate_markdown_report(package)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{package.name} - PyPI Package Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f7ff;
        }}
        .header {{
            background: linear-gradient(135deg, #9370DB, #8A2BE2);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .llama-logo {{
            font-family: monospace;
            white-space: pre;
            margin-top: 20px;
            color: #e0d8ff;
        }}
        h1, h2, h3 {{
            color: #6A5ACD;
        }}
        a {{
            color: #9370DB;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .section {{
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        .badge {{
            display: inline-block;
            background-color: #9370DB;
            color: white;
            border-radius: 15px;
            padding: 5px 10px;
            font-size: 0.8em;
            margin-right: 5px;
            margin-bottom: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px 15px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }}
        th {{
            background-color: #f2f0fa;
            color: #6A5ACD;
        }}
        tr:hover {{
            background-color: #f5f0ff;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: #666;
            font-size: 0.9em;
        }}
        .stats {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            gap: 10px;
        }}
        .stat-box {{
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            flex: 1;
            min-width: 180px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 1.8em;
            font-weight: bold;
            color: #6A5ACD;
            margin: 5px 0;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{package.name} v{package.version}</h1>
        <p>{package.description}</p>
        <div class="llama-logo">
                 ⟋|、
                (˚ˎ 。7  
                |、˜〵    Ultimate Llama PyPI Scraper
                じしˍ,)ノ  Package Analysis Report
        </div>
    </div>
    
    <div class="section">
        <h2>📦 Basic Information</h2>
        <p><strong>Author:</strong> {package.author}</p>
        <p><strong>Author Email:</strong> {package.author_email}</p>
        <p><strong>License:</strong> {package.license}</p>
        <p><strong>Release Date:</strong> {package.release_date or 'Unknown'}</p>
    </div>"""
        if package.project_urls:
            html += """
    <div class="section">
        <h2>🔗 Project URLs</h2>
        <ul>"""
            for key, url in package.project_urls.items():
                html += f"""
            <li><strong>{key}:</strong> <a href="{url}" target="_blank">{url}</a></li>"""
            html += """
        </ul>
    </div>"""
        if package.github_url:
            html += f"""
    <div class="section">
        <h2>🐙 GitHub Information</h2>
        <p><strong>Repository:</strong> <a href="{package.github_url}" target="_blank">{package.github_url}</a></p>"""
            if package.github_stats:
                html += """
        <div class="stats">"""
                for key, value in package.github_stats.items():
                    if value is not None and key in ['stars', 'forks', 'open_issues', 'watchers']:
                        key_formatted = key.replace("_", " ").title()
                        html += f"""
            <div class="stat-box">
                <div class="stat-label">{key_formatted}</div>
                <div class="stat-number">{value}</div>
            </div>"""
                html += """
        </div>"""
                html += """
        <table>
            <tbody>"""
                for key, value in package.github_stats.items():
                    if value is not None and key not in ['stars', 'forks', 'open_issues', 'watchers']:
                        key_formatted = key.replace("_", " ").title()
                        html += f"""
                <tr>
                    <th>{key_formatted}</th>
                    <td>{value}</td>
                </tr>"""
                html += """
            </tbody>
        </table>"""
            html += """
    </div>"""
        html += """
    <div class="section">
        <h2>🔄 Dependencies</h2>"""
        if package.dependencies and package.dependencies != ["No dependencies listed"]:
            html += """
        <ul>"""
            for dep in package.dependencies:
                html += f"""
            <li>{dep}</li>"""
            html += """
        </ul>"""
        else:
            html += """
        <p>No dependencies listed</p>"""
        html += """
    </div>"""
        if package.dev_dependencies:
            html += """
    <div class="section">
        <h2>🔧 Development Dependencies</h2>
        <ul>"""
            for dep in package.dev_dependencies:
                html += f"""
            <li>{dep}</li>"""
            html += """
        </ul>
    </div>"""
        if package.downloads:
            html += """
    <div class="section">
        <h2>📊 Download Statistics</h2>
        <div class="stats">"""
            for period, count in package.downloads.items():
                html += f"""
            <div class="stat-box">
                <div class="stat-label">{period}</div>
                <div class="stat-number">{count}</div>
            </div>"""
            html += """
        </div>
    </div>"""
        if package.all_versions:
            html += """
    <div class="section">
        <h2>🏷️ Version History</h2>
        <div style="display: flex; flex-wrap: wrap; gap: 8px;">"""
            for version in package.all_versions[:20]:
                html += f"""
            <span class="badge">{version}</span>"""
            html += """
        </div>"""
            if len(package.all_versions) > 20:
                html += f"""
        <p>... and {len(package.all_versions) - 20} more versions</p>"""
            html += """
    </div>"""
        if package.source_analysis and "error" not in package.source_analysis:
            html += """
    <div class="section">
        <h2>📁 Source Analysis</h2>
        <div class="stats">"""
            metrics = [
                ("Total Files", package.source_analysis.get('file_count', 0)),
                ("Total Lines", package.source_analysis.get('total_lines', 0)),
                ("Code Lines", package.source_analysis.get('code_lines', 0)),
                ("Comment Lines", package.source_analysis.get('comment_lines', 0)),
                ("Blank Lines", package.source_analysis.get('blank_lines', 0))
            ]
            for label, value in metrics:
                html += f"""
            <div class="stat-box">
                <div class="stat-label">{label}</div>
                <div class="stat-number">{value}</div>
            </div>"""
            html += """
        </div>"""
            if "file_types" in package.source_analysis:
                html += """
        <h3>File Types</h3>
        <table>
            <thead>
                <tr>
                    <th>Extension</th>
                    <th>Count</th>
                </tr>
            </thead>
            <tbody>"""
                for ext, count in sorted(package.source_analysis["file_types"].items(), key=lambda x: x[1], reverse=True):
                    html += f"""
                <tr>
                    <td>{ext}</td>
                    <td>{count}</td>
                </tr>"""
                html += """
            </tbody>
        </table>"""
            html += """
    </div>"""
        html += f"""
    <div class="footer">
        <p>Generated by Ultimate Llama PyPI Scraper on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
</body>
</html>"""
        return html
    
    def save_report(self, package: PackageInfo, output_format: str = "text") -> str:
        output_dir = os.path.join(self.output_dir, package.name, package.version)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_format == "json":
            ext = "json"
        elif output_format == "markdown":
            ext = "md"
        elif output_format == "html":
            ext = "html"
        else:
            ext = "txt"
        filename = f"{package.name}_{package.version}_{timestamp}.{ext}"
        filepath = os.path.join(output_dir, filename)
        report = self.generate_report(package, output_format)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report)
        return filepath
    
    def bulk_analyze(self, package_names: List[str], output_format: str = "text", include_source_analysis: bool = False):
        results = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task(f"[cyan]Analyzing {len(package_names)} packages...", total=len(package_names))
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for package_name in package_names:
                    future = executor.submit(self._analyze_single_package, package_name, include_source_analysis)
                    futures.append(future)
                for future in as_completed(futures):
                    package = future.result()
                    results.append(package)
                    if package and not package.error:
                        self.save_report(package, output_format)
                    progress.update(task, advance=1)
        return results
    
    def _analyze_single_package(self, package_name: str, include_source_analysis: bool) -> PackageInfo:
        try:
            package = self.fetch_package_info(package_name)
            if package and not package.error and include_source_analysis:
                package.source_analysis = self.analyze_package_source(package_name, package.version)
            return package
        except Exception as e:
            logger.error(f"Error analyzing {package_name}: {e}")
            package = PackageInfo(package_name)
            package.error = str(e)
            return package
    
    def search_packages(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        try:
            url = f"https://pypi.org/search/?q={query}&format=json"
            response = self.fetch_with_retry(url)
            if not response:
                return []
            data = response.json()
            results = data.get("results", [])
            results = results[:max_results]
            return results
        except Exception as e:
            logger.error(f"Error searching for packages: {e}")
            return {}
    
    def generate_comparison_chart(self, packages: List[PackageInfo], metric: str = "downloads") -> str:
        if not packages:
            return "No packages to compare"
        try:
            if metric == "downloads":
                data = []
                for pkg in packages:
                    if pkg.downloads:
                        data.append({
                            "name": pkg.name,
                            "downloads": pkg.downloads.get("last_month", 0)
                        })
                if not data:
                    return "No download data available for the packages"
                df = pd.DataFrame(data)
                df = df.sort_values("downloads", ascending=False)
                fig = px.bar(
                    df, 
                    x="name", 
                    y="downloads", 
                    title="Monthly Downloads Comparison",
                    labels={"name": "Package", "downloads": "Downloads (Last Month)"},
                    color="downloads",
                    color_continuous_scale="Viridis"
                )
                fig.update_layout(
                    plot_bgcolor='rgba(240,240,248,0.9)',
                    font=dict(family="Arial", size=12),
                    title_font=dict(family="Arial", size=16, color="#6A5ACD"),
                    xaxis=dict(title_font=dict(family="Arial", size=14)),
                    yaxis=dict(title_font=dict(family="Arial", size=14))
                )
                temp_file = os.path.join(self.temp_dir, "downloads_comparison.html")
                fig.write_html(temp_file)
                return temp_file
            elif metric == "github_stars":
                data = []
                for pkg in packages:
                    if pkg.github_stats and "stars" in pkg.github_stats:
                        data.append({
                            "name": pkg.name,
                            "stars": pkg.github_stats.get("stars", 0)
                        })
                if not data:
                    return "No GitHub data available for the packages"
                df = pd.DataFrame(data)
                df = df.sort_values("stars", ascending=False)
                fig = px.bar(
                    df, 
                    x="name", 
                    y="stars", 
                    title="GitHub Stars Comparison",
                    labels={"name": "Package", "stars": "GitHub Stars"},
                    color="stars",
                    color_continuous_scale="Viridis"
                )
                fig.update_layout(
                    plot_bgcolor='rgba(240,240,248,0.9)',
                    font=dict(family="Arial", size=12),
                    title_font=dict(family="Arial", size=16, color="#6A5ACD"),
                    xaxis=dict(title_font=dict(family="Arial", size=14)),
                    yaxis=dict(title_font=dict(family="Arial", size=14))
                )
                temp_file = os.path.join(self.temp_dir, "github_stars_comparison.html")
                fig.write_html(temp_file)
                return temp_file
            elif metric == "code_size":
                data = []
                for pkg in packages:
                    if pkg.source_analysis and "total_lines" in pkg.source_analysis:
                        data.append({
                            "name": pkg.name,
                            "total_lines": pkg.source_analysis.get("total_lines", 0),
                            "code_lines": pkg.source_analysis.get("code_lines", 0),
                            "comment_lines": pkg.source_analysis.get("comment_lines", 0),
                            "blank_lines": pkg.source_analysis.get("blank_lines", 0)
                        })
                if not data:
                    return "No source analysis data available for the packages"
                df = pd.DataFrame(data)
                df = df.sort_values("total_lines", ascending=False)
                fig = px.bar(
                    df, 
                    x="name", 
                    y=["code_lines", "comment_lines", "blank_lines"],
                    title="Code Size Comparison",
                    labels={"name": "Package", "value": "Lines", "variable": "Type"},
                    color_discrete_map={
                        "code_lines": "#6A5ACD",
                        "comment_lines": "#9370DB",
                        "blank_lines": "#D8BFD8"
                    }
                )
                fig.update_layout(
                    plot_bgcolor='rgba(240,240,248,0.9)',
                    font=dict(family="Arial", size=12),
                    title_font=dict(family="Arial", size=16, color="#6A5ACD"),
                    xaxis=dict(title_font=dict(family="Arial", size=14)),
                    yaxis=dict(title_font=dict(family="Arial", size=14)),
                    barmode='stack'
                )
                temp_file = os.path.join(self.temp_dir, "code_size_comparison.html")
                fig.write_html(temp_file)
                return temp_file
            else:
                return f"Unsupported metric: {metric}"
        except Exception as e:
            logger.error(f"Error generating comparison chart: {e}")
            return f"Error generating chart: {e}"
    
    def display_rich_package_info(self, package: PackageInfo):
        if package.error:
            console.print(f"[bold red]Error:[/bold red] {package.error}")
            return
        table = Table(title=f"[bold magenta]{package.name} v{package.version}[/bold magenta]", box=ROUNDED)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        table.add_row("Description", package.description)
        table.add_row("Author", package.author)
        table.add_row("License", package.license)
        table.add_row("Release Date", package.release_date or "Unknown")
        console.print(table)
        if package.project_urls:
            console.print("\n[bold cyan]Project URLs:[/bold cyan]")
            urls_table = Table(box=ROUNDED)
            urls_table.add_column("Type", style="green")
            urls_table.add_column("URL", style="blue")
            for key, url in package.project_urls.items():
                urls_table.add_row(key, url)
            console.print(urls_table)
        if package.github_url:
            console.print("\n[bold cyan]GitHub Information:[/bold cyan]")
            console.print(f"Repository: [link={package.github_url}]{package.github_url}[/link]")
            if package.github_stats:
                github_table = Table(box=ROUNDED)
                github_table.add_column("Metric", style="green")
                github_table.add_column("Value", style="blue")
                for key, value in package.github_stats.items():
                    if value is not None:
                        key_formatted = key.replace("_", " ").title()
                        github_table.add_row(key_formatted, str(value))
                console.print(github_table)
        console.print("\n[bold cyan]Dependencies:[/bold cyan]")
        if package.dependencies and package.dependencies != ["No dependencies listed"]:
            deps_panel = Panel("\n".join([f"• {dep}" for dep in package.dependencies]), title="Regular Dependencies")
            console.print(deps_panel)
        else:
            console.print("[italic]No dependencies listed[/italic]")
        if package.dev_dependencies:
            dev_deps_panel = Panel("\n".join([f"• {dep}" for dep in package.dev_dependencies]), title="Development Dependencies")
            console.print(dev_deps_panel)
        if package.downloads:
            console.print("\n[bold cyan]Download Statistics:[/bold cyan]")
            downloads_table = Table(box=ROUNDED)
            downloads_table.add_column("Period", style="green")
            downloads_table.add_column("Count", style="blue")
            for period, count in package.downloads.items():
                downloads_table.add_row(period, str(count))
            console.print(downloads_table)
        if package.all_versions:
            console.print("\n[bold cyan]Version History:[/bold cyan]")
            versions_text = " ".join([f"[magenta]{version}[/magenta]" for version in package.all_versions[:10]])
            if len(package.all_versions) > 10:
                versions_text += f"\n... and {len(package.all_versions) - 10} more versions"
            console.print(versions_text)
        if package.source_analysis and "error" not in package.source_analysis:
            console.print("\n[bold cyan]Source Analysis:[/bold cyan]")
            source_table = Table(box=ROUNDED)
            source_table.add_column("Metric", style="green")
            source_table.add_column("Value", style="blue")
            source_table.add_row("Total files", str(package.source_analysis.get("file_count", 0)))
            source_table.add_row("Total lines", str(package.source_analysis.get("total_lines", 0)))
            source_table.add_row("Code lines", str(package.source_analysis.get("code_lines", 0)))
            source_table.add_row("Comment lines", str(package.source_analysis.get("comment_lines", 0)))
            source_table.add_row("Blank lines", str(package.source_analysis.get("blank_lines", 0)))
            console.print(source_table)
            if "file_types" in package.source_analysis:
                console.print("\n[bold green]File Types:[/bold green]")
                file_types_table = Table(box=ROUNDED)
                file_types_table.add_column("Extension", style="cyan")
                file_types_table.add_column("Count", style="magenta")
                for ext, count in sorted(package.source_analysis["file_types"].items(), key=lambda x: x[1], reverse=True):
                    file_types_table.add_row(ext, str(count))
                console.print(file_types_table)

class LlamaTextualUI:
    """Textual UI for the PyPI Scraper (if textual is available)."""
    
    @staticmethod
    def run():
        if not TEXTUAL_AVAILABLE:
            console.print("[bold red]Textual not installed. Cannot display UI.[/bold red]")
            console.print("[bold yellow]Install with:[/bold yellow] pip install textual")
            return
        class PyPIScraperApp(App):
            TITLE = "Ultimate Llama PyPI Scraper"
            def compose(self):
                yield Header()
                yield Footer()
        app = PyPIScraperApp()
        app.run()

def display_llama_banner():
    try:
        figlet = Figlet(font='slant')
        llama_title = figlet.renderText('Llama PyPI')
        console.print(Panel(f"[magenta]{llama_title}[/magenta]", subtitle="Ultimate PyPI Scraper v2.1"))
    except Exception:
        console.print(Panel(LLAMA_LOGO, title="[bold magenta]Ultimate Llama PyPI Scraper v2.1[/bold magenta]"))
    console.print("[cyan]A comprehensive tool for scraping and organizing Python package information[/cyan]")
    console.print("[magenta]Enhanced with anti-detection mechanisms, beautiful visualizations, and Llama UI[/magenta]\n")

def fetch_packages_from_user_profile(url: str) -> List[str]:
    """Fetch package names from a PyPI user profile URL."""
    packages = []
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a['href']
            if href.startswith("/project/"):
                parts = href.split("/")
                if len(parts) >= 3:
                    pkg_name = parts[2]
                    if pkg_name and pkg_name not in packages:
                        packages.append(pkg_name)
    except Exception as e:
        logger.error(f"Error fetching packages from user profile {url}: {e}")
    return packages

def parse_arguments():
    parser = argparse.ArgumentParser(description="Ultimate Llama PyPI Scraper - A comprehensive tool for scraping and organizing Python package information")
    parser.add_argument("packages", nargs="*", help="PyPI package name(s) or user profile URL(s) to analyze")
    parser.add_argument("-f", "--file", help="Path to a file containing package names or user profile URLs (one per line)")
    parser.add_argument("-s", "--search", help="Search for packages matching the query")
    parser.add_argument("-o", "--output-dir", default=DEFAULT_OUTPUT_DIR, help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("-t", "--temp-dir", default=TEMP_DIR, help=f"Temporary directory (default: {TEMP_DIR})")
    parser.add_argument("--format", choices=["text", "json", "markdown", "html"], default="text", help="Output format (default: text)")
    parser.add_argument("--source-analysis", action="store_true", help="Include source code analysis")
    parser.add_argument("--no-browser", action="store_true", help="Disable browser automation")
    parser.add_argument("--no-cloudscraper", action="store_true", help="Disable cloudscraper (use standard requests)")
    parser.add_argument("--github-token", help="GitHub API token")
    parser.add_argument("--compare", choices=["downloads", "github_stars", "code_size"], help="Generate comparison chart")
    parser.add_argument("--ui", action="store_true", help="Launch the interactive UI (requires textual)")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    parser.add_argument("--test", action="store_true", help="Run tests")
    return parser.parse_args()

def main():
    args = parse_arguments()
    if args.quiet:
        logger.setLevel(logging.WARNING)
    display_llama_banner()
    if args.test:
        run_tests()
        return
    if args.ui:
        LlamaTextualUI.run()
        return
    package_names = []
    if args.packages:
        package_names.extend(args.packages)
    if args.file:
        try:
            with open(args.file, "r") as f:
                file_packages = [line.strip() for line in f if line.strip()]
                package_names.extend(file_packages)
        except Exception as e:
            logger.error(f"Error reading package file: {e}")
    if args.search:
        scraper = LlamaPyPIScraper(
            output_dir=args.output_dir,
            temp_dir=args.temp_dir,
            github_token=args.github_token or GITHUB_TOKEN,
            use_cloudscraper=not args.no_cloudscraper,
            use_browser_automation=not args.no_browser
        )
        console.print(f"[cyan]Searching for packages matching '[bold]{args.search}[/bold]'...[/cyan]")
        search_results = scraper.search_packages(args.search)
        if search_results:
            console.print(f"[green]Found {len(search_results)} packages:[/green]")
            search_table = Table(box=ROUNDED)
            search_table.add_column("Name", style="cyan")
            search_table.add_column("Version", style="magenta")
            search_table.add_column("Description")
            for result in search_results:
                search_table.add_row(
                    result.get("name", "N/A"),
                    result.get("version", "N/A"),
                    result.get("description", "No description available")
                )
            console.print(search_table)
            console.print("[yellow]Enter the numbers of packages to analyze (comma-separated) or 'all':[/yellow]")
            selection = input("> ").strip()
            if selection.lower() == "all":
                package_names.extend([result.get("name") for result in search_results])
            else:
                try:
                    indices = [int(idx.strip()) - 1 for idx in selection.split(",")]
                    for idx in indices:
                        if 0 <= idx < len(search_results):
                            package_names.append(search_results[idx].get("name"))
                except Exception as e:
                    logger.error(f"Invalid selection: {e}")
        else:
            console.print("[red]No packages found.[/red]")
    # Process user profile URLs
    final_package_names = []
    for pkg in package_names:
        if pkg.startswith("http") and "pypi.org/user/" in pkg:
            user_packages = fetch_packages_from_user_profile(pkg)
            if user_packages:
                final_package_names.extend(user_packages)
        else:
            final_package_names.append(pkg)
    package_names = list(set(final_package_names))
    if not package_names:
        console.print("[yellow]No packages specified. Use positional arguments, -f/--file, or -s/--search.[/yellow]")
        return
    scraper = LlamaPyPIScraper(
        output_dir=args.output_dir,
        temp_dir=args.temp_dir,
        github_token=args.github_token or GITHUB_TOKEN,
        use_cloudscraper=not args.no_cloudscraper,
        use_browser_automation=not args.no_browser
    )
    if args.compare and len(package_names) > 1:
        source_analysis_needed = args.compare == "code_size" or args.source_analysis
        console.print(f"[cyan]Analyzing {len(package_names)} packages for comparison...[/cyan]")
        packages = scraper.bulk_analyze(package_names, args.format, source_analysis_needed)
        chart_path = scraper.generate_comparison_chart(packages, args.compare)
        if chart_path and os.path.exists(chart_path):
            console.print(f"[green]Comparison chart generated: {chart_path}[/green]")
            webbrowser.open(f"file://{os.path.abspath(chart_path)}")
        else:
            console.print(f"[red]Failed to generate comparison chart.[/red]")
    elif len(package_names) > 1:
        console.print(f"[cyan]Analyzing {len(package_names)} packages...[/cyan]")
        packages = scraper.bulk_analyze(package_names, args.format, args.source_analysis)
        console.print(f"[green]Analysis complete for {len(packages)} packages.[/green]")
        console.print(f"[cyan]Reports saved to: {args.output_dir}[/cyan]")
        summary_table = Table(title="Package Analysis Summary", box=ROUNDED)
        summary_table.add_column("Package", style="cyan")
        summary_table.add_column("Version", style="magenta")
        summary_table.add_column("License", style="green")
        summary_table.add_column("Status", style="yellow")
        for pkg in packages:
            status = "[red]Failed[/red]" if pkg.error else "[green]Success[/green]"
            summary_table.add_row(pkg.name, pkg.version, pkg.license, status)
        console.print(summary_table)
    elif len(package_names) == 1:
        package_name = package_names[0]
        console.print(f"[cyan]Analyzing package: [bold]{package_name}[/bold][/cyan]")
        with yaspin(Spinners.bouncingBar, text=f"Fetching package info...") as spinner:
            package = scraper.fetch_package_info(package_name)
            if package.error:
                spinner.fail("💥")
            else:
                spinner.ok("✅")
        if not package.error and args.source_analysis:
            with yaspin(Spinners.bouncingBar, text=f"Analyzing source code...") as spinner:
                package.source_analysis = scraper.analyze_package_source(package_name, package.version)
                spinner.ok("✅")
        report_path = scraper.save_report(package, args.format)
        console.print(f"[green]Report saved to: {report_path}[/green]")
        scraper.display_rich_package_info(package)
        if args.format == "html" and os.path.exists(report_path):
            webbrowser.open(f"file://{os.path.abspath(report_path)}")
    if scraper.browser:
        scraper.browser.close()

def run_tests():
    console.print("[cyan]Running tests...[/cyan]")
    package_test_list = ["requests", "pandas", "numpy"]
    passed = 0
    failed = 0
    scraper = LlamaPyPIScraper()
    for package_name in package_test_list:
        try:
            with yaspin(Spinners.bouncingBar, text=f"Testing package info fetching for {package_name}...") as spinner:
                package = scraper.fetch_package_info(package_name)
                if package.error:
                    spinner.fail("💥")
                    console.print(f"[red]Failed to fetch info for {package_name}: {package.error}[/red]")
                    failed += 1
                else:
                    spinner.ok("✅")
                    console.print(f"[green]Successfully fetched info for {package_name} v{package.version}[/green]")
                    passed += 1
        except Exception as e:
            console.print(f"[red]Test error for {package_name}: {e}[/red]")
            failed += 1
    try:
        with yaspin(Spinners.bouncingBar, text="Testing anti-detection session...") as spinner:
            session = AntiDetectionRequestSession()
            response = session.get("https://www.python.org")
            if response.status_code == 200:
                spinner.ok("✅")
                console.print("[green]Anti-detection session working properly[/green]")
                passed += 1
            else:
                spinner.fail("💥")
                console.print(f"[red]Anti-detection session failed: {response.status_code}[/red]")
                failed += 1
    except Exception as e:
        console.print(f"[red]Anti-detection session test error: {e}[/red]")
        failed += 1
    try:
        with yaspin(Spinners.bouncingBar, text="Testing cloudscraper...") as spinner:
            scraper_session = cloudscraper.create_scraper()
            response = scraper_session.get("https://www.python.org")
            if response.status_code == 200:
                spinner.ok("✅")
                console.print("[green]Cloudscraper working properly[/green]")
                passed += 1
            else:
                spinner.fail("💥")
                console.print(f"[red]Cloudscraper failed: {response.status_code}[/red]")
                failed += 1
    except Exception as e:
        console.print(f"[red]Cloudscraper test error: {e}[/red]")
        failed += 1
    console.print(f"\n[bold]Test Summary:[/bold] {passed} passed, {failed} failed")
    if failed == 0:
        console.print("[bold green]All tests passed![/bold green]")
    else:
        console.print(f"[bold red]{failed} tests failed.[/bold red]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        if logging.root.level <= logging.DEBUG:
            console.print_exception()
