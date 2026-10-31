"""Code clarity + README deliverables from the task: no hard-coded keys, .env.sample, pinned deps, a one-page README."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = ("helpbot", "scripts", "tests")
SECRET = re.compile(r"AIza[0-9A-Za-z_\-]{20,}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}")
ENV_READ = re.compile(r"""os\.environ(?:\.get\(|\[)\s*["']([A-Z_]+)["']""")


def source_files() -> list[Path]:
    files = [ROOT / "main.py"]
    for folder in SOURCE_DIRS:
        files += (ROOT / folder).rglob("*.py")
    return files


def test_no_hard_coded_api_keys_in_source():
    leaks = [p.name for p in source_files() if SECRET.search(p.read_text(encoding="utf-8"))]
    assert leaks == []


def test_env_file_is_ignored_and_a_sample_is_provided():
    assert re.search(r"^\.env$", (ROOT / ".gitignore").read_text(), re.M)
    sample = (ROOT / ".env.sample").read_text()
    assert re.search(r"^GEMINI_API_KEY=$", sample, re.M)  # present but empty


def test_the_api_key_is_the_only_environment_variable_the_code_reads():
    read = {name for p in source_files() if "tests" not in p.parts for name in ENV_READ.findall(p.read_text())}
    assert read == {"GEMINI_API_KEY"}  # everything else lives in config/settings.toml


def test_env_sample_holds_only_the_empty_key():
    lines = [l for l in (ROOT / ".env.sample").read_text().splitlines() if l.strip() and not l.startswith("#")]
    assert lines == ["GEMINI_API_KEY="]


def test_no_api_key_value_sits_in_any_file_that_would_be_committed():
    value = re.compile(r"GEMINI_API_KEY\s*=\s*[\"']?[A-Za-z0-9._\-]{20,}|AIza[0-9A-Za-z_\-]{30,}")
    skipped_dirs = {".git", ".venv", "data", "__pycache__", ".pytest_cache", "articles"}
    leaks = [
        str(p.relative_to(ROOT))
        for p in ROOT.rglob("*")
        if p.is_file() and p.name != ".env" and not skipped_dirs & set(p.relative_to(ROOT).parts) and p.suffix not in {".pyc", ".png", ".jpg"}
        and value.search(p.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert leaks == []


def test_dependencies_are_pinned():
    for name in ("requirements.txt", "requirements-dev.txt"):
        lines = [l.strip() for l in (ROOT / name).read_text().splitlines() if l.strip() and not l.startswith(("#", "-r"))]
        assert lines and all("==" in l for l in lines), name


def test_readme_fits_one_page_and_has_the_required_sections():
    readme = (ROOT / "README.md").read_text()
    assert len(readme.splitlines()) <= 70
    for section in ("Run locally", "Daily job", "screenshot"):
        assert section.lower() in readme.lower(), section


def test_readme_has_no_todo_left():
    assert "TODO" not in (ROOT / "README.md").read_text()


def test_dockerfile_runs_the_job_once_and_never_bakes_in_the_key():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert re.search(r'^CMD \["python", "main\.py"\]', dockerfile, re.M)  # runs once, then the container exits
    assert "GEMINI_API_KEY" not in dockerfile.replace("Needs GEMINI_API_KEY", "")
    assert re.search(r"^\.env$", (ROOT / ".dockerignore").read_text(), re.M)
    assert "COPY config" in dockerfile  # the list of articles the job syncs must be inside the image


def test_daily_workflow_runs_once_a_day_with_the_key_from_secrets():
    workflow = (ROOT / ".github" / "workflows" / "daily-sync.yml").read_text()
    crons = re.findall(r'cron:\s*"([^"]+)"', workflow)
    assert len(crons) == 1
    minute, hour, day, month, weekday = crons[0].split()
    assert minute.isdigit() and hour.isdigit() and (day, month, weekday) == ("*", "*", "*")  # exactly once per day
    assert "${{ secrets.GEMINI_API_KEY }}" in workflow
    assert not SECRET.search(workflow)


def test_images_and_files_linked_from_the_readme_exist():
    readme = (ROOT / "README.md").read_text()
    targets = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", readme) + re.findall(r"`((?:docs|scripts|config|prompts)/[\w./\-]+)`", readme)
    assert targets, "expected the README to link at least the screenshot"
    assert [t for t in targets if not t.startswith("http") and not (ROOT / t).exists()] == []
