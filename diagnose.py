#!/usr/bin/env python3
"""Quick diagnostic script for Cynosure thread download issues."""

from service_manager import service_manager
from shared_utils import log_system_status
import sys

def main():
    print("=" * 60)
    print("CYNOSURE DIAGNOSTIC REPORT")
    print("=" * 60)
    
    # Check service status
    print("\n1. SERVICE STATUS:")
    service_info = service_manager.get_service_info()
    print(f"   Status: {service_info['status']}")
    print(f"   Running: {service_info['is_running']}")
    print(f"   Properties: {service_info['properties']}")
    
    # Get recent logs
    print("\n2. RECENT LOGS (last 30 lines):")
    logs = service_manager.get_service_logs(30)
    if logs:
        print(logs)
    else:
        print("   No logs available")
    
    # Show system status
    print("\n3. SYSTEM STATUS:")
    try:
        log_system_status()
    except Exception as e:
        print(f"   Failed to get system status: {e}")

if __name__ == "__main__":
    main()
