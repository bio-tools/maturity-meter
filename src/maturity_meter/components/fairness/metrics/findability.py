"""FAIRness metrics on findability: registries, identifiers and metadata."""

from maturity_meter.components.utils.checks import (
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.sources import (
    biotools_has,
    file_name,
    has_file,
    openebench_metric,
    readme_matches,
    registry_lookup,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult


def registry_listing(data: IngestedData) -> MetricResult:
    """Whether the software is listed in research software registries.

    Sources: entries in bio.tools, OpenEBench and RSEc for the bio.tools ID,
    registry badges in the README, and resqui's ``listed_in_registry`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "registry_listing",
        {
            "bio.tools": registry_lookup(data, data.biotools),
            "OpenEBench": registry_lookup(data, data.openebench),
            "RSEc": registry_lookup(data, data.rsec),
            "README registry badge": readme_matches(
                data, r"bio\.tools/|research-software-directory|rsd\.|biocontainers"
            ),
            "resqui check": resqui_verdict(data, "listed_in_registry"),
        },
        suggestion="Register the software in bio.tools.",
        missing="No bio.tools ID or README to check.",
    )


def persistent_identifier(data: IngestedData) -> MetricResult:
    """Whether the software has a persistent, unique identifier.

    Sources: a software DOI (Zenodo) or Software Heritage ID in the README,
    the bio.tools ID, and resqui's ``persistent_and_unique_identifier`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "persistent_identifier",
        {
            "software DOI/SWHID in README": readme_matches(
                data, r"10\.5281/zenodo\.\d+|swh:1:"
            ),
            "bio.tools ID": registry_lookup(data, data.biotools),
            "resqui check": resqui_verdict(data, "persistent_and_unique_identifier"),
        },
        suggestion="Archive releases on Zenodo to get a DOI.",
    )


def structured_metadata(data: IngestedData) -> MetricResult:
    """Whether machine-readable descriptive metadata is available.

    Sources: ``codemeta.json`` and ``CITATION.cff`` files, the bio.tools entry,
    and resqui's ``descriptive_metadata`` and ``codemeta_completeness`` checks.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "structured_metadata",
        {
            "codemeta.json": has_file(data, lambda f: file_name(f) == "codemeta.json"),
            "CITATION.cff": has_file(data, lambda f: file_name(f) == "citation.cff"),
            "bio.tools entry": registry_lookup(data, data.biotools),
            "resqui descriptive metadata": resqui_verdict(data, "descriptive_metadata"),
            "resqui CodeMeta completeness": resqui_verdict(
                data, "codemeta_completeness"
            ),
        },
        suggestion="Add a codemeta.json describing the software.",
    )


def semantic_annotation(data: IngestedData) -> MetricResult:
    """Whether the metadata uses community vocabularies (EDAM, Bioschemas).

    Sources: EDAM topics and operations in the bio.tools entry, and
    OpenEBench's Bioschemas check of the website.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    entry = data.biotools
    operations = (
        None
        if entry is None
        else float(any(f.get("operation") for f in entry.get("function") or []))
    )
    return verdict_metric(
        "semantic_annotation",
        {
            "EDAM topics (bio.tools)": biotools_has(data, "topic"),
            "EDAM operations (bio.tools)": operations,
            "Bioschemas (OpenEBench)": verdict(
                openebench_metric(data, "project.website.bioschemas")
            ),
        },
        suggestion="Annotate the bio.tools entry with EDAM topics and operations.",
        missing="No bio.tools entry or OpenEBench data.",
    )
