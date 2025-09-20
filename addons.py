"""
Mail.ru Addons - Modular Architecture

This file imports and configures all the modular addons for Mail.ru email extraction.
"""

import os
from url_rewriter import URLRewriter
from email_extractor import EmailExtractor
from auth_extractor import AuthExtractor
from thread_collector import ThreadCollector
from main_orchestrator import MainOrchestrator
from shared_utils import Logger, ResponseFilter
from config import ACTIVE_CONFIG, PERFORMANCE_CONFIG


def display_logo():
    """Display the Cynosure ASCII art logo."""
    try:
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, "logo.txt")

        if os.path.exists(logo_path):
            with open(logo_path, "r", encoding="utf-8") as f:
                logo_content = f.read()
                print(logo_content)
                print("Cynosure Email Extraction System")
                print("=" * 60)
        else:
            print("Cynosure Email Extraction System")
            print("=" * 60)
    except Exception:
        # Fallback if logo file can't be read
        print("Cynosure Email Extraction System")
        print("=" * 60)


# Display logo when the program starts
display_logo()

# Initialize response filter with performance configuration
ResponseFilter.update_from_config(PERFORMANCE_CONFIG)

# Initialize addons based on configuration
addons = []

if ACTIVE_CONFIG.get("url_rewriter", True):
    addons.append(URLRewriter())
    Logger.log("URL Rewriter addon enabled")

if ACTIVE_CONFIG.get("email_extractor", True):
    addons.append(EmailExtractor())
    Logger.log("Email Extractor addon enabled")

if ACTIVE_CONFIG.get("auth_extractor", True):
    addons.append(AuthExtractor())
    Logger.log("Auth Extractor addon enabled")

if ACTIVE_CONFIG.get("thread_collector", True):
    addons.append(ThreadCollector())
    Logger.log("Thread Collector addon enabled")

if ACTIVE_CONFIG.get("main_orchestrator", True):
    addons.append(MainOrchestrator())
    Logger.log("Main Orchestrator addon enabled")

Logger.log(f"Mail.ru addons initialized: {len(addons)} addons enabled")
