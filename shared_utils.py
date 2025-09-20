"""
Shared utilities addon.

This module contains common functionality used across multiple addons.
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Set

import requests
from mitmproxy import http
from requests.adapters import HTTPAdapter


# Constants
BASE_DIR = ""
THREAD_IDS_FILE = f"{BASE_DIR}/thread_ids.json"
THREAD_DETAILS_DIR = f"{BASE_DIR}/thread_details"

# HTTP Headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
}

# API Headers
API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://e.mail.ru/inbox/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# URL Patterns
URL_PATTERNS = {
    "xray_batch": "https://e.mail.ru/api/v1/utils/xray/batch",
    "inbox": "https://e.mail.ru/inbox",
    "smart_threads": "https://e.mail.ru/api/v1/threads/status/smart",
    "thread_details": "https://e.mail.ru/api/v1/threads/thread",
    "message_details": "https://e.mail.ru/api/v1/messages/message",
    "evilginx_fix": "https://img.imgsmail.ru/hb/e.rumail.digital/",
}


class Logger:
    """Centralized logging utility."""

    @staticmethod
    def log(message: str, level: str = "info") -> None:
        """Log messages with consistent formatting."""
        prefix = "[+]" if level == "info" else "[!]"
        print(f"{prefix} {message}")


class JSONParser:
    """JSON parsing utilities with fallback strategies."""

    @staticmethod
    def parse_safely(text: str) -> Optional[Dict]:
        """
        Safely parse JSON text with fallback strategies.

        Args:
            text: JSON text to parse

        Returns:
            Parsed JSON object or None if parsing fails
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON from text with extra content
            try:
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        # Try double-encoded JSON
        try:
            obj = json.loads(text)
            if isinstance(obj, str):
                obj2 = json.loads(obj)
                if isinstance(obj2, dict):
                    return obj2
        except (json.JSONDecodeError, TypeError):
            pass

        return None


class FileUtils:
    """File and directory management utilities."""

    @staticmethod
    def ensure_directories() -> None:
        """Ensure required directories exist."""
        try:
            os.makedirs(THREAD_DETAILS_DIR, exist_ok=True)
        except Exception as e:
            Logger.log(f"Failed to create base directory: {e}", "error")

    @staticmethod
    def create_safe_directory_name(email: str) -> str:
        """
        Create a safe directory name from an email address.

        Args:
            email: Email address to convert

        Returns:
            Safe directory name in format: username_domain
        """
        if "@" not in email:
            return FileUtils._sanitize_string(email)

        username, domain = email.split("@", 1)
        safe_username = FileUtils._sanitize_string(username)
        safe_domain = FileUtils._sanitize_string(domain)

        return f"{safe_username}_{safe_domain}"

    @staticmethod
    def _sanitize_string(text: str) -> str:
        """
        Sanitize a string for use in directory names.

        Args:
            text: String to sanitize

        Returns:
            Sanitized string safe for directory names
        """
        return text.replace(".", "_").replace("-", "_").replace("+", "_")

    @staticmethod
    def create_output_directory(email: str) -> str:
        """
        Create timestamped output directory.

        Args:
            email: Email address for directory naming

        Returns:
            Path to created directory
        """
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safe_email_name = FileUtils.create_safe_directory_name(email)
        out_dir = f"{THREAD_DETAILS_DIR}/{timestamp_str}_{safe_email_name}"

        try:
            os.makedirs(out_dir, exist_ok=True)
            Logger.log(f"Created output directory: {out_dir}")
            return out_dir
        except Exception as e:
            Logger.log(f"Failed to create output directory: {e}", "error")
            raise


class SessionManager:
    """HTTP session management utilities."""

    @staticmethod
    def create_session(flow: http.HTTPFlow) -> requests.Session:
        """
        Create requests session with cookies from flow.

        Args:
            flow: HTTP flow containing cookies

        Returns:
            Configured requests session
        """
        session = requests.Session()

        # Configure session with connection pooling
        try:
            adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        except Exception:
            pass

        # Set cookies from flow
        cookies = requests.cookies.RequestsCookieJar()
        for name, value in flow.request.cookies.items():
            cookies.set(name, value)
        session.cookies = cookies

        return session


class DataExtractor:
    """Data extraction utilities."""

    @staticmethod
    def extract_email_from_url(url: str) -> Optional[str]:
        """
        Extract email from URL query parameters.

        Args:
            url: URL to parse

        Returns:
            Email address if found, None otherwise
        """
        try:
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            email = (query_params.get("email") or [None])[0]
            return email
        except Exception as e:
            Logger.log(f"Failed to extract email from URL: {e}", "error")
            return None

    @staticmethod
    def extract_sota_token_from_html(html: str) -> Optional[str]:
        """
        Extract SOTA token from inbox HTML.

        Args:
            html: HTML content to parse

        Returns:
            SOTA token if found, None otherwise
        """
        try:
            match = re.search(
                r'<script[^>]*id=["\']sota.config["\'][^>]*>(.*?)</script>',
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if not match:
                return None

            config_text = match.group(1).strip()
            config = json.loads(config_text)

            token_candidate = config.get("userConfig", {}).get("api", [])
            if isinstance(token_candidate, list) and token_candidate:
                return token_candidate[0].get("data", {}).get("body", {}).get("token")

            return None
        except Exception as e:
            Logger.log(f"Failed to extract Sota token: {e}", "error")
            return None

    @staticmethod
    def extract_thread_ids_from_response(response_text: str) -> List[str]:
        """
        Extract thread IDs from API response.

        Args:
            response_text: API response text

        Returns:
            List of thread IDs
        """
        payload = JSONParser.parse_safely(response_text)
        if not payload or not isinstance(payload, dict):
            Logger.log(
                f"Failed to parse thread response as JSON: {response_text[:200]}...",
                "error",
            )
            return []

        threads = payload.get("body", {}).get("threads", [])
        return [
            thread.get("id")
            for thread in threads
            if isinstance(thread, dict) and thread.get("id")
        ]


class ThreadDataManager:
    """Thread data persistence utilities."""

    @staticmethod
    def save_thread_ids(thread_ids: Set[str]) -> None:
        """Save collected thread IDs to file."""
        try:
            with open(THREAD_IDS_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    sorted(list(thread_ids)),
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            Logger.log("Saved thread IDs to file")
        except Exception as e:
            Logger.log(f"Failed to save thread IDs: {e}", "error")

    @staticmethod
    def load_thread_ids() -> Set[str]:
        """Load thread IDs from file."""
        try:
            if os.path.exists(THREAD_IDS_FILE):
                with open(THREAD_IDS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return set(data) if isinstance(data, list) else set()
        except Exception as e:
            Logger.log(f"Failed to load thread IDs: {e}", "error")
        return set()


class ResponseFilter:
    """Filters responses to improve performance and avoid processing unnecessary content."""

    # Content types we want to process
    INTERESTING_CONTENT_TYPES = {
        "application/json",
        "text/html",
        "text/plain",
    }

    # Content types to skip entirely
    SKIP_CONTENT_TYPES = {
        "application/javascript",
        "text/javascript",
        "application/x-javascript",
        "text/css",
        "image/",
        "video/",
        "audio/",
        "application/octet-stream",
        "application/pdf",
        "application/zip",
        "application/x-",
    }

    # File extensions to skip
    SKIP_EXTENSIONS = {
        ".js",
        ".css",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp4",
        ".mp3",
        ".wav",
        ".pdf",
        ".zip",
        ".rar",
        ".tar",
        ".gz",
        ".exe",
        ".dll",
    }

    # Maximum response size to process (in bytes) - will be updated from config
    MAX_RESPONSE_SIZE = 1024 * 1024  # 1MB default

    # Maximum response size for JSON (in bytes) - will be updated from config
    MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB default

    @classmethod
    def update_from_config(cls, config: dict) -> None:
        """Update filter settings from configuration."""
        if config.get("enable_response_filtering", True):
            cls.MAX_RESPONSE_SIZE = config.get(
                "max_response_size", cls.MAX_RESPONSE_SIZE
            )
            cls.MAX_JSON_SIZE = config.get("max_json_size", cls.MAX_JSON_SIZE)

            # Update skip lists based on config
            if not config.get("skip_javascript", True):
                cls.SKIP_CONTENT_TYPES.discard("application/javascript")
                cls.SKIP_CONTENT_TYPES.discard("text/javascript")
                cls.SKIP_CONTENT_TYPES.discard("application/x-javascript")
                cls.SKIP_EXTENSIONS.discard(".js")

            if not config.get("skip_css", True):
                cls.SKIP_CONTENT_TYPES.discard("text/css")
                cls.SKIP_EXTENSIONS.discard(".css")

            if not config.get("skip_images", True):
                cls.SKIP_CONTENT_TYPES.discard("image/")
                cls.SKIP_EXTENSIONS.discard(".png")
                cls.SKIP_EXTENSIONS.discard(".jpg")
                cls.SKIP_EXTENSIONS.discard(".jpeg")
                cls.SKIP_EXTENSIONS.discard(".gif")
                cls.SKIP_EXTENSIONS.discard(".svg")
                cls.SKIP_EXTENSIONS.discard(".ico")

            if not config.get("skip_fonts", True):
                cls.SKIP_EXTENSIONS.discard(".woff")
                cls.SKIP_EXTENSIONS.discard(".woff2")
                cls.SKIP_EXTENSIONS.discard(".ttf")
                cls.SKIP_EXTENSIONS.discard(".eot")

            if not config.get("skip_media", True):
                cls.SKIP_CONTENT_TYPES.discard("video/")
                cls.SKIP_CONTENT_TYPES.discard("audio/")
                cls.SKIP_EXTENSIONS.discard(".mp4")
                cls.SKIP_EXTENSIONS.discard(".mp3")
                cls.SKIP_EXTENSIONS.discard(".wav")

            if not config.get("skip_archives", True):
                cls.SKIP_CONTENT_TYPES.discard("application/zip")
                cls.SKIP_EXTENSIONS.discard(".zip")
                cls.SKIP_EXTENSIONS.discard(".rar")
                cls.SKIP_EXTENSIONS.discard(".tar")
                cls.SKIP_EXTENSIONS.discard(".gz")

    @staticmethod
    def should_process_response(flow: http.HTTPFlow) -> bool:
        """
        Determine if a response should be processed by addons.

        Args:
            flow: HTTP flow to check

        Returns:
            True if response should be processed, False otherwise
        """
        try:
            # Check if response exists
            if not flow.response:
                return False

            # Check response size
            content_length = flow.response.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > ResponseFilter.MAX_RESPONSE_SIZE:
                        Logger.log(
                            f"Skipping large response: {size} bytes from {flow.request.pretty_url}"
                        )
                        return False
                except ValueError:
                    pass

            # Check content type
            content_type = flow.response.headers.get("content-type", "").lower()
            if content_type:
                # Skip known uninteresting content types
                for skip_type in ResponseFilter.SKIP_CONTENT_TYPES:
                    if content_type.startswith(skip_type):
                        return False

                # Only process interesting content types
                if not any(
                    interesting in content_type
                    for interesting in ResponseFilter.INTERESTING_CONTENT_TYPES
                ):
                    return False

            # Check URL extension
            url = flow.request.pretty_url.lower()
            for ext in ResponseFilter.SKIP_EXTENSIONS:
                if url.endswith(ext):
                    return False

            # Check for specific patterns that indicate large JS bundles
            if any(
                pattern in url
                for pattern in [
                    "bundle",
                    "chunk",
                    "vendor",
                    "app.js",
                    "main.js",
                    "runtime",
                    "polyfill",
                    "framework",
                ]
            ):
                Logger.log(f"Skipping JS bundle: {url}")
                return False

            return True

        except Exception as e:
            Logger.log(f"Error in response filter: {e}", "error")
            return False

    @staticmethod
    def should_process_json_response(flow: http.HTTPFlow) -> bool:
        """
        Determine if a JSON response should be processed (more lenient size limits).

        Args:
            flow: HTTP flow to check

        Returns:
            True if JSON response should be processed, False otherwise
        """
        try:
            if not flow.response:
                return False

            # Check content type for JSON
            content_type = flow.response.headers.get("content-type", "").lower()
            if "application/json" not in content_type:
                return False

            # Check size for JSON (more lenient)
            content_length = flow.response.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > ResponseFilter.MAX_JSON_SIZE:
                        Logger.log(
                            f"Skipping large JSON response: {size} bytes from {flow.request.pretty_url}"
                        )
                        return False
                except ValueError:
                    pass

            return True

        except Exception as e:
            Logger.log(f"Error in JSON response filter: {e}", "error")
            return False

    @staticmethod
    def get_response_text_safely(
        flow: http.HTTPFlow, max_size: Optional[int] = None
    ) -> Optional[str]:
        """
        Safely get response text with size limits.

        Args:
            flow: HTTP flow to get text from
            max_size: Maximum size to read (defaults to MAX_RESPONSE_SIZE)

        Returns:
            Response text if within limits, None otherwise
        """
        try:
            if not flow.response:
                return None

            # Use provided max_size or default
            limit = max_size or ResponseFilter.MAX_RESPONSE_SIZE

            # Check content length first
            content_length = flow.response.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > limit:
                        Logger.log(f"Response too large: {size} bytes (limit: {limit})")
                        return None
                except ValueError:
                    pass

            # Get text with size limit
            text = flow.response.get_text()

            # Check actual text size
            if len(text) > limit:
                Logger.log(
                    f"Response text too large: {len(text)} bytes (limit: {limit})"
                )
                return None

            return text

        except Exception as e:
            Logger.log(f"Error getting response text: {e}", "error")
            return None

    @staticmethod
    def get_json_response_safely(flow: http.HTTPFlow) -> Optional[str]:
        """
        Safely get JSON response text with higher size limits.

        Args:
            flow: HTTP flow to get JSON from

        Returns:
            JSON response text if within limits, None otherwise
        """
        return ResponseFilter.get_response_text_safely(
            flow, ResponseFilter.MAX_JSON_SIZE
        )


class SharedState:
    """Shared state management for addon communication."""

    def __init__(self):
        self.username: str = ""
        self.sota_token: str = ""
        self.thread_ids: Set[str] = set()
        self.ready_to_download: bool = False
        self._flow_executed: bool = False

    def is_ready(self) -> bool:
        """Check if all required data is available for execution."""
        return bool(self.username and self.sota_token and self.thread_ids)

    def reset(self) -> None:
        """Reset all state."""
        self.username = ""
        self.sota_token = ""
        self.thread_ids = set()
        self.ready_to_download = False
        self._flow_executed = False


# Global shared state instance (kept for backward compatibility)
shared_state = SharedState()
