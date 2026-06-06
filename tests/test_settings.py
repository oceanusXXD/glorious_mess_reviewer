"""Settings validation and environment alias tests."""

from __future__ import annotations

import pytest

from glorious_mess_reviewer.config.settings import Settings


def test_settings_accepts_standard_openai_api_key_env_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GLORIOUS_MESS_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "alias-key")

    settings = Settings()

    assert settings.openai_api_key == "alias-key"


def test_explicit_openai_api_key_argument_overrides_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    settings = Settings(openai_api_key=None)

    assert settings.openai_api_key is None


def test_settings_rejects_unknown_provider_backend() -> None:
    with pytest.raises(ValueError):
        Settings(provider_backend="mystery")


def test_settings_rejects_invalid_runtime_bounds() -> None:
    with pytest.raises(ValueError):
        Settings(minimum_reviewable_characters=0)

    with pytest.raises(ValueError):
        Settings(port=70000)
