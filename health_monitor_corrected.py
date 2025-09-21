"""
DEPRECATED: This file is deprecated. Use health_monitor.py instead.

This file is kept for backward compatibility only.
All functionality has been moved to the canonical health_monitor.py.
"""

# Re-export from canonical health monitor
from health_monitor import HealthMonitor, health_monitor

# Deprecated warning
import warnings
warnings.warn(
    "health_monitor_corrected.py is deprecated. Use health_monitor.py instead.",
    DeprecationWarning,
    stacklevel=2
)
