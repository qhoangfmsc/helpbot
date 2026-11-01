"""Non-secret settings live in config/settings.toml; the only environment variable is GEMINI_API_KEY."""

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "config" / "settings.toml"
ZERO_ALLOWED = {"newest_articles"}  # 0 = "no newest articles, only the listed ones"


@dataclass(frozen=True)
class Settings:
    help_center_url: str = "https://support.optisigns.com"
    article_ids_file: str = "config/article_ids.txt"
    newest_articles: int = 40
    articles_dir: str = "articles"
    store_name: str = "helpbot-docs"
    upload_workers: int = 4
    request_timeout_seconds: float = 90
    job_max_minutes: float = 30
    chat_model: str = "gemini-3.5-flash"
    chat_fallback_models: tuple[str, ...] = ("gemini-3-flash-preview", "gemini-flash-lite-latest")

    def path(self, value: str) -> Path:
        """A path setting, relative to the repo root unless it is absolute."""
        candidate = Path(value)
        return candidate if candidate.is_absolute() else ROOT / candidate


def load_settings(path: Path = SETTINGS_FILE) -> Settings:
    """Read the TOML file; a misspelt name or a value of the wrong type is an error, never silently ignored."""
    if not path.exists():
        return Settings()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    known = {f.name: f for f in fields(Settings)}
    unknown = sorted(set(data) - set(known))
    if unknown:
        raise ValueError(f"{path.name}: unknown setting(s) {', '.join(unknown)} (known: {', '.join(known)})")
    for name, value in data.items():
        expected = known[name].type
        if expected == "tuple[str, ...]" or expected == tuple[str, ...]:
            ok = isinstance(value, list) and all(isinstance(v, str) for v in value)
            data[name] = tuple(value) if ok else value
        elif expected in (int, "int"):
            ok = isinstance(value, int) and not isinstance(value, bool) and value >= (0 if name in ZERO_ALLOWED else 1)
        elif expected in (float, "float"):
            ok = isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0
        else:
            ok = isinstance(value, str) and value.strip() != ""
        if not ok:
            raise ValueError(f"{path.name}: {name} has an invalid value {value!r}")
    return Settings(**data)
