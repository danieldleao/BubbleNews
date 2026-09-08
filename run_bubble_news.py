#!/usr/bin/env python3
"""
==============================================================================
BUBBLE NEWS — Execution Runner
==============================================================================
Main execution entry point for Bubble News.

Called by:
  - Windows Task Scheduler (for automated daily execution)
  - Desktop shortcut or batch script
  - Command line (for on-demand manual execution or dry-run testing)

Usage:
  python run_bubble_news.py
  python run_bubble_news.py --dry-run
  python run_bubble_news.py --hours 24
==============================================================================
"""

import sys
from bubble_news import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Execution cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n[FATAL ERROR] Unexpected termination: {e}", file=sys.stderr)
        sys.exit(1)
