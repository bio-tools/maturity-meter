"""Accessors for the ingested data shared by the metrics.

They read one source (repository record, files and README, bio.tools,
OpenEBench, RSEc) and return a value or a 1/0 verdict, or None when the
source has no data, so metrics can tell "not assessed" from "no".
"""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

from maturity_meter.models import IngestedData


def verdict(value: Any) -> float | None:
    """1.0 for a truthy value, 0.0 for a falsy one, None when unknown."""
    return None if value is None else float(bool(value))


def repo_record(data: IngestedData) -> dict[str, Any] | None:
    """The GitHub/GitLab repository record, or None if not ingested."""
    record: dict[str, Any] | None = data.repository.get("repo")
    return record


def repo_files(data: IngestedData) -> list[str] | None:
    """Lower-cased repository file paths, or None without a file list."""
    files = data.repository.get("files")
    return None if files is None else [str(f).lower() for f in files]


def has_file(data: IngestedData, matches: Any) -> float | None:
    """Whether any repository file path matches ``matches(path)``.

    Returns 1.0 if a lower-cased path matches and 0.0 if none does, but None
    (unknown) without a file list, or when the list was truncated and no
    match was found: on very large repositories a file's absence from a cut-off
    list proves nothing.
    """
    files = repo_files(data)
    if files is None:
        return None
    if any(matches(f) for f in files):
        return 1.0
    return None if data.repository.get("files_truncated") else 0.0


def file_name(path: str) -> str:
    return PurePosixPath(path).name


def readme_matches(data: IngestedData, pattern: str) -> float | None:
    """Whether the README matches ``pattern`` (case-insensitive)."""
    readme = data.repository.get("readme")
    if readme is None:
        return None
    return float(re.search(pattern, str(readme), re.IGNORECASE) is not None)


def biotools_has(data: IngestedData, key: str) -> float | None:
    """Whether the bio.tools entry has a non-empty ``key``."""
    entry = data.biotools
    return None if entry is None else verdict(entry.get(key))


def biotools_types(data: IngestedData, key: str) -> set[str] | None:
    """All ``type`` values of a bio.tools list (e.g. documentation, links)."""
    entry = data.biotools
    if entry is None:
        return None
    types: set[str] = set()
    for item in entry.get(key) or []:
        kinds = item.get("type")
        types.update(kinds if isinstance(kinds, list) else [kinds])
    return {str(t) for t in types if t}


def openebench_metric(data: IngestedData, path: str) -> Any:
    """A value from the OpenEBench metrics by dotted path, or None."""
    value: Any = (data.openebench or {}).get("metrics")
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    # Empty objects mean OpenEBench has no data for that part.
    return None if value == {} else value


def openebench_tool_has(data: IngestedData, key: str) -> float | None:
    """Whether the OpenEBench tool record has a non-empty ``key``."""
    tool = (data.openebench or {}).get("tool")
    return None if tool is None else verdict(tool.get(key))


def registry_lookup(data: IngestedData, source: Any) -> float | None:
    """Whether a registry source (looked up by bio.tools ID) has an entry.

    Without a bio.tools ID nothing was looked up, so the answer is unknown.
    """
    if not data.request.biotools_id:
        return None
    return float(source is not None)


def parse_time(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp (GitHub and GitLab style), or None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def rsec_has(data: IngestedData, matches: Callable[[str], bool]) -> float | None:
    """Whether RSEc holds a file matching ``matches``; None without RSEc data."""
    if data.rsec is None:
        return None
    return float(any(matches(name.lower()) for name in data.rsec.get("files") or []))
