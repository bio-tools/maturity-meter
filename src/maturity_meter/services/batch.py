"""Batch evaluation service: evaluate many tools in one process.

Tools come from a bio.tools CSV export with ``biotoolsID``, ``homepage``
(repository URL) and ``dois`` (comma-separated) columns. Each tool's ingested
data is saved as soon as it is complete, then scored, and its result saved.
Tools that already have a data file are not fetched again: their saved data is
scored (or, on request, only their missing sources are fetched), so an
interrupted batch resumes where it stopped, and re-running a batch re-scores
every tool in seconds after the scoring changes.

A batch is more efficient than evaluating the tools one by one:

- Several tools are in progress at once (``jobs``, by default
  ``MATURITY_METER_BATCH_JOBS``), so the quick, network-bound
  sources of one tool overlap with the slow Docker checks of another.
- The resqui checks of all tools share one limit on resqui processes
  (``MATURITY_METER_RESQUI_PARALLEL``, by default one tool's worth), which keeps
  Docker busy without overloading it however many tools are in progress.
- All requests share one HTTP connection pool.
- Before starting a GitHub tool, the batch waits for GitHub's rate limit to
  reset if few requests are left, instead of letting sources fail.

Each tool's log is written to its own file, so the logs of tools running at the
same time do not mix.
"""

import asyncio
import contextlib
import csv
import json
import logging
import os
import re
import tempfile
import time
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from maturity_meter.config import get_settings
from maturity_meter.external.http import get_json, shared_client
from maturity_meter.external.ingestors.resqui import plugin_count, shared_limit
from maturity_meter.logging_config import LOG_FORMAT
from maturity_meter.models import EvaluationRequest, IngestedData
from maturity_meter.services.ingestion import ingest
from maturity_meter.services.processing import score

logger = logging.getLogger(__name__)

# GitHub requests that must be left before a GitHub tool starts; one tool's
# sources and resqui checks (Scorecard in particular) can use hundreds.
GITHUB_RESERVE = 500
REQUIRED_COLUMNS = frozenset({"biotoolsID", "homepage", "dois"})
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.IGNORECASE)


class SkippedURL(ValueError):
    """The homepage points inside a repository instead of to its root."""


@dataclass(frozen=True)
class BatchItem:
    """One valid CSV row, ready to evaluate.

    Attributes
    ----------
    row : int
        CSV line number (the header is line 1).
    biotools_id : str
        bio.tools identifier.
    request : EvaluationRequest
        Evaluation request for the tool.
    """

    row: int
    biotools_id: str
    request: EvaluationRequest

    @property
    def stem(self) -> str:
        """File name stem shared by the tool's data and log files."""
        return f"{self.row:04d}-{self.biotools_id}"


@dataclass(frozen=True)
class BatchRow:
    """One CSV row: a valid item, or the reason it is not evaluated.

    Attributes
    ----------
    row : int
        CSV line number (the header is line 1).
    item : BatchItem | None
        The tool to evaluate, if the row is valid.
    skipped : str | None
        Why the row is deliberately not evaluated (a URL inside a repository).
    error : str | None
        Why the row is invalid.
    """

    row: int
    item: BatchItem | None = None
    skipped: str | None = None
    error: str | None = None


EventKind = Literal[
    "invalid", "skip_url", "plan", "scored", "start", "wait", "done", "failed"
]


@dataclass(frozen=True)
class BatchEvent:
    """Progress of a batch, reported as it happens.

    Attributes
    ----------
    kind : str
        ``invalid`` or ``skip_url`` (row not evaluated), ``plan`` (dry run),
        ``scored`` (from saved data, without fetching), ``start`` and ``done``
        (fetched and scored), ``failed`` (one tool), or ``wait`` (for GitHub's
        rate limit).
    row : int | None
        CSV line number, if the event concerns one row.
    biotools_id : str
        bio.tools identifier, or an empty string.
    message : str
        Details: the repository URL, an error, or the wait.
    seconds : float | None
        Duration of a finished evaluation, or of a wait.
    """

    kind: EventKind
    row: int | None = None
    biotools_id: str = ""
    message: str = ""
    seconds: float | None = None


@dataclass
class BatchSummary:
    """Counts of what a batch did.

    Attributes
    ----------
    evaluated : int
        Tools scored (or planned, in a dry run).
    fetched : int
        Of those, tools whose data was fetched (all or only missing sources).
    from_saved : int
        Of those, tools scored from their saved data without fetching.
    skipped_urls : int
        Rows skipped because their URL points inside a repository.
    failed : int
        Invalid rows and failed evaluations.
    """

    evaluated: int = 0
    fetched: int = 0
    from_saved: int = 0
    skipped_urls: int = 0
    failed: int = 0


def repository_url(url: str) -> str:
    """Return ``url`` if it is the root of a GitHub or GitLab repository.

    Parameters
    ----------
    url : str
        Homepage from the CSV.

    Returns
    -------
    str
        The URL, stripped.

    Raises
    ------
    SkippedURL
        If the URL points inside a repository (e.g. its releases); the
        enclosing repository is not assumed to be the right one.
    ValueError
        If the URL is not a GitHub or gitlab.com repository URL.
    """
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme not in {"http", "https"}
        or host not in {"github.com", "gitlab.com"}
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.query
        or parsed.fragment
        or any(not part for part in parts)
        or len(parts) < 2
    ):
        raise ValueError(f"not a GitHub or GitLab repository URL: {url!r}")
    if host == "github.com" and len(parts) != 2:
        raise SkippedURL(f"GitHub URL has a path beyond the repository: {url!r}")
    if host == "gitlab.com" and "-" in parts:
        raise SkippedURL(f"GitLab URL points inside a repository: {url!r}")
    return url.strip()


def parse_row(row_number: int, row: dict[str, str | None]) -> BatchItem:
    """Validate one CSV row and turn it into a batch item.

    Parameters
    ----------
    row_number : int
        CSV line number.
    row : dict
        The row, by column name.

    Returns
    -------
    BatchItem
        The tool to evaluate.

    Raises
    ------
    SkippedURL
        If the homepage points inside a repository.
    ValueError
        If the bio.tools ID, homepage or a DOI is invalid.
    """
    biotools_id = (row.get("biotoolsID") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", biotools_id):
        raise ValueError(f"invalid bio.tools ID: {biotools_id!r}")
    repository = repository_url(row.get("homepage") or "")
    dois = [doi.strip() for doi in (row.get("dois") or "").split(",") if doi.strip()]
    for doi in dois:
        if not re.fullmatch(r"10\.\d{4,9}/\S+", _DOI_PREFIX.sub("", doi)):
            raise ValueError(f"invalid DOI: {doi!r}")
    try:
        request = EvaluationRequest(
            repository=repository, dois=dois, biotools_id=biotools_id
        )
    except ValidationError as error:
        raise ValueError(str(error)) from error
    return BatchItem(row_number, biotools_id, request)


def read_csv(path: Path) -> list[BatchRow]:
    """Read and validate every row of a bio.tools CSV export.

    Parameters
    ----------
    path : pathlib.Path
        CSV with ``biotoolsID``, ``homepage`` and ``dois`` columns.

    Returns
    -------
    list of BatchRow
        One entry per row, in file order.

    Raises
    ------
    ValueError
        If a required column is missing.
    OSError, csv.Error
        If the file cannot be read or parsed.
    """
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(
                f"CSV must contain columns: {', '.join(sorted(REQUIRED_COLUMNS))}"
            )
        rows = []
        for row_number, row in enumerate(reader, 2):
            try:
                rows.append(BatchRow(row_number, item=parse_row(row_number, row)))
            except SkippedURL as error:
                rows.append(BatchRow(row_number, skipped=str(error)))
            except ValueError as error:
                rows.append(BatchRow(row_number, error=str(error)))
        return rows


# The log file of the tool whose task is running, if any.
_tool_log: ContextVar[logging.Handler | None] = ContextVar("tool_log", default=None)


class _ToolLogRouter(logging.Handler):
    """Send each record to the log file of the tool that emitted it."""

    def emit(self, record: logging.LogRecord) -> None:
        handler = _tool_log.get()
        if handler is not None:
            handler.handle(record)


def _outside_tools(record: logging.LogRecord) -> bool:
    return _tool_log.get() is None


@contextlib.contextmanager
def _route_tool_logs() -> Iterator[None]:
    """Write tools' records to their own files, and not to the other handlers."""
    root = logging.getLogger()
    handlers = list(root.handlers)
    router = _ToolLogRouter()
    for handler in handlers:
        handler.addFilter(_outside_tools)
    root.addHandler(router)
    try:
        yield
    finally:
        root.removeHandler(router)
        for handler in handlers:
            handler.removeFilter(_outside_tools)


@contextlib.contextmanager
def _log_to(path: Path) -> Iterator[None]:
    """Write the records of this task (and tasks it starts) to ``path``."""
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    token = _tool_log.set(handler)
    try:
        yield
    finally:
        _tool_log.reset(token)
        handler.close()


def _write_new(path: Path, text: str) -> None:
    """Write ``path`` in one step, never replacing an existing file."""
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, suffix=".tmp", delete=False, encoding="utf-8"
    ) as file:
        file.write(text)
    try:
        os.link(file.name, path)
    except FileExistsError as error:
        raise ValueError(f"data file appeared during evaluation: {path}") from error
    finally:
        os.unlink(file.name)


def _write_replace(path: Path, text: str) -> None:
    """Write ``path`` in one step, replacing it if it exists."""
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, suffix=".tmp", delete=False, encoding="utf-8"
    ) as file:
        file.write(text)
    os.replace(file.name, path)


class _GitHubBudget:
    """Wait for GitHub's rate limit to reset when few requests are left."""

    def __init__(self, token: str, report: Callable[[BatchEvent], None]):
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
        }
        self._report = report
        # One check at a time, so a reset is waited for (and reported) once.
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            while True:
                try:
                    # Checking the rate limit does not count towards it.
                    status = await get_json(
                        "https://api.github.com/rate_limit", headers=self._headers
                    )
                    core = status["resources"]["core"]
                    remaining, reset = int(core["remaining"]), float(core["reset"])
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
                    logger.warning(f"Could not check the GitHub rate limit: {error}")
                    return
                if remaining >= GITHUB_RESERVE:
                    return
                seconds = max(reset - time.time(), 0) + 5
                self._report(
                    BatchEvent(
                        "wait",
                        message=f"{remaining} GitHub requests left until the reset",
                        seconds=seconds,
                    )
                )
                await asyncio.sleep(seconds)


async def evaluate_batch(
    rows: list[BatchRow],
    output_dir: Path,
    *,
    jobs: int | None = None,
    fill_missing: bool = False,
    dry_run: bool = False,
    report: Callable[[BatchEvent], None] = lambda event: None,
) -> BatchSummary:
    """Evaluate the tools in ``rows``, saving their data and results.

    Each tool's ingested data is saved to ``output_dir/raw/<row>-<bio.tools
    ID>.json`` (reusable with ``maturity-meter evaluate --data``), its scored
    result to ``output_dir/results/`` under the same name, and its log to
    ``output_dir/logs/``. A tool with a saved data file is not fetched again:
    the saved data is scored as it is, or with ``fill_missing`` only its
    missing sources are fetched. A failed tool is reported and leaves no new
    files; the other tools continue.

    Parameters
    ----------
    rows : list of BatchRow
        Rows from :func:`read_csv`.
    output_dir : pathlib.Path
        Directory for the data, result and log files; created if needed.
    jobs : int, optional
        Number of tools being fetched at the same time. Defaults to the
        ``batch_jobs`` setting (``MATURITY_METER_BATCH_JOBS``).
    fill_missing : bool, default=False
        For tools with saved data, fetch the sources missing from it (e.g.
        after a source was unavailable) instead of scoring it as it is.
    dry_run : bool, default=False
        Only report what would be done; create nothing.
    report : callable, optional
        Called with each :class:`BatchEvent` as it happens.

    Returns
    -------
    BatchSummary
        What the batch did.
    """
    settings = get_settings()
    if jobs is None:
        jobs = settings.batch_jobs
    if jobs < 1:
        raise ValueError("jobs must be at least 1")
    summary = BatchSummary()
    raw_dir = output_dir / "raw"
    results_dir, log_dir = output_dir / "results", output_dir / "logs"
    saved: list[BatchItem] = []
    to_fetch: list[tuple[BatchItem, bool]] = []  # (item, has saved data)
    for row in rows:
        if row.error is not None:
            summary.failed += 1
            report(BatchEvent("invalid", row.row, message=row.error))
        elif row.skipped is not None:
            summary.skipped_urls += 1
            report(BatchEvent("skip_url", row.row, message=row.skipped))
        elif row.item is not None:
            item = row.item
            has_saved = (raw_dir / f"{item.stem}.json").exists()
            if dry_run:
                action = (
                    "fetch missing sources"
                    if has_saved and fill_missing
                    else "score saved data"
                    if has_saved
                    else "fetch"
                )
                summary.evaluated += 1
                report(
                    BatchEvent(
                        "plan",
                        item.row,
                        item.biotools_id,
                        f"{action}: {item.request.repository}",
                    )
                )
            elif has_saved and not fill_missing:
                saved.append(item)
            else:
                to_fetch.append((item, has_saved))
    if dry_run or not (saved or to_fetch):
        return summary

    for directory in (raw_dir, results_dir, log_dir):
        directory.mkdir(parents=True, exist_ok=True)

    def save_result(item: BatchItem, data: IngestedData) -> None:
        _write_replace(results_dir / f"{item.stem}.json", score(data).to_json() + "\n")

    # Saved data needs no network, so it is scored right away.
    for item in saved:
        try:
            save_result(item, IngestedData.load(raw_dir / f"{item.stem}.json"))
        except Exception as error:
            summary.failed += 1
            report(
                BatchEvent(
                    "failed",
                    item.row,
                    item.biotools_id,
                    f"saved data could not be scored: {error}",
                )
            )
            continue
        summary.evaluated += 1
        summary.from_saved += 1
        report(BatchEvent("scored", item.row, item.biotools_id, "from saved data"))
    if not to_fetch:
        return summary

    token = settings.github_token
    budget = _GitHubBudget(token.get_secret_value(), report) if token else None
    if budget is None and any(i.request.host == "github.com" for i, _ in to_fetch):
        logger.warning(
            "No GitHub token is set, so GitHub allows only 60 requests an hour "
            "and most tools will lack data. Set MATURITY_METER_GITHUB_TOKEN."
        )
    slots = asyncio.Semaphore(jobs)

    async def evaluate(item: BatchItem, has_saved: bool) -> bool:
        log = log_dir / f"{item.stem}.log"
        raw = raw_dir / f"{item.stem}.json"
        async with slots:
            with _log_to(log):
                if budget is not None and item.request.host == "github.com":
                    await budget.wait()
                report(
                    BatchEvent(
                        "start", item.row, item.biotools_id, item.request.repository
                    )
                )
                start = time.monotonic()
                try:
                    request = item.request
                    if has_saved:
                        # Only the sources missing from the saved data are fetched.
                        request = EvaluationRequest(
                            repository=request.repository,
                            dois=request.dois,
                            biotools_id=request.biotools_id,
                            data=json.loads(raw.read_text(encoding="utf-8")),
                        )
                    data = await ingest(request)
                    text = data.to_json() + "\n"
                    if has_saved:
                        _write_replace(raw, text)
                    else:
                        _write_new(raw, text)
                    save_result(item, data)
                except Exception as error:
                    # One tool must never stop the batch; the traceback goes
                    # to the tool's log.
                    logger.exception(f"Evaluating {item.request.repository} failed")
                    report(
                        BatchEvent(
                            "failed",
                            item.row,
                            item.biotools_id,
                            f"{error} (log: {log})",
                        )
                    )
                    return False
            report(
                BatchEvent(
                    "done",
                    item.row,
                    item.biotools_id,
                    seconds=time.monotonic() - start,
                )
            )
            return True

    resqui_limit = settings.resqui_parallel or plugin_count()
    with _route_tool_logs(), shared_limit(resqui_limit):
        async with shared_client():
            results = await asyncio.gather(
                *(evaluate(item, has_saved) for item, has_saved in to_fetch)
            )
    summary.evaluated += sum(results)
    summary.fetched += sum(results)
    summary.failed += len(results) - sum(results)
    return summary
