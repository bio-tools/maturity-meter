"""Unit tests for reusable processing behavior."""

import logging

from maturity_meter.config import Settings
from maturity_meter.logging_config import configure_logging
from maturity_meter.services.processing import make_upper, process_text


def test_process_text_returns_structured_result():
    """Ensure service processing preserves input and returns output."""
    result = process_text("abc")

    assert result.input_text == "abc"
    assert result.output_text == "ABC"


def test_make_upper_reuses_processing_service():
    """Ensure convenience helper follows service behavior."""
    assert make_upper("research") == "RESEARCH"


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
        logging.getLogger(
            "maturity_meter.services.processing"
        ).getEffectiveLevel()
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
    assert str(settings.public_base_url) == (
        "https://example.org/maturity_meter/"
    )
