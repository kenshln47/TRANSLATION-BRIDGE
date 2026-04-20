"""
Translation Bridge v8.0
Multi-language translator via OpenRouter (Grok 4.1 Fast)

This file is a compatibility wrapper. The real code lives in the chat_bridge/ package.
Run with: python chat_bridge.py  OR  python -m chat_bridge
"""

import sys
import os

# Make sure the package can be found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chat_bridge.__main__ import main

if __name__ == "__main__":
    main()
