"""
Email Extractor Addon for Cynosure

Extracts user email addresses from API requests.
"""

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
        Logger.log("Email Extractor addon initialized")

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests and extract email from URL parameters.

        Args:
            flow: HTTP flow to process
        """
        # Extract email from e.mail.ru query params
        if flow.request.pretty_url.startswith(URL_PATTERNS["xray_batch"]):
            email = DataExtractor.extract_email_from_url(flow.request.pretty_url)

            if email:
                # Check if we already have an active session for this email
                existing_session = session_manager.get_session_by_username(email)
                if existing_session:
                    # Active session exists, skip email extraction
                    Logger.log(f"Skipping email extraction - active session exists: {existing_session.session_id} for {email}")
                    return

                # Check if we have a recently completed session (within last 30 seconds)
                recent_session = session_manager.get_recent_session_by_username(email, max_age_seconds=30)
                if recent_session:
                    # Recently completed session exists, skip to prevent duplicate sessions
                    Logger.log(f"Skipping email extraction - recent session exists: {recent_session.session_id} for {email} (completed {recent_session.last_activity})")
                    return

                Logger.log("Extracting email from e.mail.ru query params")

                # Get or create session for this user FIRST
                session = session_manager.get_or_create_session(email)

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
            else:
                Logger.log("No email found in xray/batch request", "error")

    def response(self, flow: http.HTTPFlow) -> None:
        """
        Handle outgoing responses (no processing needed for email extraction).

        Args:
            flow: HTTP flow to process
        """
        # No processing needed for email extraction in responses

    def get_email(self) -> str:
        """
        Get the currently extracted email address.
        
        DEPRECATED: Use session_manager.get_active_sessions() instead for session-specific emails.

        Returns:
            Email address if available, empty string otherwise
        """
        Logger.log("WARNING: get_email() is deprecated. Use session-specific email access instead.", "error")
        return shared_state.username
