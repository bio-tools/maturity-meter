"""Helpers to read yes/no verdicts: resqui checks and repository files."""

from collections.abc import Iterable

from maturity_meter.components.utils.scaling import placeholder_reconcile
from maturity_meter.models import IngestedData

# resqui does not serialize a pass/fail flag; the verdict is the plugin's
# ``output`` string. Other outputs (e.g. "error", "indeterminate") give no
# verdict.
PASSING_OUTPUTS = {"true", "valid", "secure"}
FAILING_OUTPUTS = {"false", "invalid", "insecure"}


def resqui_verdict(data: IngestedData, indicator: str) -> float | None:
    """Verdict of the resqui check(s) for one EVERSE indicator.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses ``quality_checks``.
    indicator : str
        EVERSE indicator identifier, e.g. ``"no_leaked_credentials"``.

    Returns
    -------
    float | None
        1.0 if passed, 0.0 if failed, reconciled with
        :func:`placeholder_reconcile` when several plugins check the indicator;
        None if resqui did not check it or gave no verdict.
    """
    verdicts: list[float | None] = []
    for check in (data.quality_checks or {}).get("checks") or []:
        assessed = str((check.get("assessesIndicator") or {}).get("@id", ""))
        if assessed.rstrip("/").rsplit("/", 1)[-1] != indicator:
            continue
        output = str(check.get("output", "")).lower()
        if output in PASSING_OUTPUTS:
            verdicts.append(1.0)
        elif output in FAILING_OUTPUTS:
            verdicts.append(0.0)
    return placeholder_reconcile(verdicts)


def has_any_file(data: IngestedData, paths: Iterable[str]) -> float | None:
    """Whether the repository contains any of the given files.

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the repository ``files`` list.
    paths : iterable of str
        File paths relative to the repository root, compared
        case-insensitively (e.g. ``".github/dependabot.yml"``).

    Returns
    -------
    float | None
        1.0 if any is present, 0.0 if none is, or None without a file list.
    """
    files = data.repository.get("files")
    if files is None:
        return None
    wanted = {path.lower() for path in paths}
    return float(any(f.lower() in wanted for f in files))


def findings_note(findings: dict[str, float | None], yes: str, no: str) -> str:
    """A note naming each source's verdict, so a disagreement is explained.

    Parameters
    ----------
    findings : dict[str, float | None]
        Verdict per source (1 or 0); sources without a verdict are skipped.
    yes, no : str
        Wording for a positive and a negative verdict.

    Returns
    -------
    str
        E.g. ``"OpenSSF Scorecard: not found; Dependabot/Renovate config: found."``
    """
    return (
        "; ".join(
            f"{source}: {yes if verdict else no}"
            for source, verdict in findings.items()
            if verdict is not None
        )
        + "."
    )
