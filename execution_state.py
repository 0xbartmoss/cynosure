"""
Execution State Manager for Mail.ru Cynosure

Manages execution state, error tracking, and restart decisions.
"""

import json
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

from shared_utils import Logger, BASE_DIR


class ExecutionStatus(Enum):
    """Execution status enumeration."""

    IDLE = "idle"
    COLLECTING = "collecting"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILED = "auth_failed"


class ErrorType(Enum):
    """Error type enumeration."""

    TEMPORARY = "temporary"  # Rate limiting, network issues
    AUTHENTICATION = "authentication"  # Token expired, login required
    PERMANENT = "permanent"  # Server errors, API changes
    UNKNOWN = "unknown"


class ExecutionStateManager:
    """
    Manages execution state, error tracking, and restart decisions.
    """

    def __init__(self):
        """Initialize the execution state manager."""
        self.state_file = f"{BASE_DIR}/execution_state.json"
        self.status = ExecutionStatus.IDLE
        self.start_time = None
        self.completion_time = None
        self.error_count = 0
        self.consecutive_errors = 0
        self.last_error_time = None
        self.last_error_type = None
        self.retry_count = 0
        self.max_retries = 3
        self.rate_limit_until = None
        self.downloaded_threads = 0
        self.total_threads = 0
        self.session_id = None

        # Load existing state
        self._load_state()

    def _load_state(self) -> None:
        """Load state from file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self.status = ExecutionStatus(data.get("status", "idle"))
                    self.start_time = data.get("start_time")
                    self.completion_time = data.get("completion_time")
                    self.error_count = data.get("error_count", 0)
                    self.consecutive_errors = data.get("consecutive_errors", 0)
                    self.last_error_time = data.get("last_error_time")
                    self.last_error_type = data.get("last_error_type")
                    self.retry_count = data.get("retry_count", 0)
                    self.rate_limit_until = data.get("rate_limit_until")
                    self.downloaded_threads = data.get("downloaded_threads", 0)
                    self.total_threads = data.get("total_threads", 0)
                    self.session_id = data.get("session_id")

                Logger.log(f"Loaded execution state: {self.status.value}")
        except Exception as e:
            Logger.log(f"Failed to load execution state: {e}", "error")
            self._reset_state()

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            data = {
                "status": self.status.value,
                "start_time": self.start_time,
                "completion_time": self.completion_time,
                "error_count": self.error_count,
                "consecutive_errors": self.consecutive_errors,
                "last_error_time": self.last_error_time,
                "last_error_type": self.last_error_type,
                "retry_count": self.retry_count,
                "rate_limit_until": self.rate_limit_until,
                "downloaded_threads": self.downloaded_threads,
                "total_threads": self.total_threads,
                "session_id": self.session_id,
                "last_updated": datetime.now().isoformat(),
            }

            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            Logger.log(f"Failed to save execution state: {e}", "error")

    def _reset_state(self) -> None:
        """Reset state to initial values."""
        self.status = ExecutionStatus.IDLE
        self.start_time = None
        self.completion_time = None
        self.error_count = 0
        self.consecutive_errors = 0
        self.last_error_time = None
        self.last_error_type = None
        self.retry_count = 0
        self.rate_limit_until = None
        self.downloaded_threads = 0
        self.total_threads = 0
        self.session_id = f"session_{int(time.time())}"
        self._save_state()

    def start_execution(self) -> None:
        """Start a new execution session."""
        self.status = ExecutionStatus.COLLECTING
        self.start_time = datetime.now().isoformat()
        self.completion_time = None
        self.error_count = 0
        self.consecutive_errors = 0
        self.last_error_time = None
        self.last_error_type = None
        self.retry_count = 0
        self.rate_limit_until = None
        self.downloaded_threads = 0
        self.total_threads = 0
        self.session_id = f"session_{int(time.time())}"
        self._save_state()
        Logger.log(f"Started execution session: {self.session_id}")

    def set_downloading(self, total_threads: int) -> None:
        """Set status to downloading."""
        self.status = ExecutionStatus.DOWNLOADING
        self.total_threads = total_threads
        self._save_state()
        Logger.log(f"Started downloading {total_threads} threads")

    def update_progress(self, downloaded: int) -> None:
        """Update download progress."""
        self.downloaded_threads = downloaded
        self._save_state()

        if downloaded % 10 == 0:  # Log every 10 downloads
            Logger.log(f"Download progress: {downloaded}/{self.total_threads} threads")

    def complete_execution(self) -> None:
        """Mark execution as completed."""
        self.status = ExecutionStatus.COMPLETED
        self.completion_time = datetime.now().isoformat()
        self.consecutive_errors = 0  # Reset consecutive errors on success
        self._save_state()
        Logger.log(
            f"Execution completed successfully: {self.downloaded_threads}/{self.total_threads} threads downloaded"
        )

    def record_error(self, error_type: ErrorType, error_message: str = "") -> None:
        """Record an error and update state."""
        self.error_count += 1
        self.consecutive_errors += 1
        self.last_error_time = datetime.now().isoformat()
        self.last_error_type = error_type.value

        if error_type == ErrorType.TEMPORARY:
            self.status = ExecutionStatus.RATE_LIMITED
            # Set rate limit for 5 minutes
            self.rate_limit_until = (datetime.now() + timedelta(minutes=5)).isoformat()
        elif error_type == ErrorType.AUTHENTICATION:
            self.status = ExecutionStatus.AUTH_FAILED
        else:
            self.status = ExecutionStatus.ERROR

        self._save_state()
        Logger.log(f"Recorded {error_type.value} error: {error_message}", "error")

    def can_retry(self) -> bool:
        """Check if we can retry the current operation."""
        if self.retry_count >= self.max_retries:
            Logger.log(f"Max retries ({self.max_retries}) exceeded", "error")
            return False

        if self.rate_limit_until:
            try:
                rate_limit_time = datetime.fromisoformat(self.rate_limit_until)
                if datetime.now() < rate_limit_time:
                    Logger.log(f"Still rate limited until {self.rate_limit_until}")
                    return False
                else:
                    # Rate limit expired, clear it
                    self.rate_limit_until = None
                    self._save_state()
            except Exception as e:
                Logger.log(f"Error parsing rate limit time: {e}", "error")
                self.rate_limit_until = None
                self._save_state()

        return True

    def should_restart(self) -> bool:
        """Determine if the service should restart."""
        # Always restart on successful completion
        if self.status == ExecutionStatus.COMPLETED:
            Logger.log("Execution completed successfully, restart recommended")
            return True

        # Restart on authentication failures
        if self.status == ExecutionStatus.AUTH_FAILED:
            Logger.log("Authentication failed, restart recommended")
            return True

        # Restart if too many consecutive errors
        if self.consecutive_errors >= 5:
            Logger.log(
                f"Too many consecutive errors ({self.consecutive_errors}), restart recommended"
            )
            return True

        # Restart if execution has been running too long (24 hours)
        if self.start_time:
            try:
                start_time = datetime.fromisoformat(self.start_time)
                if datetime.now() - start_time > timedelta(hours=24):
                    Logger.log("Execution running too long, restart recommended")
                    return True
            except Exception as e:
                Logger.log(f"Error parsing start time: {e}", "error")

        return False

    def get_restart_delay(self) -> int:
        """Get the delay in seconds before restarting."""
        if self.status == ExecutionStatus.COMPLETED:
            return 0  # Immediate restart on success

        if self.status == ExecutionStatus.AUTH_FAILED:
            return 300  # 5 minutes for auth failures

        if self.consecutive_errors >= 5:
            return 600  # 10 minutes for too many errors

        return 60  # 1 minute default delay

    def get_retry_delay(self) -> int:
        """Get the delay in seconds before retrying."""
        # Exponential backoff: base_delay * (2 ^ retry_count)
        base_delay = 60  # 1 minute base
        max_delay = 3600  # 1 hour max
        delay = min(base_delay * (2**self.retry_count), max_delay)
        return delay

    def increment_retry_count(self) -> None:
        """Increment the retry count."""
        self.retry_count += 1
        self._save_state()

    def get_status_summary(self) -> Dict:
        """Get a summary of the current status."""
        return {
            "status": self.status.value,
            "session_id": self.session_id,
            "start_time": self.start_time,
            "completion_time": self.completion_time,
            "error_count": self.error_count,
            "consecutive_errors": self.consecutive_errors,
            "last_error_type": self.last_error_type,
            "retry_count": self.retry_count,
            "downloaded_threads": self.downloaded_threads,
            "total_threads": self.total_threads,
            "rate_limited": bool(self.rate_limit_until),
            "can_retry": self.can_retry(),
            "should_restart": self.should_restart(),
            "restart_delay": self.get_restart_delay(),
            "retry_delay": self.get_retry_delay(),
        }


# Global execution state manager instance
execution_state = ExecutionStateManager()
