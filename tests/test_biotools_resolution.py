"""Tests for bio.tools ID-only evaluation."""

import asyncio
import json

import httpx
import pytest
from typer.testing import CliRunner

from maturity_meter.adapters.cli.app import app
from maturity_meter.adapters.cli.commands import evaluate
from maturity_meter.config import Settings
from maturity_meter.models import IngestedData, SuppliedData
from maturity_meter.services import batch, ingestion
from maturity_meter.services.biotools_resolution import (
    BiotoolsResolutionError,
    resolve_biotools,
)


def entry():
    return {
        "name": "Example",
        "homepage": "https://example.org/tool",
        "link": [
            {"url": "https://github.com/example/project/releases"},
            {"url": "https://github.com/example/project"},
            {"url": "https://gitlab.com/group/other"},
        ],
        "publication": [
            {"doi": "https://doi.org/10.1000/a"},
            {"doi": "doi:10.1000/a"},
            {"doi": "10.1000/b"},
        ],
    }


def test_resolution_uses_first_root_and_publications(monkeypatch):
    seen = []

    async def fetch(self):
        seen.append(self.biotools_id)
        return entry()

    monkeypatch.setattr(
        "maturity_meter.services.biotools_resolution.BiotoolsIngestor.fetch", fetch
    )
    request = asyncio.run(resolve_biotools("example", dois=["10.1000/c"]))
    assert seen == ["example"]
    assert request.repository == "https://github.com/example/project"
    assert request.dois == ["10.1000/c", "10.1000/a", "10.1000/b"]
    assert request.data.biotools == entry()


def test_supplied_entry_is_reused_and_homepage_first(monkeypatch):
    record = entry() | {"homepage": "https://gitlab.com/a/sub/project"}

    async def fetch(self):
        pytest.fail("supplied bio.tools entry should be reused")

    monkeypatch.setattr(
        "maturity_meter.services.biotools_resolution.BiotoolsIngestor.fetch", fetch
    )
    request = asyncio.run(
        resolve_biotools("example", data=SuppliedData(biotools=record))
    )
    assert request.repository == "https://gitlab.com/a/sub/project"


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"homepage": "https://example.org", "link": []}, "No supported"),
        (entry() | {"publication": [{"doi": "not-a-doi"}]}, "Invalid publication DOI"),
        (entry() | {"publication": "bad"}, "Invalid publications"),
    ],
)
def test_resolution_rejects_bad_entries(record, message):
    with pytest.raises(BiotoolsResolutionError, match=message):
        asyncio.run(resolve_biotools("example", data=SuppliedData(biotools=record)))


def test_resolution_reports_api_failure(monkeypatch):
    async def fetch(self):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(
        "maturity_meter.services.biotools_resolution.BiotoolsIngestor.fetch", fetch
    )
    with pytest.raises(BiotoolsResolutionError, match="offline"):
        asyncio.run(resolve_biotools("example"))


def test_pmid_only_publications_use_europe_pmc_and_reuse_record(monkeypatch, caplog):
    async def fetch(self):
        if self.pmid == "11":
            return {"doi": "10.1000/resolved", "id": "11"}
        return {"id": self.pmid}

    monkeypatch.setattr(
        "maturity_meter.services.biotools_resolution.EuropePMCIngestor.fetch", fetch
    )
    record = entry() | {"publication": [{"pmid": "11"}, {"pmid": "12"}]}
    request = asyncio.run(
        resolve_biotools("example", data=SuppliedData(biotools=record))
    )
    assert request.dois == ["10.1000/resolved"]
    assert request.data.europe_pmc["10.1000/resolved"]["id"] == "11"
    assert "has no DOI in Europe PMC" in caplog.text


def test_cli_id_only_and_existing_repository(monkeypatch):
    calls = []

    async def fetch(self):
        return entry()

    monkeypatch.setattr(
        "maturity_meter.services.biotools_resolution.BiotoolsIngestor.fetch", fetch
    )
    monkeypatch.setattr(
        evaluate,
        "run",
        lambda request, output, save_data: calls.append(request) or "{}",
    )
    runner = CliRunner()
    result = runner.invoke(app, ["evaluate", "--biotools-id", "example"])
    assert result.exit_code == 0, result.output
    assert calls[-1].repository == "https://github.com/example/project"
    assert calls[-1].dois == ["10.1000/a", "10.1000/b"]
    result = runner.invoke(
        app,
        ["evaluate", "https://github.com/other/project", "--biotools-id", "example"],
    )
    assert result.exit_code == 0, result.output
    assert calls[-1].repository == "https://github.com/other/project"
    assert calls[-1].dois == []
    assert runner.invoke(app, ["evaluate"]).exit_code != 0
    invalid = runner.invoke(app, ["evaluate", "--biotools-id", "../bad"])
    assert invalid.exit_code != 0 and "Invalid bio.tools ID" in invalid.output


def test_resolved_dois_are_fetched_and_entry_not_fetched_twice(monkeypatch):
    pmc_calls = []
    alex_calls = []

    async def fetch_entry(self):
        return entry()

    async def fetch_pmc(self):
        pmc_calls.append(self.doi)
        return {"doi": self.doi}

    async def fetch_alex(self):
        alex_calls.extend(self.dois)
        return {doi: {"doi": doi} for doi in self.dois}

    monkeypatch.setattr(
        "maturity_meter.services.biotools_resolution.BiotoolsIngestor.fetch",
        fetch_entry,
    )
    monkeypatch.setattr(ingestion.EuropePMCIngestor, "fetch", fetch_pmc)
    monkeypatch.setattr(ingestion.OpenAlexIngestor, "fetch", fetch_alex)
    supplied = SuppliedData(
        repository={},
        openebench={},
        quality_checks={},
        fair_checker=[],
        rsec={},
        code_metrics={},
    )
    request = asyncio.run(resolve_biotools("example", data=supplied))

    async def fail_if_refetched(self):
        pytest.fail("bio.tools entry was fetched twice")

    monkeypatch.setattr(ingestion.BiotoolsIngestor, "fetch", fail_if_refetched)
    data = asyncio.run(ingestion._ingest(request, None))
    assert pmc_calls == ["10.1000/a", "10.1000/b"]
    assert alex_calls == pmc_calls
    assert data.biotools == entry()
    assert set(data.europe_pmc) == set(pmc_calls)


def test_batch_ids_resolve_and_resume(tmp_path, monkeypatch):
    source = tmp_path / "ids.txt"
    source.write_text("example\nsecond\n")
    seen = []
    requests = []

    async def ingest(request):
        requests.append(request)
        return IngestedData(request=request, repository={})

    monkeypatch.setattr(batch, "ingest", ingest)
    monkeypatch.setattr(batch, "get_settings", lambda: Settings(_env_file=None))

    async def fetch(self):
        seen.append(self.biotools_id)
        return entry()

    monkeypatch.setattr(
        "maturity_meter.services.biotools_resolution.BiotoolsIngestor.fetch", fetch
    )
    output = tmp_path / "out"
    runner = CliRunner()
    args = ["batch", str(source), "--ids", "-o", str(output)]
    plan = runner.invoke(app, [*args, "--dry-run"])
    assert plan.exit_code == 0 and not output.exists()
    assert "bio.tools:example" in plan.output
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert seen == ["example", "second"]
    assert requests[0].dois == ["10.1000/a", "10.1000/b"]
    assert requests[0].data.biotools == entry()
    assert (
        json.loads((output / "raw/example.json").read_text())["request"]["biotools_id"]
        == "example"
    )
    again = runner.invoke(app, args)
    assert again.exit_code == 0 and "from saved data: 2" in again.stdout
    assert len(seen) == 2
    refill = runner.invoke(app, [*args, "--fill-missing"])
    assert refill.exit_code == 0, refill.output
    assert len(seen) == 2


def test_id_file_invalid_duplicate_and_empty(tmp_path):
    source = tmp_path / "ids.txt"
    source.write_text("one\nONE\n../bad\n")
    rows = batch.read_ids(source)
    assert rows[0].item is not None
    assert "duplicate" in rows[1].error
    assert "Invalid bio.tools ID" in rows[2].error
    source.write_text("\n")
    with pytest.raises(ValueError, match="no bio.tools IDs"):
        batch.read_ids(source)


def test_failed_id_does_not_stop_batch(tmp_path, monkeypatch):
    async def fetch(self):
        if self.biotools_id == "bad":
            raise httpx.ConnectError("offline")
        return entry()

    async def ingest(request):
        return IngestedData(request=request, repository={})

    monkeypatch.setattr(
        "maturity_meter.services.biotools_resolution.BiotoolsIngestor.fetch", fetch
    )
    monkeypatch.setattr(batch, "ingest", ingest)
    monkeypatch.setattr(batch, "get_settings", lambda: Settings(_env_file=None))
    source = tmp_path / "ids.txt"
    source.write_text("bad\ngood\n")
    output = tmp_path / "out"
    result = CliRunner().invoke(app, ["batch", str(source), "--ids", "-o", str(output)])
    assert result.exit_code == 1
    assert "offline" in result.output
    assert not (output / "raw/bad.json").exists()
    assert (output / "raw/good.json").exists()
