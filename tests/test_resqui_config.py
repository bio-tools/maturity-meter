"""Verify the bundled resqui indicator configuration."""

import json
from pathlib import Path


def test_fairchecker_indicators():
    config = (
        Path(__file__).resolve().parents[1]
        / "src/maturity_meter/external/ingestors/resqui_config.json"
    )
    indicators = json.loads(config.read_text())["indicators"]
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
