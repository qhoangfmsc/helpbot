"""config/settings.toml: the one place for non-secret settings. Mistakes must be loud, not silently ignored."""

import dataclasses

import pytest

from helpbot.settings import ROOT, SETTINGS_FILE, Settings, load_settings


def write(tmp_path, text):
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_committed_settings_file_is_valid_and_documents_every_setting():
    loaded = load_settings(SETTINGS_FILE)
    text = SETTINGS_FILE.read_text(encoding="utf-8")
    for field in dataclasses.fields(Settings):
        assert field.name in text, f"{field.name} is missing from config/settings.toml"
    assert loaded == Settings()  # the file shows the defaults, so deleting a line changes nothing


def test_the_settings_point_at_files_that_exist():
    settings = load_settings()
    assert settings.path(settings.article_ids_file).is_file()
    assert settings.path(settings.articles_dir).is_dir()


def test_missing_file_means_defaults(tmp_path):
    assert load_settings(tmp_path / "nope.toml") == Settings()


def test_values_override_defaults_and_lists_become_tuples(tmp_path):
    settings = load_settings(write(tmp_path, 'upload_workers = 2\nchat_fallback_models = ["a", "b"]\nstore_name = "x"\n'))
    assert (settings.upload_workers, settings.chat_fallback_models, settings.store_name) == (2, ("a", "b"), "x")


@pytest.mark.parametrize("text, words", [
    ("uplaod_workers = 2", "unknown setting"),
    ("upload_workers = 'many'", "invalid value"),
    ("upload_workers = 0", "invalid value"),
    ("job_max_minutes = true", "invalid value"),
    ("store_name = ''", "invalid value"),
    ("chat_fallback_models = 'x'", "invalid value"),
])
def test_mistakes_are_reported_with_the_setting_name(tmp_path, text, words):
    with pytest.raises(ValueError, match=words):
        load_settings(write(tmp_path, text))


def test_paths_are_relative_to_the_repo_root_unless_absolute():
    assert Settings().path("articles") == ROOT / "articles"
    assert Settings().path("/tmp/x") == __import__("pathlib").Path("/tmp/x")
