"""Compatibility metrics on distribution and packaging (repository files + RSEc)."""

from collections.abc import Callable
from typing import Any

from maturity_meter.components.utils.checks import (
    findings_note,
)
from maturity_meter.components.utils.files import (
    is_bioconda_file,
    is_biocontainers_file,
    is_distribution_file,
)
from maturity_meter.components.utils.scaling import (
    placeholder_reconcile,
)
from maturity_meter.components.utils.sources import (
    rsec_has,
)
from maturity_meter.models import IngestedData, MetricResult

_NO_RSEC = "No Research Software Ecosystem entry (a bio.tools ID is needed)."


def has_distribution_support(data: IngestedData) -> MetricResult:
    """Whether the software is distributed as a container or conda package.

    Combines a Dockerfile/Containerfile or conda recipe (``meta.yaml``) in the
    repository and a Bioconda or BioContainers entry in RSEc with
    :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if found, 0 if not, or ``value=None`` without a file list or RSEc.
    """
    files: list[Any] | None = data.repository.get("files")
    findings = {
        "Dockerfile or conda recipe": None
        if files is None
        else float(any(is_distribution_file(str(f)) for f in files)),
        "Bioconda/BioContainers": rsec_has(
            data, lambda n: is_bioconda_file(n) or is_biocontainers_file(n)
        ),
    }
    value = placeholder_reconcile(list(findings.values()))
    if value is None:
        return MetricResult(
            name="has_distribution_support",
            value=None,
            note="No repository file list or RSEc entry available.",
        )
    return MetricResult(
        name="has_distribution_support",
        value=value,
        note=findings_note(findings, "found", "not found"),
        suggestions=[]
        if value > 0
        else ["Provide a Dockerfile or a conda (e.g. Bioconda) package."],
    )


def _rsec_metric(
    data: IngestedData,
    name: str,
    platform: str,
    matches: Callable[[str], bool],
    suggestion: str,
) -> MetricResult:
    """Whether RSEc links the tool to ``platform``."""
    found = rsec_has(data, matches)
    if found is None:
        return MetricResult(name=name, value=None, note=_NO_RSEC)
    return MetricResult(
        name=name,
        value=found,
        note=f"{platform}: {'found' if found else 'not found'} in RSEc.",
        suggestions=[] if found else [suggestion],
    )


def bioconda_package(data: IngestedData) -> MetricResult:
    """Whether the tool has a Bioconda package (per RSEc).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the RSEc file list.

    Returns
    -------
    MetricResult
        1 if found, 0 if not, or ``value=None`` without an RSEc entry.
    """
    return _rsec_metric(
        data,
        "bioconda_package",
        "Bioconda",
        is_bioconda_file,
        "Package the tool in Bioconda.",
    )


def debian_med_package(data: IngestedData) -> MetricResult:
    """Whether the tool has a Debian Med package (per RSEc).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the RSEc file list.

    Returns
    -------
    MetricResult
        1 if found, 0 if not, or ``value=None`` without an RSEc entry.
    """
    return _rsec_metric(
        data,
        "debian_med_package",
        "Debian Med",
        lambda n: n.endswith(".debian.yaml"),
        "Package the tool for Debian Med.",
    )


def biocontainer_image(data: IngestedData) -> MetricResult:
    """Whether the tool has a BioContainers image (per RSEc).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the RSEc file list.

    Returns
    -------
    MetricResult
        1 if found, 0 if not, or ``value=None`` without an RSEc entry.
    """
    return _rsec_metric(
        data,
        "biocontainer_image",
        "BioContainers",
        is_biocontainers_file,
        "Provide a BioContainers image (e.g. via a Bioconda package).",
    )


def available_in_galaxy(data: IngestedData) -> MetricResult:
    """Whether the tool is available in Galaxy (per RSEc).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the RSEc file list.

    Returns
    -------
    MetricResult
        1 if found, 0 if not, or ``value=None`` without an RSEc entry.
    """
    return _rsec_metric(
        data,
        "available_in_galaxy",
        "Galaxy",
        lambda n: n.endswith(".galaxy.json"),
        "Make the tool available in Galaxy (e.g. a Galaxy tool wrapper).",
    )
