"""
Source-code metrics with Lizard (https://github.com/terryyin/lizard).
Shallow-clones the repository, or analyses a local checkout, and computes
cyclomatic complexity, lines of code and the duplicate-code rate, following
the FAIR Toolbox maturity model's analyzer.
"""

import asyncio
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import lizard

from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

CLONE_TIMEOUT_SECONDS = 300
DUPLICATES_TIMEOUT_SECONDS = 300
_DUPLICATE_RATE = re.compile(r"Total duplicate rate:\s+([\d.]+)%")


class CodeMetricsError(Exception):
    """Raised when the repository cannot be cloned or analysed."""


async def _run(command: list[str], timeout: float) -> tuple[int, str]:
    """Run a command, returning its exit code and standard output."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        # Never let git stop to ask for credentials (e.g. a missing repo).
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
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
    repository_url : str
        Repository to shallow-clone when no ``checkout`` is given.
    checkout : pathlib.Path, optional
        Existing local checkout to analyse instead of cloning.
    """

    def __init__(self, repository_url: str, checkout: Path | None = None):
        self.repository_url = repository_url
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

    async def _analyse(self, path: Path) -> dict[str, Any]:
        complexity, duplicate_rate = await asyncio.gather(
            asyncio.to_thread(_complexity, path), self._duplicate_rate(path)
        )
        return {**complexity, "duplicate_rate": duplicate_rate}

    async def fetch(self) -> dict[str, Any]:
        """
        Clone (if needed) and analyse the repository.

        Returns
        -------
        dict
            ``files``, ``functions``, ``total_nloc``, ``total_ccn``,
            ``avg_ccn`` and ``nloc_per_file`` (None without functions or
            files), and ``duplicate_rate`` in percent (None if unavailable).

        Raises
        ------
        CodeMetricsError
            If the repository cannot be cloned.
        """
        if self.checkout is not None:
            return await self._analyse(self.checkout)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repository"
            try:
                code, _ = await _run(
                    [
                        "git",
                        "clone",
                        "--quiet",
                        "--depth",
                        "1",
                        "--",
                        self.repository_url,
                        str(path),
                    ],
                    CLONE_TIMEOUT_SECONDS,
                )
            except TimeoutError as error:
                raise CodeMetricsError(
                    f"Cloning {self.repository_url} timed out"
                ) from error
            except FileNotFoundError as error:
                raise CodeMetricsError("git was not found") from error
            if code != 0:
                raise CodeMetricsError(f"Could not clone {self.repository_url}")
            metrics = await self._analyse(path)
        logger.info(f"Computed code metrics for {self.repository_url}")
        return metrics
