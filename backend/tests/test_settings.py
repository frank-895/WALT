import pytest

from api.settings import Settings


def test_demo_provider_settings_are_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WALT_OPENAI_REALTIME_MODEL", "gpt-realtime-test")
    monkeypatch.setenv("WALT_DAYTONA_SNAPSHOT", "atomic-test")
    monkeypatch.setenv("WALT_DEMO_TTL_SECONDS", "600")

    settings = Settings()

    assert settings.openai_realtime_model == "gpt-realtime-test"
    assert settings.daytona_snapshot == "atomic-test"
    assert settings.demo_ttl_seconds == 600
