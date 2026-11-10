"""
Async client for the OpenEBench Tools Monitoring API.
Fetches a tool record and its metrics by bio.tools ID and returns the raw JSON.
"""

import logging
from typing import Any

from maturity_meter.external.http import get_json, get_json_optional
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

    async def _get(self, path: str, *, optional: bool = False) -> Any:
        url = f"{OPENEBENCH_API_BASE}/{path}"
        headers = {"Accept": "application/json"}
        if optional:
            return await get_json_optional(
                url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS
            )
        return await get_json(url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)

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
        tool: dict[str, Any] = await self._get(f"tool/biotools:{self.biotools_id}")
        return tool

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
        metrics: dict[str, Any] | None = await self._get(
            f"metrics/{tool_id.removeprefix(prefix)}", optional=True
        )
        if metrics is None:
            logger.info(f"No OpenEBench metrics for {self.biotools_id}")
        return metrics

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
