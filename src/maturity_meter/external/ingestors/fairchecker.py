"""Fetch the official FAIR-Checker API's raw JSON-LD assessment."""

import logging
from typing import Any

from maturity_meter.external.http import get_json

logger = logging.getLogger(__name__)

FAIRCHECKER_API_URL = (
    "https://fair-checker.france-bioinformatique.fr/api/check/metrics_all"
)
HTTP_TIMEOUT_SECONDS = 300


class FairCheckerError(Exception):
    """The FAIR-Checker API returned an invalid assessment."""


class FairCheckerIngestor:
    """Fetch FAIR-Checker's reported test results for a repository URL."""

    def __init__(self, repository_url: str):
        self.repository_url = repository_url

    async def fetch(self) -> list[dict[str, Any]]:
        """Return the raw JSON-LD assessment without calculating scores."""
        logger.info("Fetching FAIR-Checker data for %s", self.repository_url)
        try:
            response = await get_json(
                FAIRCHECKER_API_URL,
                params={"url": self.repository_url},
                headers={"Accept": "application/json"},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
        except ValueError as error:
            raise FairCheckerError("FAIR-Checker returned invalid JSON") from error
        if (
            not isinstance(response, list)
            or not all(isinstance(node, dict) for node in response)
            or not all(isinstance(node.get("@type", []), list) for node in response)
            or not any(
                "https://w3id.org/ftr#TestResult" in node.get("@type", [])
                for node in response
            )
        ):
            raise FairCheckerError("FAIR-Checker returned an invalid assessment")
        identifiers: set[str] = set()
        for node in response:
            if "https://w3id.org/ftr#TestResult" not in node.get("@type", []):
                continue
            tests = node.get("https://w3id.org/ftr#outputFromTest")
            if (
                not isinstance(tests, list)
                or len(tests) != 1
                or not isinstance(tests[0], dict)
            ):
                raise FairCheckerError("FAIR-Checker returned an invalid test ID")
            test_id = tests[0].get("@id")
            if (
                not isinstance(test_id, str)
                or "/test/" not in test_id
                or test_id.rsplit("/test/", 1)[-1] in ("", "None")
                or test_id.rsplit("/test/", 1)[-1] in identifiers
            ):
                raise FairCheckerError(
                    f"FAIR-Checker returned a missing or duplicate test ID: {test_id}"
                )
            identifiers.add(test_id.rsplit("/test/", 1)[-1])
        logger.info(
            "Ingested %s FAIR-Checker tests for %s",
            len(identifiers),
            self.repository_url,
        )
        return response
