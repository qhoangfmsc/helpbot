"""Lint the scraped Markdown corpus. Usage: python scripts/check_markdown.py [dir]  (exit 1 on failures)."""

import re
import sys
from collections import Counter
from pathlib import Path

FENCE = re.compile(r"^[ \t]*```.*?^[ \t]*```", re.S | re.M)  # fences may be indented inside lists
HTML_TAG = re.compile(r"</?(div|span|table|thead|tbody|tr|td|th|figure|p|br|strong|em|script|style)[\s>/]")
MIN_BODY_CHARS = 120
MAX_LINE_CHARS = 5000


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    prose = FENCE.sub("", text)  # HTML inside code blocks is legitimate content
    problems = []
    if not text.startswith("# "):
        problems.append("no H1 title on first line")
    if len(re.findall(r"^Article URL: https?://\S+$", text, re.M)) != 1:
        problems.append("expected exactly one 'Article URL:' line")
    if HTML_TAG.search(prose):
        problems.append("leftover HTML tags outside code blocks")
    if re.search(r"^\|\s*\|\s*\|?\s*$", prose, re.M) and re.search(r"^\| --- \|", prose, re.M):
        problems.append("table with fully empty header or row")
    if re.search(r"^#{1,6}\s*$", prose, re.M):
        problems.append("empty heading")
    if re.search("[\u00a0\u200b\u200c\u200d\u2060\ufeff]", text):
        problems.append("non-breaking or zero-width character")
    if "](data:" in text:
        problems.append("inline base64 image")
    if max(map(len, text.splitlines()), default=0) > MAX_LINE_CHARS:
        problems.append(f"line longer than {MAX_LINE_CHARS} chars")
    if len(text) < MIN_BODY_CHARS:
        problems.append(f"suspiciously short ({len(text)} chars)")
    if prose.count("```") % 2:
        problems.append("unbalanced code fence")
    return problems


def main() -> int:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "data/articles")
    files = sorted(folder.glob("*.md"))
    failures = {f.name: p for f in files if (p := check(f))}
    stats = Counter()
    for f in files:
        text = f.read_text(encoding="utf-8")
        stats["files"] += 1
        stats["with_headings"] += bool(re.search(r"^#{2,6} ", text, re.M))
        stats["with_code_blocks"] += "```" in text
        stats["with_relative_or_anchor_links"] += bool(re.search(r"\]\((/|#)", text))
        stats["with_tables"] += bool(re.search(r"^\| --- \|", text, re.M))
    print(dict(stats))
    for name, problems in failures.items():
        print(f"FAIL {name}: {'; '.join(problems)}")
    print(f"{len(files) - len(failures)}/{len(files)} files ok")
    return 1 if failures or not files else 0


if __name__ == "__main__":
    sys.exit(main())
