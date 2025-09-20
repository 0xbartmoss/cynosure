"""
Service Manager for Mail.ru Cynosure

Handles systemd service operations and restart logic.
"""

import subprocess
import threading
import time
from typing import Optional

from shared_utils import Logger


class ServiceManager:
    """Manages systemd service operations."""

    def __init__(self, service_name: str = "cynosure"):
        """
        Initialize the service manager.

        Args:
            service_name: Name of the systemd service
        """
        self.service_name = service_name
        self.restart_timer: Optional[threading.Timer] = None
        self.retry_timer: Optional[threading.Timer] = None

    def restart_service(self, delay: int = 0) -> None:
        """
        Restart the systemd service.

        Args:
            delay: Delay in seconds before restarting
        """
        if delay > 0:
            Logger.log(f"Scheduling service restart in {delay} seconds")
            self.restart_timer = threading.Timer(delay, self._do_restart)
            self.restart_timer.start()
        else:
            self._do_restart()

    def _do_restart(self) -> None:
        """Actually perform the service restart."""
        try:
            Logger.log(f"Restarting service: {self.service_name}")
            result = subprocess.run(
                ["systemctl", "restart", self.service_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                Logger.log("Service restarted successfully")
            else:
                Logger.log(f"Failed to restart service: {result.stderr}", "error")

        except subprocess.TimeoutExpired:
            Logger.log("Service restart timed out", "error")
        except subprocess.CalledProcessError as e:
            Logger.log(
                f"Service restart failed with return code {e.returncode}: {e.stderr}",
                "error",
            )
        except Exception as e:
            Logger.log(f"Unexpected error during service restart: {e}", "error")

    def get_service_status(self) -> str:
        """
        Get the current status of the service.

        Returns:
            Service status string
        """
        try:
            result = subprocess.run(
                ["systemctl", "is-active", self.service_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except Exception as e:
            Logger.log(f"Failed to get service status: {e}", "error")
            return "unknown"

    def is_service_running(self) -> bool:
        """
        Check if the service is currently running.

        Returns:
            True if service is active, False otherwise
        """
        status = self.get_service_status()
        return status == "active"

    def get_service_logs(self, lines: int = 50) -> str:
        """
        Get recent service logs.

        Args:
            lines: Number of log lines to retrieve

        Returns:
            Service logs as string
        """
        try:
            result = subprocess.run(
                ["journalctl", "-u", self.service_name, "-n", str(lines), "--no-pager"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout
        except Exception as e:
            Logger.log(f"Failed to get service logs: {e}", "error")
            return ""

    def schedule_retry(self, delay: int, retry_function) -> None:
        """
        Schedule a retry operation.

        Args:
            delay: Delay in seconds before retrying
            retry_function: Function to call for retry
        """
        Logger.log(f"Scheduling retry in {delay} seconds")
        self.retry_timer = threading.Timer(delay, retry_function)
        self.retry_timer.start()

    def cancel_timers(self) -> None:
        """Cancel any pending timers."""
        if self.restart_timer:
            self.restart_timer.cancel()
            self.restart_timer = None
            Logger.log("Cancelled restart timer")

        if self.retry_timer:
            self.retry_timer.cancel()
            self.retry_timer = None
            Logger.log("Cancelled retry timer")

    def get_service_info(self) -> dict:
        """
        Get comprehensive service information.

        Returns:
            Dictionary with service information
        """
        try:
            # Get service status
            status = self.get_service_status()

            # Get service properties
            result = subprocess.run(
                [
                    "systemctl",
                    "show",
                    self.service_name,
                    "--property=ActiveState,SubState,LoadState,UnitFileState",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            properties = {}
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        properties[key] = value

            return {
                "status": status,
                "properties": properties,
                "is_running": self.is_service_running(),
            }

        except Exception as e:
            Logger.log(f"Failed to get service info: {e}", "error")
            return {"status": "unknown", "properties": {}, "is_running": False}


# Global service manager instance
service_manager = ServiceManager()
