#!/usr/bin/env python3
"""
Cynosure Log Checker
Check cynosure.service logs and analyze thread download issues.
"""

import subprocess
import sys
from datetime import datetime

def get_service_logs(lines=100):
    """Get recent cynosure.service logs."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", "cynosure.service", "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return result.stdout
    except Exception as e:
        print(f"Failed to get service logs: {e}")
        return ""

def get_realtime_logs():
    """Get real-time logs for monitoring."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", "cynosure.service", "-f", "--no-pager"],
            check=False,
        )
    except KeyboardInterrupt:
        print("\nStopped monitoring logs.")
    except Exception as e:
        print(f"Failed to get real-time logs: {e}")

def analyze_logs(logs):
    """Analyze logs for thread download issues."""
    print("=" * 80)
    print("CYNOSURE LOG ANALYSIS")
    print("=" * 80)
    
    lines = logs.split('\n')
    
    # Look for key indicators
    email_extractions = []
    auth_extractions = []
    thread_collections = []
    session_ready = []
    orchestrator_executions = []
    downloader_starts = []
    errors = []
    
    for line in lines:
        if "EMAIL_EXTRACTOR:" in line:
            email_extractions.append(line)
        elif "AUTH_EXTRACTOR:" in line:
            auth_extractions.append(line)
        elif "THREAD_COLLECTOR:" in line:
            thread_collections.append(line)
        elif "SESSION:" in line and "is now READY" in line:
            session_ready.append(line)
        elif "ORCHESTRATOR:" in line and "Executing flow" in line:
            orchestrator_executions.append(line)
        elif "DOWNLOADER:" in line and "Starting download" in line:
            downloader_starts.append(line)
        elif "ERROR" in line.upper() or "FAILED" in line.upper():
            errors.append(line)
    
    # Print analysis
    print(f"📧 Email Extractions: {len(email_extractions)}")
    for line in email_extractions[-3:]:  # Show last 3
        print(f"   {line}")
    
    print(f"\n🔑 Auth Token Extractions: {len(auth_extractions)}")
    for line in auth_extractions[-3:]:
        print(f"   {line}")
    
    print(f"\n🧵 Thread Collections: {len(thread_collections)}")
    for line in thread_collections[-3:]:
        print(f"   {line}")
    
    print(f"\n✅ Sessions Ready: {len(session_ready)}")
    for line in session_ready[-3:]:
        print(f"   {line}")
    
    print(f"\n🎯 Orchestrator Executions: {len(orchestrator_executions)}")
    for line in orchestrator_executions[-3:]:
        print(f"   {line}")
    
    print(f"\n⬇️  Download Starts: {len(downloader_starts)}")
    for line in downloader_starts[-3:]:
        print(f"   {line}")
    
    print(f"\n❌ Errors: {len(errors)}")
    for line in errors[-5:]:  # Show last 5 errors
        print(f"   {line}")
    
    # Analysis summary
    print("\n" + "=" * 80)
    print("DIAGNOSIS:")
    print("=" * 80)
    
    if len(email_extractions) == 0:
        print("❌ ISSUE: No email extractions detected")
        print("   - Check if Mail.ru traffic is being intercepted")
        print("   - Verify URL patterns in email_extractor.py")
    
    if len(auth_extractions) == 0:
        print("❌ ISSUE: No SOTA token extractions detected")
        print("   - Check if inbox HTML responses are being intercepted")
        print("   - Verify token extraction patterns")
    
    if len(thread_collections) == 0:
        print("❌ ISSUE: No thread collections detected")
        print("   - Check if smart threads API is being called")
        print("   - Verify JSON response parsing")
    
    if len(session_ready) == 0:
        print("❌ ISSUE: No sessions became ready")
        print("   - Sessions need email + token + thread_ids to be ready")
    
    if len(orchestrator_executions) == 0 and len(session_ready) > 0:
        print("❌ ISSUE: Sessions ready but orchestrator not executing")
        print("   - Check flow context validation")
        print("   - Check for session state conflicts")
    
    if len(downloader_starts) == 0 and len(orchestrator_executions) > 0:
        print("❌ ISSUE: Orchestrator executing but downloads not starting")
        print("   - Check ThreadDownloader initialization")
        print("   - Check for missing session data")
    
    if len(downloader_starts) > 0:
        print("✅ Downloads are starting - check for progress logs")
    
    if len(errors) > 0:
        print(f"⚠️  {len(errors)} errors detected - investigate error messages above")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--follow":
        print("Monitoring cynosure.service logs in real-time...")
        print("Press Ctrl+C to stop")
        get_realtime_logs()
    else:
        logs = get_service_logs(200)  # Get more logs for analysis
        if logs:
            analyze_logs(logs)
        else:
            print("No logs found or failed to retrieve logs")
            print("Try running: sudo journalctl -u cynosure.service -n 50")

if __name__ == "__main__":
    main()
