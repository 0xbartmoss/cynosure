"""
Main Orchestrator Addon for Mail.ru

Coordinates between all addons and manages the overall flow.
"""

import threading
import time
from typing import Dict
from mitmproxy import http

from shared_utils import Logger, shared_state, FileUtils
from thread_downloader import ThreadDownloader
from execution_state import execution_state, ExecutionStatus
from error_classifier import ErrorClassifier, RateLimitError, AuthError, ServerError
from service_manager import service_manager
from health_monitor import health_monitor
from config import RESTART_CONFIG, SERVICE_CONFIG


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
        self.retry_timer = None
        self.restart_timer = None

        # Start health monitoring if enabled
        if SERVICE_CONFIG.get("enable_health_monitoring", True):
            health_monitor.start_monitoring(
                RESTART_CONFIG.get("health_check_interval", 300)
            )

    def request(self, flow: http.HTTPFlow) -> None:
        """
        Handle incoming requests (no processing needed for orchestration).

        Args:
            flow: HTTP flow to process
        """
        pass

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
        Execute flow if all requirements are met.

        Args:
            flow: HTTP flow to process
        """
        if self._flow_executed:
            return

        if shared_state.is_ready():
            Logger.log("Requirements ready, executing flow...")
            self._flow_executed = True
            self._execute_flow(flow)

    def _execute_flow(self, flow: http.HTTPFlow) -> None:
        """
        Execute the main flow to download all thread data.

        Args:
            flow: HTTP flow containing cookies and context
        """
        try:
            Logger.log("Starting main execution flow")
            execution_state.start_execution()

            # Ensure directories exist
            FileUtils.ensure_directories()

            # Execute thread downloading
            self.thread_downloader.download_all_threads(flow)

            # Mark execution as completed
            execution_state.complete_execution()
            Logger.log("Main execution flow completed successfully")

            # Schedule restart on successful completion
            if SERVICE_CONFIG.get("enable_auto_restart", True):
                self._schedule_restart()

        except RateLimitError as e:
            Logger.log(f"Rate limit error: {e}", "error")
            execution_state.record_error(
                ErrorClassifier.classify_error(exception=e), str(e)
            )
            if SERVICE_CONFIG.get("enable_retry_logic", True):
                self._schedule_retry()

        except AuthError as e:
            Logger.log(f"Authentication error: {e}", "error")
            execution_state.record_error(
                ErrorClassifier.classify_error(exception=e), str(e)
            )
            if SERVICE_CONFIG.get("enable_auto_restart", True):
                self._schedule_restart()

        except ServerError as e:
            Logger.log(f"Server error: {e}", "error")
            execution_state.record_error(
                ErrorClassifier.classify_error(exception=e), str(e)
            )
            if SERVICE_CONFIG.get("enable_retry_logic", True):
                self._schedule_retry()

        except Exception as e:
            Logger.log(f"Unexpected error in execution flow: {e}", "error")
            execution_state.record_error(
                ErrorClassifier.classify_error(exception=e), str(e)
            )
            if SERVICE_CONFIG.get("enable_retry_logic", True):
                self._schedule_retry()

    def _schedule_retry(self) -> None:
        """Schedule a retry operation."""
        if not execution_state.can_retry():
            Logger.log("Cannot retry - max retries exceeded or rate limited", "error")
            return

        execution_state.increment_retry_count()
        delay = execution_state.get_retry_delay()

        Logger.log(f"Scheduling retry {execution_state.retry_count} in {delay} seconds")
        self.retry_timer = threading.Timer(delay, self._retry_execution)
        self.retry_timer.start()

    def _retry_execution(self) -> None:
        """Retry the execution flow."""
        Logger.log(f"Retrying execution (attempt {execution_state.retry_count})")
        self._flow_executed = False  # Allow flow to execute again
        # Note: The flow will be triggered again when new requests come in

    def _schedule_restart(self) -> None:
        """Schedule a service restart."""
        delay = execution_state.get_restart_delay()

        if delay == 0:
            Logger.log("Scheduling immediate service restart")
        else:
            Logger.log(f"Scheduling service restart in {delay} seconds")

        self.restart_timer = threading.Timer(delay, self._restart_service)
        self.restart_timer.start()

    def _restart_service(self) -> None:
        """Restart the systemd service."""
        Logger.log("Restarting service due to execution completion or error")
        service_manager.restart_service()

    def cancel_timers(self) -> None:
        """Cancel any pending timers."""
        if self.retry_timer:
            self.retry_timer.cancel()
            self.retry_timer = None
            Logger.log("Cancelled retry timer")

        if self.restart_timer:
            self.restart_timer.cancel()
            self.restart_timer = None
            Logger.log("Cancelled restart timer")

    def reset(self) -> None:
        """Reset the orchestrator state."""
        self._flow_executed = False
        self.cancel_timers()
        shared_state.reset()
        execution_state._reset_state()
        Logger.log("Orchestrator state reset")

    def get_status(self) -> Dict[str, any]:
        """
        Get current status of all components.

        Returns:
            Dictionary with status information
        """
        return {
            "username": shared_state.username,
            "has_token": bool(shared_state.sota_token),
            "thread_count": len(shared_state.thread_ids),
            "ready": shared_state.is_ready(),
            "flow_executed": self._flow_executed,
            "execution_state": execution_state.get_status_summary(),
            "service_status": service_manager.get_service_info(),
            "health_status": health_monitor.get_health_summary(),
        }
