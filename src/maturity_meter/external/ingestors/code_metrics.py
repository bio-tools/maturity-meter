"""
Source-code metrics with Lizard (https://github.com/terryyin/lizard).
Analyses a local checkout of the repository and computes
cyclomatic complexity, lines of code and the duplicate-code rate, following
the FAIR Toolbox maturity model's analyzer.
"""

import asyncio
import contextlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import lizard
from lizard_ext.lizardduplicate import LizardExtension

from maturity_meter.config import get_settings
from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

_WORKER_COMMAND = (
    "from maturity_meter.external.ingestors.code_metrics import _worker; _worker()"
)
_MEMORY_LIMIT_EXIT_CODE = 2


class CodeMetricsError(Exception):
    """Raised when the repository cannot be analysed."""


async def _run_scan(scan: str, checkout: Path) -> Any:
    """Run a single scan in a subprocess and read its compact result."""
    settings = get_settings()
    timeout = settings.lizard_timeout_seconds
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        _WORKER_COMMAND,
        scan,
        str(checkout),
        str(settings.lizard_memory_mib),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    output = asyncio.create_task(process.communicate())
    try:
        stdout, _ = await asyncio.wait_for(asyncio.shield(output), timeout=timeout)
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await output
        raise
    if process.returncode == _MEMORY_LIMIT_EXIT_CODE:
        raise CodeMetricsError(
            f"Lizard {scan} scan ran out of memory "
            f"(configured limit: {settings.lizard_memory_mib} MiB)"
        )
    if process.returncode != 0:
        raise CodeMetricsError(f"Lizard {scan} scan exited with {process.returncode}")
    try:
        return json.loads(stdout)
    except ValueError as error:
        raise CodeMetricsError(f"Lizard {scan} scan returned invalid JSON") from error


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


def _duplicate_rate(path: Path) -> float:
    """Compute the percentage reported by Lizard's duplicate-code extension."""
    duplicate = LizardExtension()
    extensions = lizard.get_extensions([duplicate])
    for _ in lizard.analyze([str(path)], exts=extensions):
        pass
    for _ in duplicate.get_duplicates():
        pass
    return float(f"{duplicate.duplicate_rate() * 100:.2f}")


def _worker() -> None:
    """Apply the memory limit in the child before opening repository files."""
    scan, path, memory_mib = sys.argv[1:]
    if sys.platform == "linux":
        import resource

        limit = int(memory_mib) * 1024**2
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        if soft != resource.RLIM_INFINITY:
            limit = min(limit, soft)
        resource.setrlimit(resource.RLIMIT_AS, (limit, hard))
    try:
        checkout = Path(path)
        result: dict[str, Any] | float
        with contextlib.redirect_stdout(sys.stderr):
            if scan == "complexity":
                result = _complexity(checkout)
            else:
                result = _duplicate_rate(checkout)
        print(json.dumps(result))
    except MemoryError:
        raise SystemExit(_MEMORY_LIMIT_EXIT_CODE) from None


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
            complexity = await _run_scan("complexity", self.checkout)
        except TimeoutError as error:
            raise CodeMetricsError("Lizard complexity scan timed out") from error
        try:
            duplicate_rate = await _run_scan("duplicate-code", self.checkout)
        except TimeoutError:
            logger.warning("Lizard duplicate-code scan timed out")
            duplicate_rate = None
        except CodeMetricsError as error:
            logger.warning("Skipping duplicate-code rate: %s", error)
            duplicate_rate = None
        metrics = {**complexity, "duplicate_rate": duplicate_rate}
        logger.info(f"Computed code metrics for {self.checkout}")
        return metrics
