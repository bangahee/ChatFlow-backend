from app.config import Settings, get_settings


def test_settings_use_safe_defaults() -> None:
    secret_key = "unit-test-secret-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    settings = Settings(_env_file=None, secret_key=secret_key)

    assert settings.app_env == "development"
    assert settings.secret_key.get_secret_value() == secret_key
    assert settings.access_token_expire_minutes == 1440
    assert settings.database_url == "sqlite:///./chatflow.db"
    assert settings.openai_api_key.get_secret_value() == ""


def test_settings_read_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "SECRET_KEY",
        "environment-test-secret-key-xxxxxxxxxxxxxxxxxxxxxxxx",
    )
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

    settings = Settings(_env_file=None)

    assert settings.app_env == "test"
    assert settings.secret_key.get_secret_value() == (
        "environment-test-secret-key-xxxxxxxxxxxxxxxxxxxxxxxx"
    )
    assert settings.access_token_expire_minutes == 30


def test_cors_origins_are_normalized_and_deduplicated() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins=(
            " http://localhost:5173/,https://frontend.example.com,"
            "http://localhost:5173 "
        ),
    )

    assert settings.cors_origin_list == [
        "http://localhost:5173",
        "https://frontend.example.com",
    ]


def test_secret_values_are_hidden_from_repr() -> None:
    secret_key = "super-secret-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    settings = Settings(
        _env_file=None,
        secret_key=secret_key,
        openai_api_key="super-secret-openai-key",
    )

    representation = repr(settings)

    assert secret_key not in representation
    assert "super-secret-openai-key" not in representation


def test_get_settings_returns_cached_instance(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "cached-test")

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.app_env == "cached-test"
    get_settings.cache_clear()
