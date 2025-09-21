"""
Service Manager for Cynosure

Handles systemd service status checking and logging.
"""

import shutil
import subprocess
from typing import Dict

from shared_utils import Logger


class ServiceManager:
    """Manages systemd service status operations."""

    def __init__(self, service_name: str = "cynosure"):
        """
        Initialize the service manager.

        Args:
            service_name: Name of the systemd service
        """
        self.service_name = service_name

    def _check_systemd_available(self) -> bool:
        """Check if systemd tools are available."""
        return shutil.which("systemctl") is not None

    def get_service_status(self) -> str:
        """
        Get the current status of the service.

        Returns:
            Service status string
        """
        if not self._check_systemd_available():
            return "unsupported"
            
        try:
            result = subprocess.run(
                ["systemctl", "is-active", self.service_name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
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
        if not shutil.which("journalctl"):
            Logger.log("journalctl not available - cannot retrieve service logs", "error")
            return "Service logs unavailable: journalctl not found (non-systemd environment?)"
            
        try:
            result = subprocess.run(
                ["journalctl", "-u", self.service_name, "-n", str(lines), "--no-pager"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return result.stdout
        except Exception as e:
            Logger.log(f"Failed to get service logs: {e}", "error")
            return ""

    def get_service_info(self) -> Dict:
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
                check=False,
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
