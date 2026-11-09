"""Unit tests for reusable processing behavior."""

import logging

from maturity_meter.config import Settings
from maturity_meter.logging_config import configure_logging
from maturity_meter.services.processing import evaluate_maturity


def test_evaluate_maturity_returns_structured_result():
    """Ensure the service returns a structured maturity result."""
    result = evaluate_maturity()

    assert result.maturity_placeholder == 1.0


def test_runtime_settings_read_project_environment(monkeypatch):
    """Ensure project-prefixed environment variables override defaults."""
    monkeypatch.setenv("MATURITY_METER_LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.log_level == "DEBUG"


def test_logging_configuration_sets_package_level():
    """Ensure configured log levels apply to package module loggers."""
    settings = Settings(_env_file=None, log_level="DEBUG")

    package_logger = configure_logging(settings)

    assert package_logger.name == "maturity_meter"
    assert (
        logging.getLogger("maturity_meter.services.processing").getEffectiveLevel()
        == logging.DEBUG
    )


def test_http_server_settings_are_typed(monkeypatch):
    """Ensure HTTP bind and public URL settings are parsed and normalized."""
    monkeypatch.setenv("MATURITY_METER_SERVER_PORT", "9000")
    monkeypatch.setenv(
        "MATURITY_METER_SERVER_ROOT_PATH",
        "services/maturity_meter/",
    )
    monkeypatch.setenv(
        "MATURITY_METER_PUBLIC_BASE_URL",
        "https://example.org/maturity_meter/",
    )

    settings = Settings(_env_file=None)

    assert settings.server_port == 9000
    assert settings.server_root_path == "/services/maturity_meter"
    assert str(settings.public_base_url) == ("https://example.org/maturity_meter/")


def test_github_headers_use_configured_token(monkeypatch):
    """Ensure the GitHub token is sent only when configured."""
    from maturity_meter.config import get_settings
    from maturity_meter.external.github.github_auth import get_github_headers

    monkeypatch.chdir("/")  # avoid picking up a local .env
    monkeypatch.delenv("MATURITY_METER_GITHUB_TOKEN", raising=False)
    get_settings.cache_clear()
    assert "Authorization" not in get_github_headers()

    monkeypatch.setenv("MATURITY_METER_GITHUB_TOKEN", "abc")
    get_settings.cache_clear()
    assert get_github_headers()["Authorization"] == "Bearer abc"
    get_settings.cache_clear()
