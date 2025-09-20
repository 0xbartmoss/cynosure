"""
Health Monitor for Cynosure

Monitors system health and detects stuck executions.
"""

import time
from datetime import datetime, timedelta
from typing import Dict

from execution_state import execution_state, ExecutionStatus
from service_manager import service_manager
from shared_utils import Logger


class HealthMonitor:
    """Monitors system health and detects issues."""

    def __init__(self):
        """Initialize the health monitor."""
        self.last_health_check = None
        self.health_check_interval = 300  # 5 minutes
        self.stuck_threshold = 1800  # 30 minutes without progress
        self.max_execution_time = 86400  # 24 hours

    def check_health(self) -> Dict:
        """
        Perform a comprehensive health check.

        Returns:
            Dictionary with health status information
        """
        self.last_health_check = datetime.now()

        health_status = {
            "timestamp": self.last_health_check.isoformat(),
            "execution_status": execution_state.get_status_summary(),
            "service_status": service_manager.get_service_info(),
            "issues": [],
            "recommendations": [],
        }

        # Check for stuck execution
        if self._is_execution_stuck():
            health_status["issues"].append("Execution appears stuck")
            health_status["recommendations"].append("Consider restarting service")

        # Check for long-running execution
        if self._is_execution_too_long():
            health_status["issues"].append("Execution running too long")
            health_status["recommendations"].append("Consider restarting service")

        # Check for too many errors
        if execution_state.consecutive_errors >= 5:
            health_status["issues"].append("Too many consecutive errors")
            health_status["recommendations"].append("Restart service to reset state")

        # Check service status
        if not service_manager.is_service_running():
            health_status["issues"].append("Service is not running")
            health_status["recommendations"].append("Start the service")

        # Log health status
        if health_status["issues"]:
            Logger.log(f"Health check found issues: {health_status['issues']}", "error")
            for recommendation in health_status["recommendations"]:
                Logger.log(f"Recommendation: {recommendation}")
        else:
            Logger.log("Health check passed - no issues detected")

        return health_status

    def _is_execution_stuck(self) -> bool:
        """
        Check if execution appears to be stuck.

        Returns:
            True if execution appears stuck
        """
        if execution_state.status not in [
            ExecutionStatus.DOWNLOADING,
            ExecutionStatus.COLLECTING,
        ]:
            return False

        # Check if we've been in the same state for too long without progress
        if execution_state.last_error_time:
            try:
                last_error = datetime.fromisoformat(execution_state.last_error_time)
                if datetime.now() - last_error > timedelta(
                    seconds=self.stuck_threshold
                ):
                    return True
            except Exception as e:
                Logger.log(f"Error parsing last error time: {e}", "error")

        # Check if we've been downloading for too long without progress
        if execution_state.status == ExecutionStatus.DOWNLOADING:
            if (
                execution_state.downloaded_threads == 0
                and execution_state.total_threads > 0
            ):
                # Started downloading but no progress
                if execution_state.start_time:
                    try:
                        start_time = datetime.fromisoformat(execution_state.start_time)
                        if datetime.now() - start_time > timedelta(
                            seconds=self.stuck_threshold
                        ):
                            return True
                    except Exception as e:
                        Logger.log(f"Error parsing start time: {e}", "error")

        return False

    def _is_execution_too_long(self) -> bool:
        """
        Check if execution has been running too long.

        Returns:
            True if execution is too long
        """
        if not execution_state.start_time:
            return False

        try:
            start_time = datetime.fromisoformat(execution_state.start_time)
            execution_duration = datetime.now() - start_time

            if execution_duration > timedelta(seconds=self.max_execution_time):
                Logger.log(f"Execution running too long: {execution_duration}")
                return True
        except Exception as e:
            Logger.log(f"Error parsing start time: {e}", "error")

        return False

    def should_restart_service(self) -> bool:
        """
        Determine if the service should be restarted based on health check.

        Returns:
            True if service should be restarted
        """
        # Check if execution is stuck
        if self._is_execution_stuck():
            Logger.log("Execution is stuck, restart recommended")
            return True

        # Check if execution is too long
        if self._is_execution_too_long():
            Logger.log("Execution is too long, restart recommended")
            return True

        # Check if service is not running
        if not service_manager.is_service_running():
            Logger.log("Service is not running, restart recommended")
            return True

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
            "execution_stuck": self._is_execution_stuck(),
            "execution_too_long": self._is_execution_too_long(),
            "service_running": service_manager.is_service_running(),
            "should_restart": self.should_restart_service(),
            "execution_state": execution_state.get_status_summary(),
        }

    def start_monitoring(self, interval: int = None) -> None:
        """
        Start continuous health monitoring.

        Args:
            interval: Monitoring interval in seconds
        """
        if interval:
            self.health_check_interval = interval

        Logger.log(
            f"Starting health monitoring with {self.health_check_interval}s interval"
        )

        def monitor_loop():
            while True:
                try:
                    self.check_health()

                    # If health check recommends restart, do it
                    if self.should_restart_service():
                        Logger.log("Health monitor recommends service restart")
                        service_manager.restart_service(delay=60)  # 1 minute delay
                        break  # Exit monitoring loop after restart

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
