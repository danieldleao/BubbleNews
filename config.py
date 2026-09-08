"""
==============================================================================
BUBBLE NEWS — Core Configuration (v0.1 Beta)
==============================================================================
Central configuration file for Bubble News.
Customize these settings with your personal credentials and preferences.
==============================================================================
"""

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load key-value pairs from a local .env file into os.environ if present."""
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.is_file():
        return
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


_load_dotenv()


# ==============================================================================
# 1. EMAIL DELIVERY CONFIGURATION (Disroot SMTP)
# ==============================================================================
# The email address used as both the sender and recipient of the news digest.
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "your-email@example.com")

# Password or App Password for your Disroot email / SMTP account.
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "YOUR_EMAIL_PASSWORD")

# SMTP Server host and port (Disroot SMTP uses port 587 with STARTTLS).
SMTP_SERVER = os.environ.get("SMTP_SERVER", "disroot.org")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))

# ==============================================================================
# 2. AI ENGINE CONFIGURATION (Google Gemini)
# ==============================================================================
# AI Provider name
AI_PROVIDER = "Google Gemini"

# Google Gemini API Key from Google AI Studio (https://aistudio.google.com)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

# Gemini model for deduplication, consolidation, and summarization.
# Recommended: "gemini-3.6-flash" (fast, high quality)
# Alternatives: "gemini-2.5-flash", "gemini-1.5-pro"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

# ==============================================================================
# 3. SCHEDULE CONFIGURATION
# ==============================================================================
# Daily scheduled run time in 24-hour HH:MM format (e.g. "08:00", "07:30", "19:00").
# This represents the single source of truth for when Bubble News is intended to run.
SCHEDULE_TIME = os.environ.get("SCHEDULE_TIME", "08:00")

# ==============================================================================
# 4. APPLICATION & RSS SETTINGS
# ==============================================================================
# Path to the RSS feeds JSON configuration file.
FEEDS_FILE = os.environ.get("FEEDS_FILE", "bubble_news.json")

# Time window in hours for article publication (default: 12 hours).
TIME_WINDOW_HOURS = int(os.environ.get("TIME_WINDOW_HOURS", 12))

# Execution log file.
LOG_FILE = os.environ.get("LOG_FILE", "bubble_news.log")
