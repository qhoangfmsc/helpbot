"""Pick a deterministic sample of scraped articles for the repo. Usage: python scripts/make_samples.py [src] [dst] [n]."""

import re
import shutil
import sys
from pathlib import Path

DEFAULT_SIZE = 40
QUOTA = {"youtube": None, "code": 6, "table": 6}  # None = take all matches


def pick(files: list[Path], size: int) -> list[Path]:
    """All YouTube articles, a few with code blocks / tables, then an even spread of the rest."""
    chosen: dict[str, Path] = {}
    texts = {f: f.read_text(encoding="utf-8") for f in files}
    matchers = {
        "youtube": lambda f: "youtube" in f.name,
        "code": lambda f: "```" in texts[f],
        "table": lambda f: re.search(r"^\| --- \|", texts[f], re.M) is not None,
    }
    for kind, match in matchers.items():
        taken = 0
        for f in files:
            if QUOTA[kind] is not None and taken >= QUOTA[kind]:
                break
            if match(f) and f.name not in chosen:
                chosen[f.name] = f
                taken += 1
    rest = [f for f in files if f.name not in chosen]
    step = max(len(rest) // max(size - len(chosen), 1), 1)
    for f in rest[::step]:
        if len(chosen) >= size:
            break
        chosen[f.name] = f
    return sorted(chosen.values())


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/articles")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "samples/articles")
    size = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_SIZE
    files = sorted(src.glob("*.md"))
    if not files:
        print(f"no markdown files in {src}", file=sys.stderr)
        return 1
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    selected = pick(files, size)
    for f in selected:
        shutil.copy2(f, dst / f.name)
    print(f"copied {len(selected)} of {len(files)} files to {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
