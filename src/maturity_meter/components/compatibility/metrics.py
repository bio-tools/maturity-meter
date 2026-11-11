"""Compatibility metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`. When several sources measure the same thing, they are
combined with :func:`placeholder_reconcile`. ``dependency_management`` is
shared with the security dimension.
"""

from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

from maturity_meter.components.shared.metrics import dependency_management
from maturity_meter.components.utils.checks import findings_note
from maturity_meter.components.utils.scaling import placeholder_reconcile
from maturity_meter.models import IngestedData, MetricResult

__all__ = [
    "available_in_galaxy",
    "biocontainer_image",
    "bioconda_package",
    "debian_med_package",
    "dependency_management",
    "has_distribution_support",
    "input_formats",
    "output_formats",
]

_NO_BIOTOOLS = "No bio.tools entry (a bio.tools ID is needed)."
_NO_RSEC = "No Research Software Ecosystem entry (a bio.tools ID is needed)."


# --- EDAM formats -------------------------------------------------------------


def _formats(data: IngestedData, direction: str) -> list[str]:
    """Unique EDAM format IRIs of the bio.tools entry's inputs or outputs."""
    iris: dict[str, None] = {}
    for function in (data.biotools or {}).get("function") or []:
        for io in function.get(direction) or []:
            for fmt in io.get("format") or []:
                if fmt.get("uri"):
                    iris[fmt["uri"]] = None
    return list(iris)


def _format_share(data: IngestedData, direction: str) -> MetricResult:
    """Share of the inputs' or outputs' formats that are specific EDAM terms."""
    name = f"{direction}_formats"
    if data.biotools is None:
        return MetricResult(name=name, value=None, note=_NO_BIOTOOLS)
    iris = _formats(data, direction)
    if not iris:
        return MetricResult(
            name=name,
            value=None,
            note=f"bio.tools lists no {direction} formats.",
            suggestions=[f"Annotate the {direction} formats in bio.tools with EDAM."],
        )
    terms = {iri: data.edam.get(iri) for iri in iris}
    known = {iri: term for iri, term in terms.items() if term is not None}
    if not known:
        return MetricResult(
            name=name, value=None, note="The formats could not be looked up in EDAM."
        )
    # A leaf term is a specific format (e.g. BAM); a term with children is a
    # broad class (e.g. "Sequence format"). Obsolete terms are not specific.
    specific = [
        iri
        for iri, term in known.items()
        if term.get("has_children") is False and not term.get("is_obsolete")
    ]
    value = len(specific) / len(known)
    broad = [str(known[iri].get("label")) for iri in known if iri not in specific]
    return MetricResult(
        name=name,
        value=value,
        note=(
            f"{len(specific)} of {len(known)} {direction} formats are specific "
            "EDAM terms"
            + (f"; broad or obsolete: {', '.join(broad)}" if broad else "")
            + "."
        ),
        suggestions=[]
        if value == 1
        else [f"Use specific EDAM formats for the {direction}s instead of broad ones."],
    )


def input_formats(data: IngestedData) -> MetricResult:
    """Share of the input formats that are specific EDAM terms (leaf nodes).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the bio.tools functions' inputs and their EDAM
        terms.

    Returns
    -------
    MetricResult
        The share in [0, 1], or ``value=None`` without a bio.tools entry,
        formats or EDAM terms.
    """
    return _format_share(data, "input")


def output_formats(data: IngestedData) -> MetricResult:
    """Share of the output formats that are specific EDAM terms (leaf nodes).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the bio.tools functions' outputs and their EDAM
        terms.

    Returns
    -------
    MetricResult
        The share in [0, 1], or ``value=None`` without a bio.tools entry,
        formats or EDAM terms.
    """
    return _format_share(data, "output")


# --- distribution ----------------------------------------------------------------


def _rsec_has(data: IngestedData, matches: Callable[[str], bool]) -> float | None:
    """Whether RSEc holds a file matching ``matches``; None without RSEc data."""
    if data.rsec is None:
        return None
    return float(any(matches(name.lower()) for name in data.rsec.get("files") or []))


def _is_bioconda(name: str) -> bool:
    return name.startswith("bioconda_") and name.endswith(".yaml")


def _is_biocontainers(name: str) -> bool:
    return name.endswith("biocontainers.yaml")


def _is_distribution_file(path: str) -> bool:
    """A Dockerfile/Containerfile or a conda recipe (``meta.yaml``)."""
    name = PurePosixPath(path.lower()).name
    return name.startswith(("dockerfile", "containerfile")) or name == "meta.yaml"


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
        else float(any(_is_distribution_file(str(f)) for f in files)),
        "Bioconda/BioContainers": _rsec_has(
            data, lambda n: _is_bioconda(n) or _is_biocontainers(n)
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
    found = _rsec_has(data, matches)
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
        _is_bioconda,
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
        _is_biocontainers,
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
