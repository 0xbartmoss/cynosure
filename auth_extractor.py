"""
Authentication Token Extractor Addon for Mail.ru

Extracts SOTA authentication tokens from Mail.ru inbox HTML responses.
"""

from mitmproxy import http
from shared_utils import URL_PATTERNS, Logger, DataExtractor, shared_state


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
        # Extract SOTA token from inbox HTML
        if flow.request.pretty_url.startswith(URL_PATTERNS["inbox"]):
            Logger.log("Extracting SOTA token from e.mail.ru inbox HTML")
            html = flow.response.get_text()
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
