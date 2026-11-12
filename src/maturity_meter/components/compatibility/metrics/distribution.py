"""Compatibility metrics on distribution and packaging (repository files + RSEc)."""

from collections.abc import Callable

from maturity_meter.components.utils.checks import (
    verdict_metric,
)
from maturity_meter.components.utils.files import (
    is_bioconda_file,
    is_biocontainers_file,
    is_distribution_file,
)
from maturity_meter.components.utils.sources import (
    has_file,
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
    return verdict_metric(
        "has_distribution_support",
        {
            "Dockerfile or conda recipe": has_file(data, is_distribution_file),
            "Bioconda/BioContainers": rsec_has(
                data, lambda n: is_bioconda_file(n) or is_biocontainers_file(n)
            ),
        },
        suggestion="Provide a Dockerfile or a conda (e.g. Bioconda) package.",
        missing="No repository file list or RSEc entry available.",
    )


def _rsec_metric(
    data: IngestedData,
    name: str,
    platform: str,
    matches: Callable[[str], bool],
    suggestion: str,
) -> MetricResult:
    """Whether RSEc links the tool to ``platform``."""
    return verdict_metric(
        name,
        {f"{platform} (RSEc)": rsec_has(data, matches)},
        suggestion=suggestion,
        missing=_NO_RSEC,
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
