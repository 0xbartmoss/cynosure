# Mail.ru Cynosure - Intelligent Restart & Retry System

This document describes the intelligent restart and retry system implemented for the Mail.ru Cynosure email extraction service.

## 🎯 **Problem Solved**

The original system had a simple restart-on-completion approach, but this caused issues when:

- Server returned temporary errors (rate limiting, network issues)
- Authentication tokens expired
- Service got stuck in error loops
- Need to distinguish between "successful completion" vs "temporary failures"

## 🏗️ **Solution Architecture**

### **Core Components:**

1. **`execution_state.py`** - State management and persistence
2. **`error_classifier.py`** - Error classification and handling
3. **`service_manager.py`** - Systemd service operations
4. **`health_monitor.py`** - Health monitoring and stuck detection
5. **Enhanced `main_orchestrator.py`** - Intelligent flow coordination
6. **Enhanced `thread_downloader.py`** - Error-aware downloading

### **Key Features:**

- **Intelligent Error Classification**: Distinguishes between temporary, authentication, and permanent errors
- **Exponential Backoff**: Prevents overwhelming the server with retries
- **Rate Limit Awareness**: Waits for rate limits to expire before retrying
- **Health Monitoring**: Detects stuck executions and long-running processes
- **Persistent State**: Survives service restarts and maintains execution history
- **Configurable Behavior**: All timeouts and limits are configurable

## 📊 **Error Classification System**

### **Error Types:**

| Error Type       | Description                                  | Action                         |
| ---------------- | -------------------------------------------- | ------------------------------ |
| `TEMPORARY`      | Rate limiting, network issues, server errors | Retry with exponential backoff |
| `AUTHENTICATION` | Token expired, login required                | Restart service after delay    |
| `PERMANENT`      | API changes, permanent server issues         | Long delay before retry        |
| `UNKNOWN`        | Unclassified errors                          | Conservative retry approach    |

### **HTTP Status Code Mapping:**

- **429 (Too Many Requests)** → `TEMPORARY`
- **401/403 (Auth Issues)** → `AUTHENTICATION`
- **5xx (Server Errors)** → `TEMPORARY`
- **404 (Not Found)** → `PERMANENT`

## 🔄 **Execution Flow**

### **Normal Flow:**

```
1. Service starts → start_execution()
2. Collects data → set_downloading(total_threads)
3. Downloads threads → update_progress(downloaded)
4. Completes → complete_execution() → restart_service()
```

### **Error Flow:**

```
1. Error occurs → record_error(error_type, message)
2. Classify error → determine retry/restart strategy
3. Temporary error → schedule_retry() (wait and retry)
4. Auth error → schedule_restart() (restart after delay)
5. Permanent error → schedule_retry_or_restart() (based on retry count)
```

### **Rate Limiting Flow:**

```
1. Rate limit detected → record_error(TEMPORARY)
2. Set rate_limit_until timestamp
3. Wait until rate limit expires
4. Retry without restart
```

## ⚙️ **Configuration**

### **Restart Configuration (`config.py`):**

```python
RESTART_CONFIG = {
    "max_retries": 3,                    # Maximum retry attempts
    "retry_delay_base": 60,              # Base delay in seconds
    "retry_delay_multiplier": 2,         # Exponential backoff multiplier
    "max_retry_delay": 3600,             # Maximum retry delay (1 hour)
    "restart_delay_success": 0,          # Immediate restart on success
    "restart_delay_auth": 300,           # 5 minutes for auth failures
    "restart_delay_errors": 600,         # 10 minutes for too many errors
    "max_execution_time": 86400,         # 24 hours max execution time
    "max_consecutive_errors": 5,         # Max consecutive errors before restart
    "rate_limit_duration": 300,          # 5 minutes rate limit duration
    "stuck_threshold": 1800,             # 30 minutes without progress
    "health_check_interval": 300,        # 5 minutes health check interval
}
```

### **Service Configuration:**

```python
SERVICE_CONFIG = {
    "service_name": "cynosure",
    "enable_health_monitoring": True,
    "enable_auto_restart": True,
    "enable_retry_logic": True,
}
```

## 📈 **State Management**

### **Execution States:**

- **`IDLE`** - Service started, waiting for data
- **`COLLECTING`** - Collecting thread IDs
- **`DOWNLOADING`** - Downloading thread data
- **`COMPLETED`** - Successfully completed
- **`ERROR`** - General error state
- **`RATE_LIMITED`** - Rate limited, waiting
- **`AUTH_FAILED`** - Authentication failed

### **Persistent State File:**

The system maintains state in `/home/sh4d3/amsul/projects/mailru/execution_state.json`:

```json
{
  "status": "completed",
  "session_id": "session_1758381295",
  "start_time": "2025-09-20T18:14:55.040334",
  "completion_time": "2025-09-20T18:19:55.040334",
  "error_count": 0,
  "consecutive_errors": 0,
  "retry_count": 0,
  "downloaded_threads": 100,
  "total_threads": 100,
  "rate_limited": false,
  "last_updated": "2025-09-20T18:19:55.040334"
}
```

## 🏥 **Health Monitoring**

### **Health Checks:**

- **Stuck Execution Detection**: No progress for 30 minutes
- **Long Execution Detection**: Running for more than 24 hours
- **Error Threshold**: More than 5 consecutive errors
- **Service Status**: Service not running

### **Health Check Results:**

```python
{
  "timestamp": "2025-09-20T18:19:55.040334",
  "execution_status": {...},
  "service_status": {...},
  "issues": ["Service is not running"],
  "recommendations": ["Start the service"]
}
```

## 🔧 **Usage Examples**

### **Enable/Disable Features:**

```python
# Disable auto-restart
SERVICE_CONFIG["enable_auto_restart"] = False

# Disable retry logic
SERVICE_CONFIG["enable_retry_logic"] = False

# Disable health monitoring
SERVICE_CONFIG["enable_health_monitoring"] = False
```

### **Customize Retry Behavior:**

```python
# More aggressive retry
RESTART_CONFIG["max_retries"] = 5
RESTART_CONFIG["retry_delay_base"] = 30

# More conservative retry
RESTART_CONFIG["max_retries"] = 2
RESTART_CONFIG["retry_delay_base"] = 120
```

## 📊 **Monitoring & Logging**

### **Log Messages:**

```
[+] Started execution session: session_1758381295
[+] Started downloading 100 threads
[+] Download progress: 50/100 threads
[!] Recorded temporary error: Rate limited
[+] Execution completed successfully: 100/100 threads downloaded
[+] Scheduling retry in 60 seconds
[+] Scheduling service restart in 0 seconds
```

### **Status Monitoring:**

```python
# Get comprehensive status
status = main_orchestrator.get_status()
print(f"Execution: {status['execution_state']['status']}")
print(f"Service: {status['service_status']['status']}")
print(f"Health: {status['health_status']['should_restart']}")
```

## 🚀 **Benefits**

### **Reliability:**

- **Self-Healing**: Automatically recovers from temporary failures
- **Error Resilience**: Handles various error conditions gracefully
- **Stuck Detection**: Prevents infinite loops and stuck executions

### **Efficiency:**

- **Smart Retries**: Only retries when appropriate
- **Rate Limit Respect**: Waits for rate limits to expire
- **Exponential Backoff**: Prevents server overload

### **Maintainability:**

- **Comprehensive Logging**: Full audit trail of execution
- **State Persistence**: Survives service restarts
- **Configurable**: Easy to adjust behavior without code changes

### **Monitoring:**

- **Health Checks**: Proactive monitoring of system health
- **Status Reporting**: Detailed status information
- **Error Classification**: Clear understanding of error types

## 🔄 **Migration from Original System**

The intelligent restart system is **backward compatible**:

1. **Same Functionality**: All original features preserved
2. **Enhanced Error Handling**: Better error recovery
3. **Configurable**: Can disable new features if needed
4. **Same Directory Structure**: `YYYY-MM-DD_HHMMSS_username_domain`

## 🛠️ **Troubleshooting**

### **Common Issues:**

1. **Service keeps restarting**: Check error logs, may be authentication issues
2. **Downloads stuck**: Health monitor will detect and restart
3. **Rate limiting**: System will wait and retry automatically
4. **State file issues**: Delete `/home/sh4d3/amsul/projects/mailru/execution_state.json` to reset

### **Debug Commands:**

```bash
# Check service status
systemctl status cynosure

# View service logs
journalctl -u cynosure -f

# Check execution state
cat /home/sh4d3/amsul/projects/mailru/execution_state.json
```

## 📋 **System Requirements**

- **Python 3.7+**
- **systemd** (for service management)
- **All original dependencies** (mitmproxy, requests, etc.)

## 🎯 **Future Enhancements**

- **Metrics Collection**: Prometheus/Grafana integration
- **Alert System**: Email/Slack notifications for critical issues
- **Load Balancing**: Multiple service instances
- **Advanced Retry Strategies**: Circuit breaker pattern
- **Performance Optimization**: Adaptive retry delays based on server response

This intelligent restart system transforms the Mail.ru Cynosure service from a simple "restart on completion" system into a robust, self-healing service that can handle various error conditions gracefully while maintaining high reliability and efficiency.
