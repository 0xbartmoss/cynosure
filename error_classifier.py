"""
Error Classifier for Mail.ru Cynosure

Classifies errors to determine appropriate retry/restart behavior.
"""

from execution_state import ErrorType
from shared_utils import Logger


class RateLimitError(Exception):
    """Exception raised when rate limited."""

    pass


class AuthError(Exception):
    """Exception raised when authentication fails."""

    pass


class ServerError(Exception):
    """Exception raised when server errors occur."""

    pass


class ErrorClassifier:
    """Classifies errors to determine appropriate handling strategy."""

    @staticmethod
    def classify_error(
        response_status: int = None,
        response_text: str = "",
        exception: Exception = None,
    ) -> ErrorType:
        """
        Classify an error based on response status, text, or exception.

        Args:
            response_status: HTTP response status code
            response_text: Response text content
            exception: Exception object

        Returns:
            ErrorType enum value
        """
        # Check response status codes
        if response_status:
            if response_status == 429:  # Too Many Requests
                return ErrorType.TEMPORARY
            elif response_status in [401, 403]:  # Authentication/Authorization issues
                return ErrorType.AUTHENTICATION
            elif response_status >= 500:  # Server errors
                return ErrorType.TEMPORARY
            elif response_status == 404:  # Not found
                return ErrorType.PERMANENT

        # Check response text for specific error patterns
        if response_text:
            response_lower = response_text.lower()

            # Rate limiting indicators
            if any(
                phrase in response_lower
                for phrase in [
                    "rate limit",
                    "too many requests",
                    "quota exceeded",
                    "throttled",
                    "slow down",
                    "try again later",
                ]
            ):
                return ErrorType.TEMPORARY

            # Authentication indicators
            if any(
                phrase in response_lower
                for phrase in [
                    "token expired",
                    "invalid token",
                    "unauthorized",
                    "authentication failed",
                    "login required",
                    "session expired",
                ]
            ):
                return ErrorType.AUTHENTICATION

            # Server error indicators
            if any(
                phrase in response_lower
                for phrase in [
                    "internal server error",
                    "service unavailable",
                    "bad gateway",
                    "timeout",
                    "connection error",
                ]
            ):
                return ErrorType.TEMPORARY

        # Check exception types
        if exception:
            if isinstance(exception, RateLimitError):
                return ErrorType.TEMPORARY
            elif isinstance(exception, AuthError):
                return ErrorType.AUTHENTICATION
            elif isinstance(exception, ServerError):
                return ErrorType.TEMPORARY
            elif isinstance(exception, ConnectionError):
                return ErrorType.TEMPORARY
            elif isinstance(exception, TimeoutError):
                return ErrorType.TEMPORARY

        # Default to unknown if we can't classify
        return ErrorType.UNKNOWN

    @staticmethod
    def create_exception_from_response(
        response_status: int, response_text: str = ""
    ) -> Exception:
        """
        Create appropriate exception from HTTP response.

        Args:
            response_status: HTTP response status code
            response_text: Response text content

        Returns:
            Appropriate exception object
        """
        if response_status == 429:
            return RateLimitError(f"Rate limited: {response_text}")
        elif response_status in [401, 403]:
            return AuthError(f"Authentication failed: {response_text}")
        elif response_status >= 500:
            return ServerError(f"Server error {response_status}: {response_text}")
        else:
            return Exception(f"HTTP {response_status}: {response_text}")

    @staticmethod
    def should_retry_immediately(error_type: ErrorType) -> bool:
        """
        Determine if we should retry immediately or wait.

        Args:
            error_type: Classified error type

        Returns:
            True if should retry immediately, False if should wait
        """
        # Never retry immediately for authentication errors
        if error_type == ErrorType.AUTHENTICATION:
            return False

        # Retry immediately for temporary server errors
        if error_type == ErrorType.TEMPORARY:
            return True

        # Don't retry immediately for permanent errors
        if error_type == ErrorType.PERMANENT:
            return False

        # Unknown errors - be conservative and wait
        return False

    @staticmethod
    def get_retry_delay(error_type: ErrorType, retry_count: int) -> int:
        """
        Get retry delay based on error type and retry count.

        Args:
            error_type: Classified error type
            retry_count: Number of previous retries

        Returns:
            Delay in seconds
        """
        if error_type == ErrorType.TEMPORARY:
            # Exponential backoff for temporary errors
            return min(60 * (2**retry_count), 3600)  # Max 1 hour
        elif error_type == ErrorType.AUTHENTICATION:
            # Longer delay for auth errors
            return 300  # 5 minutes
        elif error_type == ErrorType.PERMANENT:
            # Very long delay for permanent errors
            return 1800  # 30 minutes
        else:
            # Default delay for unknown errors
            return 120  # 2 minutes
