"""
Thread Collector Addon

Collects thread IDs from API responses with pagination support.
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
    ResponseFilter,
    with_retries,
    log_session_request_details,
)
from session_manager import session_manager


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
        # Only process smart threads API responses
        if not flow.request.pretty_url.startswith(URL_PATTERNS["smart_threads"]):
            return

        # Apply JSON response filtering for API responses
        if not ResponseFilter.should_process_json_response(flow):
            return

        # Check if we already have a session with threads collected
        # Find the most recent session that needs thread collection
        active_sessions = session_manager.get_active_sessions()
        sessions_needing_threads = [
            session
            for session in active_sessions.values()
            if not session.thread_ids and not session.is_completed
        ]

        if not sessions_needing_threads:
            # All sessions already have threads collected, skip
            return

        # Safely get JSON response text with size limits
        response_text = ResponseFilter.get_json_response_safely(flow)
        if not response_text:
            Logger.log(
                "Skipping smart threads response - too large or invalid", "error"
            )
            return

        Logger.log("Capturing thread IDs from smart threads list")
        thread_ids = DataExtractor.extract_thread_ids_from_response(response_text)

        if thread_ids:
            # Find the most recent session that needs thread collection
            most_recent_session = max(
                sessions_needing_threads, key=lambda s: s.created_at
            )

            # Add thread IDs to the most recent session
            session_added = session_manager.add_thread_ids(
                most_recent_session.session_id, thread_ids
            )
            Logger.log(
                f"Added {session_added} thread IDs to session {most_recent_session.session_id} (user: {most_recent_session.username})"
            )

            # Reset pagination offset for this session to ensure it starts from the beginning
            session_manager.reset_pagination_offset(most_recent_session.session_id)

            # Note: Global shared_state is deprecated - using session-based state only
            Logger.log(
                f"Collected {len(thread_ids)} thread IDs for session {most_recent_session.session_id}"
            )
            
            # Save thread IDs to file using session data (for backward compatibility)
            ThreadDataManager.save_thread_ids(most_recent_session.thread_ids)

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

        # Find the most recent session that needs pagination
        active_sessions = session_manager.get_active_sessions()
        sessions_needing_threads = [
            session for session in active_sessions.values() if not session.is_completed
        ]

        if not sessions_needing_threads:
            Logger.log("No active sessions found for pagination")
            return

        most_recent_session = max(sessions_needing_threads, key=lambda s: s.created_at)

        if not most_recent_session.sota_token:
            Logger.log(
                f"No SOTA token available for session {most_recent_session.session_id}"
            )
            return

        # Extract parameters from original request
        parsed = urlparse(flow.request.pretty_url)
        query_params = parse_qs(parsed.query)

        # Build base parameters using session-specific data
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
            "email": most_recent_session.username,  # Use session-specific email
            "htmlencoded": query_params.get("htmlencoded", ["false"])[0],
            "token": most_recent_session.sota_token,  # Use session-specific token
            "_": str(int(time.time() * 1000)),
        }

        session = SessionManager.create_session(flow)
        all_thread_ids = set(
            most_recent_session.thread_ids
        )  # Use session-specific thread IDs
        
        # Get session-specific pagination offset instead of hardcoded 50
        offset = session_manager.get_pagination_offset(most_recent_session.session_id)
        Logger.log(f"Starting pagination for session {most_recent_session.session_id} from offset {offset}")

        while True:
            params = base_params.copy()
            params["offset"] = str(offset)

            try:
                Logger.log(f"Fetching 50 threads with offset {offset} for session {most_recent_session.session_id}")
                
                # Log pagination request details
                log_session_request_details(
                    session_id=most_recent_session.session_id,
                    username=most_recent_session.username,
                    sota_token=most_recent_session.sota_token,
                    thread_id=f"pagination_offset_{offset}",
                    params=params,
                    request_type="thread_pagination"
                )

                # Use retry logic for pagination requests
                def fetch_page():
                    response = session.get(
                        URL_PATTERNS["smart_threads"],
                        headers=API_HEADERS,
                        params=params,
                        timeout=30,
                    )
                    
                    if response.status_code != 200:
                        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
                    
                    data = response.json()
                    if not isinstance(data, dict) or data.get("status") != 200:
                        raise Exception(f"Invalid API response status: {data.get('status', 'unknown')}")
                    
                    return data
                
                # Retry with exponential backoff
                data = with_retries(
                    fetch_page,
                    attempts=3,
                    delay_base=2.0,
                    delay_multiplier=2.0,
                    max_delay=30.0,
                    exceptions=(Exception,),
                    on_error=lambda e, attempt: Logger.log(
                        f"Pagination attempt {attempt} failed at offset {offset} for session {most_recent_session.session_id}: {e}", "error"
                    )
                )

                threads = data.get("body", {}).get("threads", [])
                if not threads:
                    Logger.log(
                        f"No more threads found at offset {offset} for session {most_recent_session.session_id}, pagination complete"
                    )
                    break

                new_ids = [
                    thread.get("id")
                    for thread in threads
                    if isinstance(thread, dict) and thread.get("id")
                ]

                if not new_ids:
                    Logger.log(
                        f"No valid thread IDs found at offset {offset} for session {most_recent_session.session_id}, pagination complete"
                    )
                    break

                # Add new IDs
                before_count = len(all_thread_ids)
                all_thread_ids.update(new_ids)
                added = len(all_thread_ids) - before_count

                Logger.log(
                    f"Found {len(new_ids)} threads at offset {offset} for session {most_recent_session.session_id}, added {added} new (total {len(all_thread_ids)})"
                )

                # Check if we've reached the end
                if len(new_ids) < 50:
                    Logger.log(f"Reached end of threads for session {most_recent_session.session_id} (got {len(new_ids)} < 50)")
                    break

                # Update session-specific offset for next iteration
                offset += 50
                session_manager.update_pagination_offset(most_recent_session.session_id, offset)

            except Exception as e:
                Logger.log(f"All retry attempts failed for offset {offset} in session {most_recent_session.session_id}: {e}", "error")
                # Continue with next offset instead of breaking entirely
                Logger.log(f"Skipping offset {offset} for session {most_recent_session.session_id}, continuing with next batch...")
                offset += 50
                session_manager.update_pagination_offset(most_recent_session.session_id, offset)
                continue

        # Update session with all collected thread IDs
        session_manager.add_thread_ids(most_recent_session.session_id, all_thread_ids)
        Logger.log(
            f"Pagination complete for session {most_recent_session.session_id}. Total threads collected: {len(all_thread_ids)}"
        )

        # Save thread IDs to file using session data (for backward compatibility)
        ThreadDataManager.save_thread_ids(all_thread_ids)

    def get_thread_ids(self) -> List[str]:
        """
        Get the currently collected thread IDs.

        Returns:
            List of thread IDs
        """
        return list(shared_state.thread_ids)
