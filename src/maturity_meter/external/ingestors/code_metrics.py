"""
Source-code metrics with Lizard (https://github.com/terryyin/lizard).
Analyses a local checkout of the repository and computes
cyclomatic complexity, lines of code and the duplicate-code rate, following
the FAIR Toolbox maturity model's analyzer.
"""

import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Any

import lizard

from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

DUPLICATES_TIMEOUT_SECONDS = 300
_DUPLICATE_RATE = re.compile(r"Total duplicate rate:\s+([\d.]+)%")


class CodeMetricsError(Exception):
    """Raised when the repository cannot be analysed."""


async def _run(command: list[str], timeout: float) -> tuple[int, str]:
    """Run a command, returning its exit code and standard output."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except BaseException:
        process.kill()
        await process.wait()
        raise
    return process.returncode or 0, stdout.decode(errors="replace")


def _complexity(path: Path) -> dict[str, Any]:
    """Compute complexity and size metrics with the Lizard API."""
    total_nloc = total_ccn = functions = files = 0
    for file_result in lizard.analyze([str(path)]):
        files += 1
        for function in file_result.function_list:
            total_nloc += function.nloc
            total_ccn += function.cyclomatic_complexity
            functions += 1
    return {
        "files": files,
        "functions": functions,
        "total_nloc": total_nloc,
        "total_ccn": total_ccn,
        "avg_ccn": round(total_ccn / functions, 2) if functions else None,
        "nloc_per_file": round(total_nloc / files, 2) if files else None,
    }


class CodeMetricsIngestor(Ingestor):
    """
    Compute source-code metrics for a repository.

    Parameters
    ----------
    checkout : pathlib.Path
        Local checkout of the repository to analyse.
    """

    def __init__(self, checkout: Path):
        self.checkout = checkout

    async def _duplicate_rate(self, path: Path) -> float | None:
        """Duplicate-code rate (%) from Lizard's ``-Eduplicate`` extension."""
        try:
            _, output = await _run(
                [sys.executable, "-m", "lizard", "-Eduplicate", str(path)],
                DUPLICATES_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning("Duplicate-code analysis timed out")
            return None
        match = _DUPLICATE_RATE.search(output)
        return float(match.group(1)) if match else None

    async def fetch(self) -> dict[str, Any]:
        """
        Analyse the checkout.

        Returns
        -------
        dict
            ``files``, ``functions``, ``total_nloc``, ``total_ccn``,
            ``avg_ccn`` and ``nloc_per_file`` (None without functions or
            files), and ``duplicate_rate`` in percent (None if unavailable).

        Raises
        ------
        CodeMetricsError
            If the analysis fails.
        """
        try:
            complexity, duplicate_rate = await asyncio.gather(
                asyncio.to_thread(_complexity, self.checkout),
                self._duplicate_rate(self.checkout),
            )
        except Exception as error:
            # Lizard can fail on unusual source files; report it as this
            # source being unavailable rather than failing the evaluation.
            raise CodeMetricsError(f"Code analysis failed: {error!r}") from error
        metrics = {**complexity, "duplicate_rate": duplicate_rate}
        logger.info(f"Computed code metrics for {self.checkout}")
        return metrics
