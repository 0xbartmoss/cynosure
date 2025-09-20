# Mail.ru Email Thread Extractor - Modular Architecture

This project has been refactored into a modular addon architecture for better maintainability, testability, and flexibility.

## 🏗️ Architecture Overview

The original monolithic `mitm.py` has been split into multiple focused addons, each with a single responsibility:

### **Core Addons:**

1. **`URLRewriter`** (`url_rewriter.py`)

   - Fixes evilginx domain issues
   - Rewrites URLs from evilginx domains to real domains

2. **`EmailExtractor`** (`email_extractor.py`)

   - Extracts user email from URL parameters
   - Monitors xray/batch API calls

3. **`AuthExtractor`** (`auth_extractor.py`)

   - Extracts SOTA authentication tokens
   - Parses tokens from inbox HTML responses

4. **`ThreadCollector`** (`thread_collector.py`)

   - Collects thread IDs from API responses
   - Handles pagination to fetch all threads
   - Persists thread IDs to file

5. **`ThreadDownloader`** (`thread_downloader.py`)

   - Downloads thread data and attachments
   - Creates organized directory structures
   - Handles parallel processing

6. **`MainOrchestrator`** (`main_orchestrator.py`)
   - Coordinates between all addons
   - Manages overall flow execution
   - Triggers downloading when ready

### **Supporting Modules:**

- **`shared_utils.py`** - Common utilities and shared state
- **`config.py`** - Configuration for enabling/disabling addons
- **`addons.py`** - Main addon loader and configuration

## 🚀 Usage

### **Full Functionality (Default)**

```bash
mitmdump -s addons.py
```

### **Collection Only (No Downloading)**

Edit `config.py` and set:

```python
ACTIVE_CONFIG = COLLECTION_ONLY_CONFIG
```

### **Download Only (Use Existing Thread IDs)**

Edit `config.py` and set:

```python
ACTIVE_CONFIG = DOWNLOAD_ONLY_CONFIG
```

### **Minimal (Just URL Rewriting)**

Edit `config.py` and set:

```python
ACTIVE_CONFIG = MINIMAL_CONFIG
```

## 📁 Directory Structure

```
/home/sh4d3/amsul/projects/mailru/
├── shared_utils.py          # Common utilities and shared state
├── url_rewriter.py          # URL rewriting addon
├── email_extractor.py       # Email extraction addon
├── auth_extractor.py        # Authentication token extraction addon
├── thread_collector.py      # Thread collection addon
├── thread_downloader.py     # Thread downloading addon
├── main_orchestrator.py     # Main coordination addon
├── config.py               # Configuration file
├── addons.py               # Main addon loader
├── mitm.py                 # Original monolithic version (backup)
└── README_MODULAR.md       # This documentation
```

## 🔧 Configuration

### **Enable/Disable Addons**

Edit `config.py` to customize which addons are active:

```python
ADDON_CONFIG = {
    "url_rewriter": True,      # Fix evilginx domain issues
    "email_extractor": True,   # Extract email from URL parameters
    "auth_extractor": True,    # Extract SOTA tokens from HTML
    "thread_collector": True,  # Collect thread IDs with pagination
    "main_orchestrator": True, # Coordinate and execute main flow
}
```

### **Preset Configurations**

- `ADDON_CONFIG` - Full functionality (default)
- `COLLECTION_ONLY_CONFIG` - Only collect threads, no downloading
- `DOWNLOAD_ONLY_CONFIG` - Only download existing threads
- `MINIMAL_CONFIG` - Just URL rewriting

## 📊 Benefits of Modular Architecture

### **1. Single Responsibility**

Each addon has one clear purpose, making the code easier to understand and maintain.

### **2. Independence**

Addons can work independently and be tested in isolation.

### **3. Composability**

Mix and match addons as needed for different use cases.

### **4. Testability**

Each addon can be unit tested separately.

### **5. Maintainability**

Changes to one addon don't affect others.

### **6. Extensibility**

Easy to add new addons (e.g., attachment processor, email parser).

## 🔄 Data Flow

```
1. URLRewriter → Fixes domain issues
2. EmailExtractor → Extracts email from URLs
3. AuthExtractor → Extracts SOTA tokens from HTML
4. ThreadCollector → Collects thread IDs with pagination
5. MainOrchestrator → Coordinates and triggers downloading
6. ThreadDownloader → Downloads threads and attachments
```

## 📝 Shared State

All addons communicate through a shared state object (`shared_state`) that contains:

- `username` - Extracted email address
- `sota_token` - Authentication token
- `thread_ids` - Collected thread IDs
- `ready_to_download` - Flag indicating readiness
- `_flow_executed` - Prevents duplicate execution

## 🧪 Testing

Each addon can be tested independently:

```python
# Test individual addon
from email_extractor import EmailExtractor
extractor = EmailExtractor()
# ... test methods
```

## 🔄 Migration from Monolithic Version

The original `mitm.py` has been preserved as a backup. To use the modular version:

1. Use `addons.py` instead of `mitm.py`
2. Configure addons in `config.py`
3. All functionality remains the same

## 📈 Performance

The modular architecture maintains the same performance characteristics as the original:

- Parallel thread processing
- Efficient attachment downloading
- Connection pooling
- Proper error handling

## 🛠️ Development

To add a new addon:

1. Create a new Python file (e.g., `new_addon.py`)
2. Implement the addon class with `request()` and `response()` methods
3. Add configuration option to `config.py`
4. Import and initialize in `addons.py`

## 📋 Requirements

Same requirements as the original version:

- Python 3.7+
- mitmproxy
- requests
- All dependencies from the original `mitm.py`

## 🎯 Use Cases

### **Full Email Extraction**

Use all addons for complete email thread extraction with attachments.

### **Thread Collection Only**

Use collection addons to gather thread IDs without downloading content.

### **Download Existing Threads**

Use downloader addon to process previously collected thread IDs.

### **URL Fixing Only**

Use URL rewriter addon to fix evilginx domain issues without other functionality.

This modular architecture provides the same functionality as the original monolithic version while being much more maintainable, testable, and flexible.
