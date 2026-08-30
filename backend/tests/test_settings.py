import pytest
from pydantic import ValidationError

from api.settings import Settings


def test_demo_provider_settings_are_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WALT_OPENAI_REALTIME_MODEL", "gpt-realtime-test")
    monkeypatch.setenv("WALT_OPENAI_REALTIME_VAD_THRESHOLD", "0.75")
    monkeypatch.setenv("WALT_OPENAI_REALTIME_NOISE_REDUCTION", "near_field")
    monkeypatch.setenv("WALT_DAYTONA_SNAPSHOT", "atomic-test")
    monkeypatch.setenv("WALT_DEMO_TTL_SECONDS", "600")

    settings = Settings()

    assert settings.openai_realtime_model == "gpt-realtime-test"
    assert settings.openai_realtime_vad_threshold == 0.75
    assert settings.openai_realtime_noise_reduction == "near_field"
    assert settings.daytona_snapshot == "atomic-test"
    assert settings.demo_ttl_seconds == 600


def test_realtime_audio_defaults_favor_laptop_demo_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WALT_OPENAI_REALTIME_VAD_THRESHOLD", raising=False)
    monkeypatch.delenv("WALT_OPENAI_REALTIME_NOISE_REDUCTION", raising=False)
    settings = Settings(_env_file=None)

    assert settings.openai_realtime_vad_threshold == 0.9
    assert settings.openai_realtime_noise_reduction == "far_field"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("WALT_OPENAI_REALTIME_VAD_THRESHOLD", "-0.1"),
        ("WALT_OPENAI_REALTIME_VAD_THRESHOLD", "1.1"),
        ("WALT_OPENAI_REALTIME_NOISE_REDUCTION", "unsupported"),
    ],
)
def test_invalid_realtime_audio_settings_are_rejected(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
