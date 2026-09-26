import pytest

from station import livelog, settings


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Never read or write the real data/ folder from tests."""
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(livelog, "DATA_DIR", tmp_path)
    monkeypatch.setattr(livelog, "LOG_FILE", tmp_path / "bias_log.jsonl")
