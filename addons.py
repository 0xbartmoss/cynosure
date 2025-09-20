"""
Mail.ru Addons - Modular Architecture

This file imports and configures all the modular addons for Mail.ru email extraction.
"""

from url_rewriter import URLRewriter
from email_extractor import EmailExtractor
from auth_extractor import AuthExtractor
from thread_collector import ThreadCollector
from main_orchestrator import MainOrchestrator
from shared_utils import Logger
from config import ACTIVE_CONFIG

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
