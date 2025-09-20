"""
Thread Downloader Addon for Mail.ru

Downloads thread data and attachments from Mail.ru API.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

import requests
from mitmproxy import http
from shared_utils import (
    URL_PATTERNS,
    Logger,
    FileUtils,
    SessionManager,
    DEFAULT_HEADERS,
    shared_state,
)
from execution_state import execution_state
from error_classifier import ErrorClassifier, RateLimitError, AuthError, ServerError


class ThreadDownloader:
    """
    Addon that downloads thread data and attachments from Mail.ru API.

    This addon handles downloading individual thread data, processing
    attachments, and creating organized directory structures.
    """

    def __init__(self):
        """Initialize the thread downloader."""
        Logger.log("Thread Downloader addon initialized")

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests (no processing needed for downloading).

        Args:
            flow: HTTP flow to process
        """
        pass

    def response(self, flow: http.HTTPFlow) -> None:
        """
        Handle outgoing responses (no processing needed for downloading).

        Args:
            flow: HTTP flow to process
        """
        pass

    def download_all_threads(self, flow: http.HTTPFlow) -> None:
        """
        Download all collected thread data and attachments.

        Args:
            flow: HTTP flow containing cookies and context
        """
        if not shared_state.thread_ids:
            Logger.log("No thread IDs available for downloading", "error")
            return
        if not shared_state.sota_token:
            Logger.log("Missing SOTA token for downloading", "error")
            return
        if not shared_state.username:
            Logger.log("Missing username for downloading", "error")
            return

        # Create output directory
        try:
            out_dir = FileUtils.create_output_directory(shared_state.username)
        except Exception:
            return

        # Set execution state to downloading
        execution_state.set_downloading(len(shared_state.thread_ids))

        # Create session and headers
        session = SessionManager.create_session(flow)
        headers = dict(DEFAULT_HEADERS)
        headers["Host"] = "e.mail.ru"
        cookies = flow.request.cookies

        # Process threads in parallel
        thread_ids = sorted(list(shared_state.thread_ids))
        total = len(thread_ids)
        success = 0
        max_workers = 24

        Logger.log(f"Starting to process {total} threads with {max_workers} workers")

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_id = {
                    executor.submit(
                        self._fetch_and_save_thread,
                        tid,
                        out_dir,
                        session,
                        headers,
                        cookies,
                    ): tid
                    for tid in thread_ids
                }

                for future in as_completed(future_to_id):
                    tid = future_to_id[future]
                    try:
                        if future.result():
                            success += 1
                            execution_state.update_progress(success)
                            Logger.log(f"Saved thread {tid}")
                    except RateLimitError as e:
                        Logger.log(f"Rate limit error for thread {tid}: {e}", "error")
                        raise  # Re-raise to be handled by orchestrator
                    except AuthError as e:
                        Logger.log(f"Auth error for thread {tid}: {e}", "error")
                        raise  # Re-raise to be handled by orchestrator
                    except ServerError as e:
                        Logger.log(f"Server error for thread {tid}: {e}", "error")
                        raise  # Re-raise to be handled by orchestrator
                    except Exception as e:
                        Logger.log(f"Failed to fetch/save thread {tid}: {e}", "error")

            Logger.log(f"Thread download complete: {success}/{total} saved")
            sys.stdout.flush()

        except (RateLimitError, AuthError, ServerError):
            # Re-raise these errors to be handled by the orchestrator
            raise
        except Exception as e:
            Logger.log(f"Unexpected error during thread download: {e}", "error")
            raise ServerError(f"Thread download failed: {e}")

    def _fetch_and_save_thread(
        self,
        thread_id: str,
        out_dir: str,
        session: requests.Session,
        headers: Dict,
        cookies,
    ) -> bool:
        """
        Fetch and save a single thread with its attachments.

        Args:
            thread_id: Thread ID to fetch
            out_dir: Output directory
            session: Requests session
            headers: HTTP headers
            cookies: Request cookies

        Returns:
            True if successful, False otherwise
        """
        params = {
            "quotes_version": "1",
            "id": thread_id,
            "offset": "0",
            "last_modified": "1",
            "force_custom_thread": "true",
            "use_color_scheme": "1",
            "remove_emoji_opts": json.dumps(
                {
                    "remove_from_sender_name": True,
                    "remove_from_snippet": True,
                    "remove_from_subject": True,
                }
            ),
            "disable_quotation_parser": "true",
            "email": shared_state.username,
            "htmlencoded": "false",
            "token": shared_state.sota_token,
            "_": str(int(time.time() * 1000)),
        }

        try:
            response = session.get(
                URL_PATTERNS["thread_details"],
                headers=headers,
                cookies=cookies,
                params=params,
                timeout=20,
            )

            # Check for HTTP errors and raise appropriate exceptions
            if response.status_code == 429:
                raise RateLimitError(f"Rate limited for thread {thread_id}")
            elif response.status_code in [401, 403]:
                raise AuthError(
                    f"Authentication failed for thread {thread_id}: {response.text}"
                )
            elif response.status_code >= 500:
                raise ServerError(
                    f"Server error {response.status_code} for thread {thread_id}"
                )

            data = response.json()
            if isinstance(data, dict) and data.get("status") == 403:
                raise AuthError(
                    f"API returned 403 for thread {thread_id}. Body: {data.get('body')}"
                )

            # Save thread data
            safe_id = thread_id.replace(":", "_")
            out_path = os.path.join(out_dir, f"{safe_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # Process attachments
            try:
                attach_dir = os.path.join(out_dir, f"{safe_id}_attachments")
                os.makedirs(attach_dir, exist_ok=True)

                body = data.get("body", {})
                messages_raw = (
                    body.get("messages", []) if isinstance(body, dict) else []
                )

                # Parse messages from different structures
                messages = []
                for item in messages_raw:
                    if isinstance(item, dict):
                        if "id" in item:
                            messages.append(item)
                        else:
                            # Handle numeric key structure
                            for key, value in item.items():
                                if (
                                    key.isdigit()
                                    and isinstance(value, dict)
                                    and "id" in value
                                ):
                                    messages.append(value)

                Logger.log(f"Processing {len(messages)} messages in thread {thread_id}")

                # Collect attachment downloads
                downloads = self._process_messages_for_attachments(
                    messages, session, headers, cookies
                )

                # Download attachments
                if downloads:
                    success_count = self._download_attachments(
                        downloads, attach_dir, session, headers, cookies
                    )
                    Logger.log(
                        f"Attachments saved for {thread_id}: {success_count}/{len(downloads)}"
                    )

            except Exception as e:
                Logger.log(
                    f"Attachment processing failed for {thread_id}: {e}", "error"
                )

            return True

        except Exception as e:
            Logger.log(f"Failed to parse JSON for {thread_id}: {e}", "error")
            return False

    def _process_messages_for_attachments(
        self, messages: List[Dict], session: requests.Session, headers: Dict, cookies
    ) -> List[Tuple[str, str]]:
        """
        Process messages to collect attachment URLs.

        Args:
            messages: List of message objects
            session: Requests session
            headers: HTTP headers
            cookies: Request cookies

        Returns:
            List of (url, filename) tuples for attachments
        """
        downloads = []

        # Collect attachments from thread-level response
        for i, msg in enumerate(messages):
            msg_id = msg.get("id", f"msg_{i}")
            attaches = (msg.get("attaches") or {}).get("list") or []
            Logger.log(
                f"Message {msg_id} has {len(attaches)} attachments (thread level)"
            )

            for attachment in attaches:
                hrefs = attachment.get("href") or {}
                url = hrefs.get("download") or hrefs.get("view")
                name = attachment.get("name") or "attachment.bin"
                if url:
                    downloads.append((url, name))
                    Logger.log(f"Found attachment: {name}")

        # Fetch individual message details for messages with attachments
        messages_with_attachments = [
            msg for msg in messages if msg.get("flags", {}).get("attach", False)
        ]

        if messages_with_attachments:

            def fetch_message_details(msg: Dict) -> List[Tuple[str, str]]:
                msg_id = msg.get("id")
                folder_id = msg.get("folder")

                if not msg_id or not folder_id:
                    return []

                msg_params = {
                    "quotes_version": "1",
                    "id": msg_id,
                    "folder_id": str(folder_id),
                    "use_color_scheme": "1",
                    "remove_emoji_opts": "{}",
                    "disable_quotation_parser": "true",
                    "email": shared_state.username,
                    "htmlencoded": "false",
                    "token": shared_state.sota_token,
                    "_": str(int(time.time() * 1000)),
                }

                try:
                    # Retry logic with exponential backoff
                    max_retries = 2
                    for attempt in range(max_retries):
                        try:
                            response = session.get(
                                URL_PATTERNS["message_details"],
                                headers=headers,
                                params=msg_params,
                                timeout=20,
                            )
                            data = response.json()
                            break
                        except Exception as e:
                            if attempt == max_retries - 1:
                                raise e
                            time.sleep(2**attempt)

                    if isinstance(data, dict) and data.get("status") == 200:
                        msg_body = data.get("body", {})
                        msg_attaches = (msg_body.get("attaches") or {}).get(
                            "list"
                        ) or []
                        msg_downloads = []
                        for attachment in msg_attaches:
                            hrefs = attachment.get("href") or {}
                            url = hrefs.get("download") or hrefs.get("view")
                            name = attachment.get("name") or "attachment.bin"
                            if url:
                                msg_downloads.append((url, name))
                        return msg_downloads
                    return []
                except Exception as e:
                    Logger.log(f"Error fetching message {msg_id}: {e}", "error")
                    return []

            # Fetch message details in parallel
            with ThreadPoolExecutor(
                max_workers=min(4, len(messages_with_attachments))
            ) as executor:
                futures = [
                    executor.submit(fetch_message_details, msg)
                    for msg in messages_with_attachments
                ]
                for future in as_completed(futures):
                    try:
                        msg_downloads = future.result()
                        downloads.extend(msg_downloads)
                    except Exception as e:
                        Logger.log(f"Error processing message details: {e}", "error")

        return downloads

    def _download_attachments(
        self,
        downloads: List[Tuple[str, str]],
        attach_dir: str,
        session: requests.Session,
        headers: Dict,
        cookies,
    ) -> int:
        """
        Download attachments in parallel.

        Args:
            downloads: List of (url, filename) tuples
            attach_dir: Directory to save attachments
            session: Requests session
            headers: HTTP headers
            cookies: Request cookies

        Returns:
            Number of successfully downloaded attachments
        """

        def download_attachment(url: str, name: str) -> bool:
            try:
                Logger.log(f"Downloading attachment: {name}")
                response = session.get(
                    url, headers=headers, cookies=cookies, timeout=60
                )
                if response.status_code == 200:
                    file_path = os.path.join(attach_dir, name)
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    Logger.log(f"Saved attachment: {name} -> {file_path}")
                    return True
                else:
                    Logger.log(
                        f"Failed to download {name}: HTTP {response.status_code}",
                        "error",
                    )
                    return False
            except Exception as e:
                Logger.log(f"Error downloading {name}: {e}", "error")
                return False

        success_count = 0
        with ThreadPoolExecutor(max_workers=min(8, len(downloads))) as executor:
            futures = [
                executor.submit(download_attachment, url, name)
                for url, name in downloads
            ]
            for future in as_completed(futures):
                try:
                    if future.result():
                        success_count += 1
                except Exception:
                    pass

        return success_count
