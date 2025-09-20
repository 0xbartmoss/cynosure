"""
Thread Collector Addon for Mail.ru

Collects thread IDs from Mail.ru API responses with pagination support.
"""

import time
from typing import List
from urllib.parse import urlparse, parse_qs

import requests
from mitmproxy import http
from shared_utils import (
    URL_PATTERNS,
    Logger,
    DataExtractor,
    ThreadDataManager,
    SessionManager,
    API_HEADERS,
    shared_state,
)


class ThreadCollector:
    """
    Addon that collects thread IDs from Mail.ru API responses.

    This addon monitors smart threads API responses, extracts thread IDs,
    handles pagination to collect all threads, and persists the data.
    """

    def __init__(self):
        """Initialize the thread collector."""
        Logger.log("Thread Collector addon initialized")

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests (no processing needed for thread collection).

        Args:
            flow: HTTP flow to process
        """
        pass

    def response(self, flow: http.HTTPFlow) -> None:
        """
        Handle outgoing responses and collect thread IDs from smart threads API.

        Args:
            flow: HTTP flow to process
        """
        # Capture thread IDs from smart threads list
        if flow.request.pretty_url.startswith(URL_PATTERNS["smart_threads"]):
            Logger.log("Capturing thread IDs from smart threads list")
            response_text = flow.response.get_text()
            thread_ids = DataExtractor.extract_thread_ids_from_response(response_text)

            if thread_ids:
                before_count = len(shared_state.thread_ids)
                shared_state.thread_ids.update(thread_ids)
                added = len(shared_state.thread_ids) - before_count
                Logger.log(
                    f"Collected {len(thread_ids)} thread IDs, added {added} new (total {len(shared_state.thread_ids)})"
                )

                # Save thread IDs to file
                ThreadDataManager.save_thread_ids(shared_state.thread_ids)

                # Start pagination to fetch all threads
                self._fetch_all_threads_with_pagination(flow)
            else:
                Logger.log("No thread IDs found in smart threads response", "error")

    def _fetch_all_threads_with_pagination(self, flow: http.HTTPFlow) -> None:
        """
        Fetch all threads using pagination.

        Args:
            flow: HTTP flow containing request parameters
        """
        Logger.log("Starting pagination to fetch all threads")

        # Extract parameters from original request
        parsed = urlparse(flow.request.pretty_url)
        query_params = parse_qs(parsed.query)

        # Build base parameters
        base_params = {
            "folder": query_params.get("folder", ["0"])[0],
            "limit": "50",
            "filters": query_params.get("filters", ["{}"])[0],
            "sort": query_params.get("sort", ['{"type":"date","order":"desc"}'])[0],
            "last_modified": query_params.get("last_modified", ["1"])[0],
            "force_custom_thread": query_params.get("force_custom_thread", ["true"])[0],
            "with_thread_representations": query_params.get(
                "with_thread_representations", ["false"]
            )[0],
            "supported_custom_metathreads": query_params.get(
                "supported_custom_metathreads", ['["tomyself"]']
            )[0],
            "remove_emoji_opts": query_params.get(
                "remove_emoji_opts",
                [
                    '{"remove_from_sender_name":true,"remove_from_snippet":true,"remove_from_subject":true}'
                ],
            )[0],
            "email": shared_state.username,
            "htmlencoded": query_params.get("htmlencoded", ["false"])[0],
            "token": shared_state.sota_token,
            "_": str(int(time.time() * 1000)),
        }

        session = SessionManager.create_session(flow)
        all_thread_ids = set(shared_state.thread_ids)
        offset = 50  # Start from offset 50 (first 50 already collected)

        while True:
            params = base_params.copy()
            params["offset"] = str(offset)

            try:
                Logger.log(f"Fetching 50 threads with offset {offset}")
                response = session.get(
                    URL_PATTERNS["smart_threads"],
                    headers=API_HEADERS,
                    params=params,
                    timeout=30,
                )

                if response.status_code != 200:
                    Logger.log(
                        f"Failed to fetch threads at offset {offset}: HTTP {response.status_code}",
                        "error",
                    )
                    break

                data = response.json()
                if not isinstance(data, dict) or data.get("status") != 200:
                    Logger.log(
                        f"Invalid response at offset {offset}: {data.get('status', 'unknown')}",
                        "error",
                    )
                    break

                threads = data.get("body", {}).get("threads", [])
                if not threads:
                    Logger.log(
                        f"No more threads found at offset {offset}, pagination complete"
                    )
                    break

                new_ids = [
                    thread.get("id")
                    for thread in threads
                    if isinstance(thread, dict) and thread.get("id")
                ]

                if not new_ids:
                    Logger.log(
                        f"No valid thread IDs found at offset {offset}, pagination complete"
                    )
                    break

                # Add new IDs
                before_count = len(all_thread_ids)
                all_thread_ids.update(new_ids)
                added = len(all_thread_ids) - before_count

                Logger.log(
                    f"Found {len(new_ids)} threads at offset {offset}, added {added} new (total {len(all_thread_ids)})"
                )

                # Check if we've reached the end
                if len(new_ids) < 50:
                    Logger.log(f"Reached end of threads (got {len(new_ids)} < 50)")
                    break

                offset += 50

            except Exception as e:
                Logger.log(f"Error fetching threads at offset {offset}: {e}", "error")
                break

        # Update thread IDs and save
        shared_state.thread_ids = all_thread_ids
        Logger.log(
            f"Pagination complete. Total threads collected: {len(shared_state.thread_ids)}"
        )
        ThreadDataManager.save_thread_ids(shared_state.thread_ids)

    def get_thread_ids(self) -> List[str]:
        """
        Get the currently collected thread IDs.

        Returns:
            List of thread IDs
        """
        return list(shared_state.thread_ids)
