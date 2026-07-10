#!/usr/bin/env python3
"""
AI-based junk mail filter for Outlook.

Run standalone:
  python3 batch_cleanup.py

Or schedule daily via launchd (see com.song.junk-cleaner.plist)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from junk_cleaner.runner import main

if __name__ == "__main__":
    main()
