#!/bin/bash
# Restart script for Cynosure service
# This script can be called by the service to restart itself

SERVICE_NAME="cynosure"
LOG_FILE="/tmp/cynosure_restart.log"

echo "$(date): Attempting to restart $SERVICE_NAME service" >> "$LOG_FILE"

# Try different restart methods
if systemctl restart "$SERVICE_NAME" 2>> "$LOG_FILE"; then
    echo "$(date): Service restarted successfully via systemctl" >> "$LOG_FILE"
    exit 0
fi

# If systemctl fails, try with sudo
if sudo systemctl restart "$SERVICE_NAME" 2>> "$LOG_FILE"; then
    echo "$(date): Service restarted successfully via sudo systemctl" >> "$LOG_FILE"
    exit 0
fi

# If all else fails, send SIGTERM to the process to trigger systemd restart
echo "$(date): systemctl restart failed, sending SIGTERM to trigger restart" >> "$LOG_FILE"
pkill -f "mitmdump.*cynosure" || true
exit 1
