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
from session_manager import session_manager


class AuthExtractor:
    """
    Addon that extracts SOTA tokens from Mail.ru responses.

    This addon monitors inbox HTML responses, extracts SOTA tokens,
    and stores them for authentication in subsequent requests.
    """

    def __init__(self):
        """Initialize the auth extractor."""
        Logger.log("Auth Extractor addon initialized")

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests (no processing needed for token extraction).

        Args:
            flow: HTTP flow to process
        """

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
            # CRITICAL FIX: Extract email from current flow to identify correct user
            flow_email = DataExtractor.extract_email_from_url(flow.request.pretty_url)
            
            if flow_email:
                # Create or get session for the user from this specific flow
                target_session = session_manager.get_or_create_session(flow_email)
                
                # Assign token to the correct user's session
                session_manager.update_session_token(target_session.session_id, token)
                Logger.log(
                    f"SOTA token extracted and assigned to correct user: {token} "
                    f"(session: {target_session.session_id}, user: {target_session.username})"
                )
                Logger.log(f"Token assigned via flow-based identification - no race condition")
            else:
                # Fallback: Try to find existing sessions that need tokens
                Logger.log("No email in flow context, falling back to session matching")
                active_sessions = session_manager.get_active_sessions()
                sessions_needing_tokens = [
                    session
                    for session in active_sessions.values()
                    if not session.sota_token and not session.is_completed
                ]

                if sessions_needing_tokens:
                    # Sort by creation time to get the most recent session
                    most_recent_session = max(
                        sessions_needing_tokens, key=lambda s: s.created_at
                    )
                    
                    session_manager.update_session_token(
                        most_recent_session.session_id, token
                    )
                    Logger.log(
                        f"SOTA token assigned to most recent session: {token} "
                        f"(session: {most_recent_session.session_id}, user: {most_recent_session.username})"
                    )
                    Logger.log("WARNING: Used fallback session assignment - potential race condition")
                else:
                    # Buffer the token for future session creation
                    Logger.log(f"SOTA token extracted but no sessions exist: {token}")
                    Logger.log("Token will be buffered for next session creation")
                    # Store in session manager's buffer with a generic key
                    session_manager.buffer_token_for_user("pending_user", token)
        else:
            Logger.log("Could not find script#sota.config in inbox HTML", "error")

    def get_token(self) -> str:
        """
        Get the currently extracted SOTA token.
        
        DEPRECATED: Use session_manager.get_session_by_username() instead for session-specific tokens.

        Returns:
            SOTA token if available, empty string otherwise
        """
        Logger.log("WARNING: get_token() is deprecated. Use session-specific token access instead.", "error")
        return shared_state.sota_token
