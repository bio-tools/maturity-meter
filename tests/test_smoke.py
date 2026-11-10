"""Smoke tests for the generated Python package."""

import asyncio
from importlib.metadata import PackageNotFoundError, version

import pytest

from maturity_meter import EvaluationRequest, __version__, evaluate_maturity
from maturity_meter.main import main


def test_package_has_version():
    """Ensure the package exposes its installed distribution version."""
    try:
        installed_version = version("maturity-meter")
    except PackageNotFoundError:
        installed_version = "0+unknown"

    assert __version__ == installed_version


def test_main_is_callable():
    """Ensure the runtime entry point can be imported."""
    assert callable(main)


def test_library_api_evaluates_maturity(monkeypatch):
    """Ensure reusable service logic is available from the package API."""
    from maturity_meter.models import Evaluation, IngestedData
    from maturity_meter.services import processing

    async def fake_ingest(request):
        return IngestedData(request=request, repository={})

    monkeypatch.setattr(processing, "ingest", fake_ingest)
    request = EvaluationRequest(repository="https://github.com/o/r")
    result = asyncio.run(evaluate_maturity(request))

    assert result.maturity_placeholder == Evaluation()


def test_runtime_settings_import():
    """Ensure the selected runtime settings boundary imports."""
    from maturity_meter.config import Settings

    assert Settings(_env_file=None).log_level == "INFO"


def test_http_server_runner_imports():
    """Ensure the configured HTTP server entry point imports."""
    pytest.importorskip("uvicorn")
    from maturity_meter.adapters.server_runner import main

    assert callable(main)


def test_cli_entry_point_imports():
    """Ensure the selected command-line application imports."""
    pytest.importorskip("typer")
    from maturity_meter.adapters.cli.app import app

    assert callable(app)


def test_api_entry_point_imports():
    """Ensure the selected API application factory imports."""
    pytest.importorskip("fastapi")
    from maturity_meter.adapters.api.app import create_app

    assert callable(create_app)
