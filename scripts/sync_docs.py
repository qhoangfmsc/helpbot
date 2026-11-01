"""Sync the Markdown articles into the Gemini store: the same job the daily workflow runs.

Usage: python scripts/sync_docs.py            (needs GEMINI_API_KEY in .env; first run ~2-3 min, later runs only upload changes)
Prints `added=… updated=… skipped=…` at the end. Check the result with scripts/check_store.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
