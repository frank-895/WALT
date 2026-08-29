import pytest

from api.settings import Settings


def test_ai_settings_are_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WALT_AI_MODEL", "openai:example-model")
    monkeypatch.setenv("WALT_AI_TEMPERATURE", "0.25")
    monkeypatch.setenv("WALT_AI_MAX_TOKENS", "512")

    settings = Settings()

    assert settings.ai_model == "openai:example-model"
    assert settings.ai_model_settings == {
        "temperature": 0.25,
        "max_tokens": 512,
    }
