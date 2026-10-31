---
name: md-quality-check
description: Lint the scraped Markdown corpus (data/articles) for leftover HTML, missing Article URL lines, empty tables, short files; then spot-read a few files by eye. Use after any change to the scraper or converter.
---

# md-quality-check

1. Re-scrape if the converter changed, then run `.venv/bin/python scripts/check_markdown.py data/articles`. Exit code must be 0.
2. Read the printed stats: headings, code blocks, relative/anchor links and tables should be present in a plausible share of files (they are the spec's "preserve" list).
3. Spot-read 3 files by eye, always including one with a table, one with a code block, and the article that answers "How do I add a YouTube video?" (`*-how-to-use-youtube-with-optisigns.md`). Check headings, lists, links, images, and that the first lines are `# Title` then `Article URL: ...`.
4. If a pattern of noise shows up (e.g. empty header rows, wrapper elements), fix it in `src/helpbot/markdown.py`, add a unit test in `tests/test_markdown.py`, and repeat.
5. Log what was found and fixed in `NOTES.md`.

Known-legit warnings: HTML inside fenced code blocks (embed examples); comparison tables whose top-left cell is empty.
