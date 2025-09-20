"""
Authentication Token Extractor Addon for Mail.ru

Extracts SOTA authentication tokens from Mail.ru inbox HTML responses.
"""

from mitmproxy import http
from shared_utils import (
    URL_PATTERNS,
    Logger,
    DataExtractor,
    shared_state,
    ResponseFilter,
)


class AuthExtractor:
    """
    Addon that extracts SOTA authentication tokens from Mail.ru responses.

    This addon monitors inbox HTML responses and extracts SOTA tokens
    from script tags, storing them for other addons to use.
    """

    def __init__(self):
        """Initialize the authentication extractor."""
        Logger.log("Auth Extractor addon initialized")

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests (no processing needed for token extraction).

        Args:
            flow: HTTP flow to process
        """
        pass

    def response(self, flow: http.HTTPFlow) -> None:
        """
        Handle outgoing responses and extract SOTA tokens from inbox HTML.

        Args:
            flow: HTTP flow to process
        """
        # Only process inbox HTML responses
        if not flow.request.pretty_url.startswith(URL_PATTERNS["inbox"]):
            return

        # Apply response filtering to avoid processing large files
        if not ResponseFilter.should_process_response(flow):
            return

        # Safely get response text with size limits
        html = ResponseFilter.get_response_text_safely(flow)
        if not html:
            Logger.log("Skipping inbox response - too large or invalid", "error")
            return

        Logger.log("Extracting SOTA token from e.mail.ru inbox HTML")
        token = DataExtractor.extract_sota_token_from_html(html)

        if token:
            shared_state.sota_token = token
            Logger.log(f"SOTA token extracted: {shared_state.sota_token}")
        else:
            Logger.log("Could not find script#sota.config in inbox HTML", "error")

    def get_token(self) -> str:
        """
        Get the currently extracted SOTA token.

        Returns:
            SOTA token if available, empty string otherwise
        """
        return shared_state.sota_token
