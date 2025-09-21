"""
Email Extractor Addon

Extracts email addresses from API request parameters.
"""

import time
from mitmproxy import http
from shared_utils import URL_PATTERNS, Logger, DataExtractor, shared_state
from session_manager import session_manager


class EmailExtractor:
    """
    Addon that extracts email addresses from Mail.ru API requests.

    This addon monitors xray/batch API calls and extracts the email
    address from query parameters, storing it for other addons to use.
    """

    def __init__(self):
        """Initialize the email extractor."""
        self._processed_emails = set()  # Cache to avoid redundant processing
        self._last_cleanup = time.time()
        Logger.log("Email Extractor addon initialized")

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests and extract email from URL parameters.

        Args:
            flow: HTTP flow to process
        """
        # PERFORMANCE: Early exit for non-matching URLs (avoid string operations)
        url = flow.request.pretty_url
        if not url.startswith(URL_PATTERNS["xray_batch"]):
            return

        # PERFORMANCE: Extract email only once
        email = DataExtractor.extract_email_from_url(url)
        if not email:
            return

        # PERFORMANCE: Check local cache first to avoid database lookups
        current_time = time.time()
        if email in self._processed_emails:
            # Clean cache every 60 seconds to prevent memory leaks
            if current_time - self._last_cleanup > 60:
                self._cleanup_processed_cache()
            return

        # PERFORMANCE: Single optimized session lookup
        session_status = session_manager.get_session_status_for_user(email)
        
        if session_status["has_active"]:
            # Active session exists, add to cache and skip
            self._processed_emails.add(email)
            Logger.log(f"Skipping email extraction - active session exists: {session_status['session_id']} for {email}")
            return

        if session_status["has_recent"]:
            # Recent session exists, add to cache and skip
            self._processed_emails.add(email)
            Logger.log(f"Skipping email extraction - recent session exists: {session_status['session_id']} for {email}")
            return

        # Process new email
        Logger.log("Extracting email from e.mail.ru query params")
        
        # Get or create session for this user
        session = session_manager.get_or_create_session(email)
        
        # Add to processed cache
        self._processed_emails.add(email)

        # CRITICAL FIX: Check for buffered tokens for this user or pending tokens
        buffered_token = session_manager.get_and_clear_buffered_token(email)
        if not buffered_token:
            # Check for generic pending token
            buffered_token = session_manager.get_and_clear_buffered_token("pending_user")
        
        if buffered_token and not session.sota_token:
            session_manager.update_session_token(session.session_id, buffered_token)
            Logger.log(f"Applied buffered token to session {session.session_id} for user {email}")

        # NOTE: Removed all shared_state writes for complete session isolation
        # Each session now maintains its own username independently
        Logger.log(f"Email extracted and assigned to session {session.session_id} - no global state contamination")

        Logger.log(
            f"Email extracted from e.mail.ru: {email} (session: {session.session_id})"
        )

    def response(self, flow: http.HTTPFlow) -> None:
        """
        Handle outgoing responses (no processing needed for email extraction).

        Args:
            flow: HTTP flow to process
        """
        # No processing needed for email extraction in responses

    def _cleanup_processed_cache(self) -> None:
        """Clean up the processed emails cache to prevent memory leaks."""
        # Clear cache every hour to allow reprocessing if needed
        self._processed_emails.clear()
        self._last_cleanup = time.time()
        Logger.log(f"Cleaned up email processing cache ({len(self._processed_emails)} entries)")

    def get_email(self) -> str:
        """
        Get the currently extracted email address.
        
        DEPRECATED: Use session_manager.get_active_sessions() instead for session-specific emails.

        Returns:
            Email address if available, empty string otherwise
        """
        Logger.log("WARNING: get_email() is deprecated. Use session-specific email access instead.", "error")
        return shared_state.username
