"""After the run, print what each test file covers (its module docstring) and how many of its tests passed.

`pytest -q` alone only shows dots; this summary groups the results by grading area so a reviewer sees what is tested.
"""

import ast
import shutil
import textwrap
from collections import defaultdict
from pathlib import Path

AREAS = {  # folder under tests/ -> heading
    "scrape_quality": "Scrape and clean quality (25 pts)",
    "vector_upload": "API vector-store upload (20 pts)",
    "daily_job": "Daily job and logs (15 pts)",
    "repo_hygiene": "Code clarity and README (10 pts)",
}
OUTCOMES = ("passed", "failed", "error", "skipped")


def module_summary(path: Path) -> str:
    """First line of the test file's module docstring ('' if it has none)."""
    docstring = ast.get_docstring(ast.parse(path.read_text()))
    return docstring.splitlines()[0] if docstring else ""


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    per_file: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(OUTCOMES, 0))
    for outcome in OUTCOMES:
        for report in terminalreporter.stats.get(outcome, []):
            if report.when == "call" or outcome in ("error", "skipped"):
                per_file[report.nodeid.split("::")[0]][outcome] += 1
    if not per_file:
        return

    width = shutil.get_terminal_size((100, 20)).columns
    terminalreporter.section("what the tests cover")
    for folder, heading in AREAS.items():
        files = sorted(path for path in per_file if Path(path).parent.name == folder)
        if not files:
            continue
        total = sum(per_file[path]["passed"] for path in files)
        terminalreporter.write_line(f"{heading}: {total} passed in {len(files)} files")
        for path in files:
            counts = per_file[path]
            status = f"{counts['passed']:>3} passed" + "".join(
                f", {counts[o]} {o}" for o in OUTCOMES[1:] if counts[o]
            )
            terminalreporter.write_line(f"  {Path(path).name}  [{status}]")
            summary = module_summary(Path(config.rootpath) / path)
            if summary:
                terminalreporter.write_line(
                    textwrap.fill(summary, width=width - 1, initial_indent="      ", subsequent_indent="      ")
                )
        terminalreporter.write_line("")
