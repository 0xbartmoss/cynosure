"""
Email Extractor Addon for Mail.ru

Extracts user email addresses from Mail.ru API requests.
"""

from mitmproxy import http
from shared_utils import URL_PATTERNS, Logger, DataExtractor, shared_state


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
            Logger.log("Extracting email from e.mail.ru query params")
            email = DataExtractor.extract_email_from_url(flow.request.pretty_url)

            if email:
                shared_state.username = email
                Logger.log(f"Email extracted from e.mail.ru: {shared_state.username}")
            else:
                Logger.log("No email found in xray/batch request", "error")

    def response(self, flow: http.HTTPFlow) -> None:
        """
        Handle outgoing responses (no processing needed for email extraction).

        Args:
            flow: HTTP flow to process
        """
        pass

    def get_email(self) -> str:
        """
        Get the currently extracted email address.

        Returns:
            Email address if available, empty string otherwise
        """
        return shared_state.username
