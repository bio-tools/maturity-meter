import asyncio
import sys

import pytest

from maturity_meter.config import Settings
from maturity_meter.external.ingestors import code_metrics
from maturity_meter.services.ingestion import _optional


def test_lizard_subprocesses_preserve_code_metrics(tmp_path):
    (tmp_path / "tool.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    assert asyncio.run(code_metrics.CodeMetricsIngestor(tmp_path).fetch()) == {
        "files": 1,
        "functions": 1,
        "total_nloc": 2,
        "total_ccn": 1,
        "avg_ccn": 1.0,
        "nloc_per_file": 2.0,
        "duplicate_rate": 0.0,
    }


@pytest.mark.skipif(sys.platform != "linux", reason="address-space limit is Linux-only")
def test_lizard_memory_failure_is_optional(tmp_path, monkeypatch, caplog):
    (tmp_path / "large.py").write_bytes(b"#" * (8 * 1024**2))
    settings = Settings(lizard_memory_mib=1)
    monkeypatch.setattr(code_metrics, "get_settings", lambda: settings)

    metrics = asyncio.run(
        _optional("code metrics", code_metrics.CodeMetricsIngestor(tmp_path).fetch())
    )

    assert metrics is None
    assert "Lizard complexity scan ran out of memory" in caplog.text


def test_lizard_timeout_stops_worker(tmp_path, monkeypatch):
    settings = Settings(lizard_timeout_seconds=1)
    monkeypatch.setattr(code_metrics, "get_settings", lambda: settings)
    monkeypatch.setattr(code_metrics, "_WORKER_COMMAND", "import time; time.sleep(30)")

    with pytest.raises(code_metrics.CodeMetricsError, match="scan timed out"):
        asyncio.run(code_metrics.CodeMetricsIngestor(tmp_path).fetch())
