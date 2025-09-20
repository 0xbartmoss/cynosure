"""
Session-based Execution State Manager for Cynosure

Manages execution state per session instead of globally.
"""

import json
import os
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional

from shared_utils import Logger, BASE_DIR
from config import SESSION_CONFIG


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


class SessionExecutionState:
    """Manages execution state for a single session."""

    def __init__(self, session_id: str):
        """Initialize the session execution state."""
        self.session_id = session_id
        self.state_file = f"{BASE_DIR}/execution_state_{session_id}.json"
        self.status = ExecutionStatus.IDLE
        self.start_time = None
        self.completion_time = None
        self.error_count = 0
        self.consecutive_errors = 0
        self.last_error_time = None
        self.last_error_type = None
        self.retry_count = 0
        self.max_retries = SESSION_CONFIG.get("max_retries", 3)
        self.rate_limit_until = None
        self.downloaded_threads = 0
        self.total_threads = 0

        # Load existing state
        self._load_state()

    def _load_state(self) -> None:
        """Load state from file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
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

                Logger.log(
                    f"Loaded execution state for session {self.session_id}: {self.status.value}"
                )
        except Exception as e:
            Logger.log(
                f"Failed to load execution state for session {self.session_id}: {e}",
                "error",
            )
            self._reset_state()

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            data = {
                "session_id": self.session_id,
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
                "last_updated": datetime.now().isoformat(),
            }

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            Logger.log(
                f"Failed to save execution state for session {self.session_id}: {e}",
                "error",
            )

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
        self._save_state()
        Logger.log(f"Started execution for session: {self.session_id}")

    def set_downloading(self, total_threads: int) -> None:
        """Set status to downloading."""
        self.status = ExecutionStatus.DOWNLOADING
        self.total_threads = total_threads
        self._save_state()
        Logger.log(
            f"Started downloading {total_threads} threads for session {self.session_id}"
        )

    def update_progress(self, downloaded: int) -> None:
        """Update download progress."""
        self.downloaded_threads = downloaded
        self._save_state()

        if downloaded % 10 == 0:  # Log every 10 downloads
            Logger.log(
                f"Download progress for session {self.session_id}: {downloaded}/{self.total_threads} threads"
            )

    def complete_execution(self) -> None:
        """Mark execution as completed."""
        self.status = ExecutionStatus.COMPLETED
        self.completion_time = datetime.now().isoformat()
        self.consecutive_errors = 0  # Reset consecutive errors on success
        self._save_state()
        Logger.log(
            f"Execution completed successfully for session {self.session_id}: {self.downloaded_threads}/{self.total_threads} threads downloaded"
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
        Logger.log(
            f"Recorded {error_type.value} error for session {self.session_id}: {error_message}",
            "error",
        )

    def can_retry(self) -> bool:
        """Check if we can retry the current operation."""
        if self.retry_count >= self.max_retries:
            Logger.log(
                f"Max retries ({self.max_retries}) exceeded for session {self.session_id}",
                "error",
            )
            return False

        if self.rate_limit_until:
            try:
                rate_limit_time = datetime.fromisoformat(self.rate_limit_until)
                if datetime.now() < rate_limit_time:
                    Logger.log(
                        f"Session {self.session_id} still rate limited until {self.rate_limit_until}"
                    )
                    return False
                else:
                    # Rate limit expired, clear it
                    self.rate_limit_until = None
                    self._save_state()
            except Exception as e:
                Logger.log(
                    f"Error parsing rate limit time for session {self.session_id}: {e}",
                    "error",
                )
                self.rate_limit_until = None
                self._save_state()

        return True

    def should_restart(self) -> bool:
        """Determine if the session should restart (not applicable for session-based approach)."""
        # In session-based approach, we don't restart the service
        # Instead, we just mark the session as completed
        return False

    def get_restart_delay(self) -> int:
        """Get the delay in seconds before restarting (not applicable for session-based approach)."""
        return 0

    def get_retry_delay(self) -> int:
        """Get the delay in seconds before retrying."""
        # Exponential backoff: base_delay * (2 ^ retry_count)
        base_delay = SESSION_CONFIG.get("retry_delay_base", 60)
        max_delay = SESSION_CONFIG.get("max_retry_delay", 3600)
        delay = min(base_delay * (2**self.retry_count), max_delay)
        return delay

    def increment_retry_count(self) -> None:
        """Increment the retry count."""
        self.retry_count += 1
        self._save_state()

    def get_status_summary(self) -> Dict:
        """Get a summary of the current status."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
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

    def cleanup(self) -> None:
        """Clean up the session execution state."""
        try:
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
            Logger.log(f"Cleaned up execution state for session {self.session_id}")
        except Exception as e:
            Logger.log(
                f"Failed to cleanup execution state for session {self.session_id}: {e}",
                "error",
            )


class SessionExecutionStateManager:
    """Manages execution states for multiple sessions."""

    def __init__(self):
        """Initialize the session execution state manager."""
        self._states: Dict[str, SessionExecutionState] = {}
        self._lock = threading.RLock()

    def get_or_create_state(self, session_id: str) -> SessionExecutionState:
        """Get existing execution state or create a new one for the session."""
        with self._lock:
            if session_id not in self._states:
                self._states[session_id] = SessionExecutionState(session_id)
            return self._states[session_id]

    def get_state(self, session_id: str) -> Optional[SessionExecutionState]:
        """Get execution state for a session."""
        with self._lock:
            return self._states.get(session_id)

    def cleanup_state(self, session_id: str) -> bool:
        """Clean up execution state for a session."""
        with self._lock:
            if session_id in self._states:
                self._states[session_id].cleanup()
                del self._states[session_id]
                return True
            return False

    def get_all_states(self) -> Dict[str, SessionExecutionState]:
        """Get all execution states."""
        with self._lock:
            return self._states.copy()

    def get_stats(self) -> Dict:
        """Get statistics about all execution states."""
        with self._lock:
            states = list(self._states.values())
            return {
                "total_sessions": len(states),
                "by_status": {
                    status.value: len([s for s in states if s.status == status])
                    for status in ExecutionStatus
                },
                "sessions": [state.get_status_summary() for state in states],
            }


# Global session execution state manager instance
session_execution_manager = SessionExecutionStateManager()
