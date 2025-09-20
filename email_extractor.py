"""
Email Extractor Addon for Mail.ru

Extracts user email addresses from Mail.ru API requests.
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
                # Check if we already have a session for this email
                existing_session = session_manager.get_session_by_username(email)
                if existing_session:
                    # Email already extracted for this session, skip
                    return

                Logger.log("Extracting email from e.mail.ru query params")

                # Get or create session for this user FIRST
                session = session_manager.get_or_create_session(email)

                # Update global state only if no other active sessions exist
                # This prevents contamination when multiple users are active
                active_sessions = session_manager.get_active_sessions()
                if len(active_sessions) <= 1:
                    shared_state.username = email
                else:
                    Logger.log(
                        f"Multiple active sessions detected, not updating global state for {email}"
                    )

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

        Returns:
            Email address if available, empty string otherwise
        """
        return shared_state.username
