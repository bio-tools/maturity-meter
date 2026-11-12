"""Tests for direct FAIR-Checker ingestion and saved-data reuse."""

import asyncio
import json

import httpx
import pytest

from maturity_meter.external.ingestors import fairchecker
from maturity_meter.models import EvaluationRequest, IngestedData
from maturity_meter.services import ingestion

URL = "https://github.com/example/tool"


def assessment(score=0):
    return [
        {
            "@type": ["https://w3id.org/ftr#TestResult"],
            "https://w3id.org/ftr#outputFromTest": [
                {"@id": "https://fair-checker.example/test/F1A"}
            ],
            "http://www.w3.org/ns/prov#value": [{"@value": score}],
        }
    ]


def test_fetch_uses_official_api_and_preserves_raw_data(monkeypatch):
    async def get(url, **kwargs):
        assert url == fairchecker.FAIRCHECKER_API_URL
        assert kwargs["params"] == {"url": URL}
        assert kwargs["timeout"] == 300
        return assessment(2)

    monkeypatch.setattr(fairchecker, "get_json", get)
    assert asyncio.run(fairchecker.FairCheckerIngestor(URL).fetch()) == assessment(2)


@pytest.mark.parametrize("response", [{}, [], "bad", [{"@type": []}]])
def test_invalid_response_is_reported(monkeypatch, response):
    async def get(*args, **kwargs):
        return response

    monkeypatch.setattr(fairchecker, "get_json", get)
    with pytest.raises(fairchecker.FairCheckerError, match="invalid assessment"):
        asyncio.run(fairchecker.FairCheckerIngestor(URL).fetch())


def test_invalid_json_is_reported(monkeypatch):
    async def get(*args, **kwargs):
        raise json.JSONDecodeError("bad", "", 0)

    monkeypatch.setattr(fairchecker, "get_json", get)
    with pytest.raises(fairchecker.FairCheckerError, match="invalid JSON"):
        asyncio.run(fairchecker.FairCheckerIngestor(URL).fetch())


@pytest.mark.parametrize("test_id", ["https://example.org/test/None", ""])
def test_missing_test_identifiers_are_rejected(monkeypatch, test_id):
    async def get(*args, **kwargs):
        data = assessment()
        data[0]["https://w3id.org/ftr#outputFromTest"][0]["@id"] = test_id
        return data

    monkeypatch.setattr(fairchecker, "get_json", get)
    with pytest.raises(fairchecker.FairCheckerError, match="missing or duplicate"):
        asyncio.run(fairchecker.FairCheckerIngestor(URL).fetch())


def test_duplicate_test_identifiers_are_rejected(monkeypatch):
    async def get(*args, **kwargs):
        return assessment(0) + assessment(2)

    monkeypatch.setattr(fairchecker, "get_json", get)
    with pytest.raises(fairchecker.FairCheckerError, match="missing or duplicate"):
        asyncio.run(fairchecker.FairCheckerIngestor(URL).fetch())


def supplied(fair_checker=None):
    return {
        "repository": {},
        "quality_checks": {"checks": []},
        "code_metrics": {},
        "fair_checker": fair_checker,
    }


def test_ingestion_fetch_save_reload_and_reuse(monkeypatch, tmp_path):
    calls = []

    async def fetch(self):
        calls.append(self.repository_url)
        return assessment()

    monkeypatch.setattr(ingestion.FairCheckerIngestor, "fetch", fetch)
    request = EvaluationRequest(repository=URL, data=supplied())
    data = asyncio.run(ingestion._ingest(request, None))
    assert data.fair_checker == assessment()
    assert calls == [URL]
    path = tmp_path / "data.json"
    data.save(path)
    assert IngestedData.load(path).fair_checker == assessment()
    reused = EvaluationRequest(repository=URL, data=json.loads(path.read_text()))
    assert asyncio.run(ingestion._ingest(reused, None)).fair_checker == assessment()
    assert calls == [URL]


def test_api_failure_is_optional_and_logged(monkeypatch, caplog):
    async def fetch(self):
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(ingestion.FairCheckerIngestor, "fetch", fetch)
    data = asyncio.run(
        ingestion._ingest(EvaluationRequest(repository=URL, data=supplied()), None)
    )
    assert data.fair_checker is None
    assert "Skipping FAIR-Checker: unavailable" in caplog.text


def test_old_saved_data_is_loadable(tmp_path):
    data = IngestedData(request=EvaluationRequest(repository=URL), repository={})
    old = json.loads(data.to_json())
    del old["fair_checker"]
    path = tmp_path / "old.json"
    path.write_text(json.dumps(old))
    assert IngestedData.load(path).fair_checker is None
