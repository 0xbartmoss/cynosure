"""
Session Manager for Cynosure

Manages multiple concurrent user sessions for processing different users simultaneously.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
from dataclasses import dataclass, field

from shared_utils import Logger
from config import SESSION_CONFIG


@dataclass
class UserSession:
    """Represents a user session with all necessary data."""

    session_id: str
    username: str
    sota_token: str
    thread_ids: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    is_ready: bool = False
    is_downloading: bool = False
    is_completed: bool = False
    download_progress: int = 0
    total_threads: int = 0

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now()

    def is_expired(self, max_age_hours: int = None) -> bool:
        """Check if the session has expired."""
        if max_age_hours is None:
            max_age_hours = SESSION_CONFIG.get("session_max_age_hours", 24)
        return datetime.now() - self.created_at > timedelta(hours=max_age_hours)

    def is_stale(self, max_idle_minutes: int = None) -> bool:
        """Check if the session has been idle too long."""
        if max_idle_minutes is None:
            max_idle_minutes = SESSION_CONFIG.get("session_max_idle_minutes", 30)
        return datetime.now() - self.last_activity > timedelta(minutes=max_idle_minutes)


class SessionManager:
    """Manages multiple concurrent user sessions."""

    def __init__(self):
        """Initialize the session manager."""
        self._sessions: Dict[str, UserSession] = {}
        self._lock = threading.RLock()
        self._cleanup_timer: Optional[threading.Timer] = None
        self._start_cleanup_timer()

    def _start_cleanup_timer(self) -> None:
        """Start the cleanup timer for expired sessions."""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()

        # Run cleanup every 5 minutes
        self._cleanup_timer = threading.Timer(300, self._cleanup_expired_sessions)
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired and stale sessions."""
        with self._lock:
            expired_sessions = []
            for session_id, session in self._sessions.items():
                if session.is_expired() or session.is_stale():
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                del self._sessions[session_id]
                Logger.log(f"Cleaned up expired session: {session_id}")

        # Restart the cleanup timer
        self._start_cleanup_timer()

    def get_or_create_session(self, username: str) -> UserSession:
        """Get existing session or create a new one for the username."""
        with self._lock:
            # Look for existing active session for this user
            for session in self._sessions.values():
                if (
                    session.username == username
                    and not session.is_completed
                    and not session.is_expired()
                ):
                    session.update_activity()
                    Logger.log(
                        f"Reusing existing session for {username}: {session.session_id}"
                    )
                    return session

            # Create new session
            session_id = f"session_{username}_{int(time.time())}"
            session = UserSession(
                session_id=session_id,
                username=username,
                sota_token="",
            )
            self._sessions[session_id] = session
            Logger.log(f"Created new session for {username}: {session_id}")
            return session

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.update_activity()
            return session

    def get_session_by_username(self, username: str) -> Optional[UserSession]:
        """Get the most recent active session for a username."""
        with self._lock:
            active_sessions = [
                session
                for session in self._sessions.values()
                if session.username == username
                and not session.is_completed
                and not session.is_expired()
            ]
            if active_sessions:
                # Return the most recent one
                session = max(active_sessions, key=lambda s: s.last_activity)
                session.update_activity()
                return session
            return None

    def update_session_token(self, session_id: str, token: str) -> bool:
        """Update the SOTA token for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.sota_token = token
                session.update_activity()
                session.is_ready = bool(
                    session.username and session.sota_token and session.thread_ids
                )
                Logger.log(f"Updated token for session {session_id}")
                return True
            return False

    def add_thread_ids(self, session_id: str, thread_ids: Set[str]) -> int:
        """Add thread IDs to a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                before_count = len(session.thread_ids)
                session.thread_ids.update(thread_ids)
                added = len(session.thread_ids) - before_count
                session.update_activity()
                session.is_ready = bool(
                    session.username and session.sota_token and session.thread_ids
                )
                Logger.log(
                    f"Added {added} thread IDs to session {session_id} (total: {len(session.thread_ids)})"
                )
                return added
            return 0

    def mark_downloading(self, session_id: str) -> bool:
        """Mark a session as downloading."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_ready:
                session.is_downloading = True
                session.total_threads = len(session.thread_ids)
                session.download_progress = 0
                session.update_activity()
                Logger.log(
                    f"Marked session {session_id} as downloading ({session.total_threads} threads)"
                )
                return True
            return False

    def update_download_progress(self, session_id: str, progress: int) -> bool:
        """Update download progress for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.is_downloading:
                session.download_progress = progress
                session.update_activity()
                return True
            return False

    def mark_completed(self, session_id: str) -> bool:
        """Mark a session as completed."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.is_completed = True
                session.is_downloading = False
                session.update_activity()
                Logger.log(f"Marked session {session_id} as completed")
                return True
            return False

    def get_active_sessions(self) -> Dict[str, UserSession]:
        """Get all active (non-completed, non-expired) sessions."""
        with self._lock:
            return {
                session_id: session
                for session_id, session in self._sessions.items()
                if not session.is_completed and not session.is_expired()
            }

    def get_session_stats(self) -> Dict:
        """Get statistics about current sessions."""
        with self._lock:
            active_sessions = self.get_active_sessions()
            downloading_sessions = [
                s for s in active_sessions.values() if s.is_downloading
            ]
            ready_sessions = [
                s
                for s in active_sessions.values()
                if s.is_ready and not s.is_downloading
            ]

            return {
                "total_sessions": len(self._sessions),
                "active_sessions": len(active_sessions),
                "downloading_sessions": len(downloading_sessions),
                "ready_sessions": len(ready_sessions),
                "completed_sessions": len(
                    [s for s in self._sessions.values() if s.is_completed]
                ),
                "sessions": [
                    {
                        "session_id": session.session_id,
                        "username": session.username,
                        "is_ready": session.is_ready,
                        "is_downloading": session.is_downloading,
                        "is_completed": session.is_completed,
                        "thread_count": len(session.thread_ids),
                        "progress": (
                            f"{session.download_progress}/{session.total_threads}"
                            if session.is_downloading
                            else "N/A"
                        ),
                        "created_at": session.created_at.isoformat(),
                        "last_activity": session.last_activity.isoformat(),
                    }
                    for session in active_sessions.values()
                ],
            }

    def cleanup_session(self, session_id: str) -> bool:
        """Manually cleanup a specific session."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                Logger.log(f"Manually cleaned up session: {session_id}")
                return True
            return False


# Global session manager instance
session_manager = SessionManager()
