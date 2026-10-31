"""Sync the Markdown articles into the Gemini store: the same job the daily workflow runs.

Usage: python scripts/sync_docs.py            (needs GEMINI_API_KEY in .env; first run ~1-2 min, later runs only upload changes)
       python scripts/sync_docs.py --allow-mass-delete   (one-off cleanup after deliberately shrinking config/article_ids.txt)
Prints `added=… updated=… skipped=…` at the end. Check the result with scripts/check_store.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
