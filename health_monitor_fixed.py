"""
Health Monitor for Mail.ru Cynosure

Monitors system health and provides recommendations.
Updated for session-based architecture.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List

from shared_utils import Logger
from service_manager import service_manager
from execution_state import execution_state
from session_manager import session_manager
from session_execution_state import session_execution_manager


class HealthMonitor:
    """
    Monitors system health and provides recommendations.

    Updated for session-based architecture - no longer restarts service.
    """

    def __init__(self, health_check_interval: int = 300):
        """
        Initialize the health monitor.

        Args:
            health_check_interval: Interval between health checks in seconds
        """
        self.health_check_interval = health_check_interval
        self.last_health_check = None
        Logger.log("Health Monitor initialized")

    def check_health(self) -> Dict:
        """
        Perform a comprehensive health check.

        Returns:
            Dictionary with health status and recommendations
        """
        self.last_health_check = datetime.now()
        issues = []
        recommendations = []

        # Check service status
        if not service_manager.is_service_running():
            issues.append("Service is not running")
            recommendations.append("Start the service")

        # Check for stuck sessions
        stuck_sessions = self._find_stuck_sessions()
        if stuck_sessions:
            issues.append(f"Found {len(stuck_sessions)} stuck sessions")
            recommendations.append("Review stuck sessions")

        # Check for sessions with too many errors
        error_sessions = self._find_sessions_with_errors()
        if error_sessions:
            issues.append(f"Found {len(error_sessions)} sessions with errors")
            recommendations.append("Review error sessions")

        # Check execution state
        if execution_state.is_rate_limited():
            issues.append("System is rate limited")
            recommendations.append("Wait for rate limit to expire")

        health_status = {
            "timestamp": self.last_health_check.isoformat(),
            "healthy": len(issues) == 0,
            "issues": issues,
            "recommendations": recommendations,
            "active_sessions": len(session_manager.get_active_sessions()),
            "service_running": service_manager.is_service_running(),
        }

        if issues:
            Logger.log(f"Health check found issues: {issues}")
            for rec in recommendations:
                Logger.log(f"Recommendation: {rec}")
        else:
            Logger.log("Health check passed - no issues detected")

        return health_status

    def _find_stuck_sessions(self) -> List[str]:
        """
        Find sessions that appear to be stuck.

        Returns:
            List of stuck session IDs
        """
        stuck_sessions = []
        active_sessions = session_manager.get_active_sessions()

        for session_id, session in active_sessions.items():
            exec_state = session_execution_manager.get_state(session_id)
            if exec_state and exec_state.is_stuck():
                stuck_sessions.append(session_id)

        return stuck_sessions

    def _find_sessions_with_errors(self) -> List[str]:
        """
        Find sessions with too many consecutive errors.

        Returns:
            List of session IDs with errors
        """
        error_sessions = []
        active_sessions = session_manager.get_active_sessions()

        for session_id, session in active_sessions.items():
            exec_state = session_execution_manager.get_state(session_id)
            if exec_state and exec_state.consecutive_errors >= 3:
                error_sessions.append(session_id)

        return error_sessions

    def _is_execution_too_long(self) -> bool:
        """
        Check if execution has been running too long.

        Returns:
            True if execution is too long
        """
        if not execution_state.start_time:
            return False

        max_execution_time = 86400  # 24 hours
        execution_duration = (
            datetime.now() - execution_state.start_time
        ).total_seconds()
        return execution_duration > max_execution_time

    def should_restart_service(self) -> bool:
        """
        Determine if service restart is recommended (legacy method - not used in session-based approach).

        Returns:
            False (service restart not needed in session-based approach)
        """
        # In session-based approach, we don't restart the service
        # Individual sessions handle their own retry logic
        return False

    def get_health_summary(self) -> Dict:
        """
        Get a summary of system health.

        Returns:
            Dictionary with health summary
        """
        return {
            "last_check": (
                self.last_health_check.isoformat() if self.last_health_check else None
            ),
            "check_interval": self.health_check_interval,
            "active_sessions": len(session_manager.get_active_sessions()),
            "service_running": service_manager.is_service_running(),
        }

    def start_monitoring(self) -> None:
        """
        Start the health monitoring loop.

        Updated for session-based architecture - no longer restarts service.
        """
        Logger.log(
            f"Starting health monitoring with {self.health_check_interval}s interval"
        )

        def monitor_loop():
            while True:
                try:
                    self.check_health()

                    # Check health but don't restart service (session-based approach)
                    if self.should_restart_service():
                        Logger.log(
                            "Health issues detected, but service restart not needed in session-based mode"
                        )
                        # In session-based approach, we don't restart the service
                        # Individual sessions handle their own retry logic

                    time.sleep(self.health_check_interval)

                except Exception as e:
                    Logger.log(f"Error in health monitoring: {e}", "error")
                    time.sleep(60)  # Wait 1 minute before retrying

        # Start monitoring in a separate thread
        import threading

        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()


# Global health monitor instance
health_monitor = HealthMonitor()
