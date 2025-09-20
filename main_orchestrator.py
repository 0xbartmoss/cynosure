"""
Main Orchestrator Addon for Mail.ru

Coordinates between all addons and manages the overall flow.
"""

import threading
from typing import Dict
from mitmproxy import http

from shared_utils import Logger, shared_state, FileUtils, DataExtractor
from thread_downloader import ThreadDownloader
from execution_state import execution_state
from error_classifier import ErrorClassifier, RateLimitError, AuthError, ServerError
from service_manager import service_manager
from health_monitor import health_monitor
from config import SESSION_CONFIG, SERVICE_CONFIG
from session_manager import session_manager
from session_execution_state import session_execution_manager


class MainOrchestrator:
    """
    Main orchestrator that coordinates between all addons.

    This addon manages the overall flow, checks when all required data
    is available, and triggers the thread downloading process.
    """

    def __init__(self):
        """Initialize the main orchestrator."""
        Logger.log("Main Orchestrator addon initialized")
        self.thread_downloader = ThreadDownloader()
        self._flow_executed = False

        # Start health monitoring if enabled
        if SERVICE_CONFIG.get("enable_health_monitoring", True):
            health_monitor.start_monitoring(
                SESSION_CONFIG.get("health_check_interval", 300)
            )

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests (no processing needed for orchestration).

        Args:
            flow: HTTP flow to process
        """
        # No processing needed for orchestration

    def response(self, flow: http.HTTPFlow) -> None:
        """
        Handle outgoing responses and check if ready to execute flow.

        Args:
            flow: HTTP flow to process
        """
        # Check if we're ready to execute the main flow
        self._maybe_execute_flow(flow)

    def _maybe_execute_flow(self, flow: http.HTTPFlow) -> None:
        """
        Execute flow if all requirements are met for any ready session.

        Args:
            flow: HTTP flow to process
        """
        # Check for ready sessions that haven't been executed yet
        active_sessions = session_manager.get_active_sessions()

        for session_id, session in active_sessions.items():
            if (
                session.is_ready
                and not session.is_downloading
                and not session.is_completed
            ):
                Logger.log(
                    f"Requirements ready for session {session_id}, executing flow..."
                )
                self._execute_flow_for_session(flow, session)
                break  # Execute one session at a time to avoid conflicts

    def _execute_flow_for_session(self, flow: http.HTTPFlow, session) -> None:
        """
        Execute the main flow to download all thread data for a specific session.

        Args:
            flow: HTTP flow containing cookies and context
            session: UserSession object containing session data
        """
        try:
            Logger.log(f"Starting main execution flow for session {session.session_id}")

            # Check if the flow context matches the session context
            # This prevents executing downloads for one user when another user is active
            flow_email = DataExtractor.extract_email_from_url(flow.request.pretty_url)
            if flow_email and flow_email != session.username:
                Logger.log(
                    f"Skipping execution for session {session.session_id} - flow context ({flow_email}) doesn't match session user ({session.username})",
                    "error",
                )
                return

            # Get or create execution state for this session
            session_exec_state = session_execution_manager.get_or_create_state(
                session.session_id
            )
            session_exec_state.start_execution()

            # Mark session as downloading
            session_manager.mark_downloading(session.session_id)

            # Ensure directories exist
            FileUtils.ensure_directories()

            # Execute thread downloading for this session
            self.thread_downloader.download_all_threads_for_session(flow, session)

            # Mark execution as completed
            session_exec_state.complete_execution()
            session_manager.mark_completed(session.session_id)
            Logger.log(
                f"Main execution flow completed successfully for session {session.session_id}"
            )

            # No service restart - just mark session as completed

        except RateLimitError as e:
            Logger.log(
                f"Rate limit error for session {session.session_id}: {e}", "error"
            )
            session_exec_state = session_execution_manager.get_state(session.session_id)
            if session_exec_state:
                session_exec_state.record_error(
                    ErrorClassifier.classify_error(exception=e), str(e)
                )
            if SERVICE_CONFIG.get("enable_retry_logic", True):
                self._schedule_retry_for_session(session.session_id)

        except AuthError as e:
            Logger.log(
                f"Authentication error for session {session.session_id}: {e}", "error"
            )
            session_exec_state = session_execution_manager.get_state(session.session_id)
            if session_exec_state:
                session_exec_state.record_error(
                    ErrorClassifier.classify_error(exception=e), str(e)
                )
            # Mark session as completed on auth error
            session_manager.mark_completed(session.session_id)

        except ServerError as e:
            Logger.log(f"Server error for session {session.session_id}: {e}", "error")
            session_exec_state = session_execution_manager.get_state(session.session_id)
            if session_exec_state:
                session_exec_state.record_error(
                    ErrorClassifier.classify_error(exception=e), str(e)
                )
            if SERVICE_CONFIG.get("enable_retry_logic", True):
                self._schedule_retry_for_session(session.session_id)

        except Exception as e:
            Logger.log(
                f"Unexpected error in execution flow for session {session.session_id}: {e}",
                "error",
            )
            session_exec_state = session_execution_manager.get_state(session.session_id)
            if session_exec_state:
                session_exec_state.record_error(
                    ErrorClassifier.classify_error(exception=e), str(e)
                )
            if SERVICE_CONFIG.get("enable_retry_logic", True):
                self._schedule_retry_for_session(session.session_id)

    def _execute_flow(self, flow: http.HTTPFlow) -> None:
        """
        Legacy method - kept for backward compatibility.
        Now delegates to session-based execution.

        Args:
            flow: HTTP flow containing cookies and context
        """
        # This method is kept for backward compatibility but now uses session-based approach
        self._maybe_execute_flow(flow)

    def _schedule_retry_for_session(self, session_id: str) -> None:
        """Schedule a retry operation for a specific session."""
        session_exec_state = session_execution_manager.get_state(session_id)
        if not session_exec_state or not session_exec_state.can_retry():
            Logger.log(
                f"Cannot retry session {session_id} - max retries exceeded or rate limited",
                "error",
            )
            return

        session_exec_state.increment_retry_count()
        delay = session_exec_state.get_retry_delay()

        Logger.log(
            f"Scheduling retry {session_exec_state.retry_count} for session {session_id} in {delay} seconds"
        )
        retry_timer = threading.Timer(
            delay, self._retry_execution_for_session, args=[session_id]
        )
        retry_timer.daemon = True
        retry_timer.start()

    def _retry_execution_for_session(self, session_id: str) -> None:
        """Retry the execution flow for a specific session."""
        session = session_manager.get_session(session_id)
        if session and session.is_ready and not session.is_completed:
            Logger.log(f"Retrying execution for session {session_id}")
            # The flow will be triggered again when new requests come in
        else:
            Logger.log(
                f"Cannot retry session {session_id} - session not ready or completed"
            )

    def cancel_timers(self) -> None:
        """Cancel any pending timers (legacy method - no longer needed in session-based approach)."""
        Logger.log("Timer cancellation is not needed in session-based mode")

    def reset(self) -> None:
        """Reset the orchestrator state."""
        self._flow_executed = False
        self.cancel_timers()
        shared_state.reset()
        execution_state.reset()
        Logger.log("Orchestrator state reset")

    def get_status(self) -> Dict[str, any]:
        """
        Get current status of all components.

        Returns:
            Dictionary with status information
        """
        return {
            "global_state": {
                "username": shared_state.username,
                "has_token": bool(shared_state.sota_token),
                "thread_count": len(shared_state.thread_ids),
                "ready": shared_state.is_ready(),
                "flow_executed": self._flow_executed,
            },
            "session_manager": session_manager.get_session_stats(),
            "session_execution_manager": session_execution_manager.get_stats(),
            "legacy_execution_state": execution_state.get_status_summary(),
            "service_status": service_manager.get_service_info(),
            "health_status": health_monitor.get_health_summary(),
        }
