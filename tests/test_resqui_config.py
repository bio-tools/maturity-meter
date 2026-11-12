"""Verify the bundled resqui indicator configuration."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

CONFIG = (
    Path(__file__).resolve().parents[1]
    / "src/maturity_meter/external/ingestors/resqui_config.json"
)


def test_fairchecker_indicators():
    indicators = json.loads(CONFIG.read_text())["indicators"]
    fairchecker = [entry for entry in indicators if entry["plugin"] == "FAIRChecker"]
    expected = {
        "unique_ids": "F1A",
        "persistent_ids": "F1B",
        "structured_metadata": "F2A",
        "shared_vocabularies_for_metadata": "F2B",
        "machine_readable_format": "I1",
        "use_shared_ontologies": "I2",
        "external_links": "I3",
        "license_metadata": "R11",
    }
    assert len(fairchecker) == len(expected)
    assert {entry["name"]: entry["@id"] for entry in fairchecker} == {
        name: f"https://w3id.org/fair/principles/terms/{identifier}"
        for name, identifier in expected.items()
    }


def test_new_indicators_and_unique_configuration():
    indicators = json.loads(CONFIG.read_text())["indicators"]
    entries = {(entry["plugin"], entry["name"]) for entry in indicators}
    assert len(entries) == len(indicators)
    assert {
        ("RSFC", "has_contribution_guidelines"),
        ("RSFC", "requirements_specified"),
        ("RSFC", "archived_in_scholarly_repository"),
        ("OEBFAIR", "listed_in_registry"),
        ("OEBFAIR", "repository_workflows"),
        ("HowFairIs", "software_has_license_for_file_types"),
        ("OpenSSFScorecard", "no_critical_vulnerability"),
        ("OpenSSFScorecard", "has_no_binary_artifacts"),
    }.issubset(entries)
    assert not any(plugin == "PySCN" for plugin, _ in entries)


def test_configured_methods_exist_in_installed_resqui():
    plugins = pytest.importorskip("resqui.plugins")
    for indicator in json.loads(CONFIG.read_text())["indicators"]:
        plugin = getattr(plugins, indicator["plugin"])
        assert indicator["name"] in plugin.indicators
        assert callable(getattr(plugin, indicator["name"]))


def test_missing_checks_are_logged(tmp_path, monkeypatch, caplog):
    from maturity_meter.external.ingestors import resqui

    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "indicators": [
                    {"plugin": "OpenSSFScorecard", "name": "has_ci_tests", "@id": "ci"},
                    {"plugin": "RSFC", "name": "has_releases", "@id": "release"},
                ]
            }
        )
    )
    assessment = {
        "checks": [
            {
                "checkingSoftware": {"name": "OpenSSF Scorecard"},
                "assessesIndicator": {"@id": "ci"},
            }
        ]
    }
    monkeypatch.setattr(resqui.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(resqui, "_remove_containers", AsyncMock())

    # Each plugin runs separately; a failed plugin is skipped, not fatal.
    async def run(self, workdir, env, plugin, config):
        if plugin == "RSFC":
            raise resqui.ResquiError("RSFC crashed")
        return assessment

    monkeypatch.setattr(resqui.ResquiIngestor, "_run", run)
    with caplog.at_level(logging.WARNING, logger=resqui.__name__):
        result = asyncio.run(
            resqui.ResquiIngestor("https://github.com/x/y", config=config).fetch()
        )
    assert result == assessment
    assert "Skipping resqui plugin RSFC: RSFC crashed" in caplog.text
    assert "RSFC.has_releases" in caplog.text
    assert "OpenSSFScorecard.has_ci_tests" not in caplog.text


def test_resqui_reports_partial_errors_without_confusing_failed_scores(
    tmp_path, monkeypatch, caplog
):
    from maturity_meter.external.ingestors import resqui

    script = tmp_path / "fake-resqui"
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "print('  check/Plugin ✖ ')\n"
        "print('  other/Plugin ✖ RuntimeError: failed with secret-token')\n"
        "with open(sys.argv[sys.argv.index('-o') + 1], 'w') as f:\n"
        "    json.dump({'checks': []}, f)\n"
    )
    script.chmod(0o755)
    monkeypatch.setattr(resqui, "_executable", lambda: str(script))
    with caplog.at_level(logging.WARNING, logger=resqui.__name__):
        result = asyncio.run(
            resqui.ResquiIngestor(
                "https://github.com/x/y", github_token="secret-token"
            )._run(tmp_path, {}, "Plugin", tmp_path / "config.json")
        )
    assert result == {"checks": []}
    assert "RuntimeError: failed with [redacted]" in caplog.text
    assert "secret-token" not in caplog.text
    assert "check/Plugin" not in caplog.text


def test_resqui_error_reports_stdout_if_stderr_empty(tmp_path, monkeypatch):
    from maturity_meter.external.ingestors import resqui

    script = tmp_path / "fake-resqui"
    script.write_text(
        f"#!{sys.executable}\nimport sys\nprint('Error: no space left')\nsys.exit(1)\n"
    )
    script.chmod(0o755)
    monkeypatch.setattr(resqui, "_executable", lambda: str(script))
    with pytest.raises(resqui.ResquiError, match="Error: no space left"):
        asyncio.run(
            resqui.ResquiIngestor("https://github.com/x/y")._run(
                tmp_path, {}, "Plugin", tmp_path / "config.json"
            )
        )


@pytest.mark.parametrize("mirror", [None, "mirror.git"])
def test_resqui_clones_from_mirror_when_given(tmp_path, monkeypatch, mirror):
    from maturity_meter.external.ingestors import resqui

    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"indicators": [{"plugin": "RSFC", "name": "x", "@id": "x"}]})
    )
    monkeypatch.setattr(resqui.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(resqui, "_remove_containers", AsyncMock())
    envs = []

    async def run(self, workdir, env, plugin, config):
        envs.append(env)
        return {"checks": []}

    monkeypatch.setattr(resqui.ResquiIngestor, "_run", run)
    mirror_path = tmp_path / mirror if mirror else None
    url = "https://github.com/x/y"
    asyncio.run(resqui.ResquiIngestor(url, config=config, mirror=mirror_path).fetch())
    if mirror_path is None:
        assert "GIT_CONFIG_COUNT" not in envs[0]
    else:
        assert envs[0]["GIT_CONFIG_KEY_0"] == f"url.{mirror_path}.insteadOf"
        assert envs[0]["GIT_CONFIG_VALUE_0"] == url
