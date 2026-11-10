"""
Async client for the OpenEBench Tools Monitoring API.
Fetches a tool record and its metrics by bio.tools ID and returns the raw JSON.
"""

import logging
from typing import Any

import httpx

from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

OPENEBENCH_API_BASE = "https://openebench.bsc.es/monitor"
HTTP_TIMEOUT_SECONDS = 15


class OpenEBenchIngestor(Ingestor):
    """
    Ingest a tool's OpenEBench record and metrics via the Tools Monitoring API.

    Parameters
    ----------
    biotools_id : str
        The bio.tools identifier of the tool (e.g. ``"samtools"``).
    """

    def __init__(self, biotools_id: str):
        self.biotools_id = biotools_id

    async def _get(self, path: str) -> dict[str, Any]:
        url = f"{OPENEBENCH_API_BASE}/{path}"
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                return data
        except httpx.RequestError as e:
            logger.error(f"Network error while fetching {url}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} from {url}")
            raise

    async def fetch_tool(self) -> dict[str, Any]:
        """
        Fetch the OpenEBench tool record.

        Returns
        -------
        dict
            Raw JSON for the tool from GET /tool/biotools:{id}. When several
            versions or deployments exist, OpenEBench returns the first match.

        Raises
        ------
        httpx.HTTPStatusError
            With status 404 if OpenEBench does not know the tool.
        """
        logger.debug(f"Fetching OpenEBench tool biotools:{self.biotools_id}")
        return await self._get(f"tool/biotools:{self.biotools_id}")

    async def fetch_metrics(self, tool: dict[str, Any]) -> dict[str, Any] | None:
        """
        Fetch the metrics of a tool record, or None if it has none.

        Parameters
        ----------
        tool : dict
            Tool record from :meth:`fetch_tool`. The metrics endpoint needs
            the record's full identifier, not the short bio.tools form.

        Returns
        -------
        dict | None
            Raw JSON from GET /metrics/{id}, or None when absent.
        """
        tool_id = str(tool.get("@id", ""))
        prefix = f"{OPENEBENCH_API_BASE}/tool/"
        if not tool_id.startswith(prefix):
            logger.info(f"OpenEBench tool {self.biotools_id} has no usable @id")
            return None
        try:
            return await self._get(f"metrics/{tool_id.removeprefix(prefix)}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"No OpenEBench metrics for {self.biotools_id}")
                return None
            raise

    async def fetch(self) -> dict[str, Any]:
        """
        Fetch the tool record and its metrics.

        Returns
        -------
        dict
            ``{"tool": <tool record>, "metrics": <metrics or None>}``.

        Raises
        ------
        httpx.HTTPStatusError, httpx.RequestError
            If the tool is unknown or OpenEBench cannot be reached.
        """
        tool = await self.fetch_tool()
        metrics = await self.fetch_metrics(tool)
        logger.info(f"Ingested OpenEBench data for {self.biotools_id} successfully")
        return {"tool": tool, "metrics": metrics}
