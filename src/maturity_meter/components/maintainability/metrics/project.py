"""Maintainability metric on declared dependencies."""

from pathlib import PurePosixPath

from maturity_meter.components.utils.checks import (
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.files import (
    DEPENDENCY_MANIFESTS,
)
from maturity_meter.components.utils.sources import file_name, has_file
from maturity_meter.models import IngestedData, MetricResult


def requirements_specified(data: IngestedData) -> MetricResult:
    """Whether the software declares its dependencies.

    Combines a dependency manifest in the repository (e.g.
    ``requirements.txt``, ``pyproject.toml``, ``environment.yml``,
    ``package.json``, ``DESCRIPTION``, ``Cargo.toml``, ``go.mod``) and resqui's
    ``requirements_specified`` check (if run) with
    :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if declared, 0 if not, or ``value=None`` without a file list or
        check.
    """
    manifests = sorted(
        {
            PurePosixPath(str(f)).name
            for f in data.repository.get("files") or []
            if file_name(str(f).lower()) in DEPENDENCY_MANIFESTS
        }
    )
    return verdict_metric(
        "requirements_specified",
        {
            "dependency manifest": has_file(
                data, lambda f: file_name(f) in DEPENDENCY_MANIFESTS
            ),
            "RSFC": resqui_verdict(data, "requirements_specified"),
        },
        suggestion="Declare the dependencies (e.g. in requirements.txt).",
        missing="Repository file list unavailable.",
        detail=f"Manifests: {', '.join(manifests)}." if manifests else "",
    )
