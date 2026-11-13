"""FAIRness metrics on findability: registries, identifiers and metadata."""

from maturity_meter.components.utils.checks import (
    Aspect,
    aspect_metric,
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.sources import (
    biotools_has,
    fair_checker_score,
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

    Sources: the bio.tools, OpenEBench and RSEc entries looked up by bio.tools
    ID, and a registry badge in the README.

    OEBFAIR's ``listed_in_registry`` check is not used: it reported "not
    listed" for every tool, including tools listed in bio.tools.

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
        },
        suggestion="Register the software in bio.tools.",
        missing="No bio.tools ID or README to check.",
    )


def persistent_identifier(data: IngestedData) -> MetricResult:
    """Whether the software has a persistent, unique identifier.

    Sources: a software DOI or SWHID in the README, the bio.tools ID, the
    RSFC and OEBFAIR ``persistent_and_unique_identifier`` checks, and
    FAIR-Checker's persistent-identifier test (F1B) on the repository page.

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
            "RSFC/OEBFAIR": resqui_verdict(data, "persistent_and_unique_identifier"),
            "FAIR-Checker F1B": fair_checker_score(data, "F1B"),
        },
        suggestion="Archive releases on Zenodo to get a DOI.",
    )


def machine_readable_metadata(data: IngestedData) -> MetricResult:
    """How much machine-readable metadata describes the software.

    Aspects and their sources:

    - structured metadata: a ``codemeta.json`` or ``CITATION.cff`` file, a
      bio.tools entry, RSFC's ``codemeta_completeness`` check, and
      FAIR-Checker's structured-metadata (F2A), machine-readable-format (I1),
      external-links (I3) and provenance (R1.2) tests on the repository page;
    - community vocabularies: EDAM topics and operations in bio.tools,
      OpenEBench's Bioschemas check, and FAIR-Checker's shared-vocabulary
      (F2B), shared-ontology (I2) and community-standard (R1.3) tests.

    The RSFC and OEBFAIR ``descriptive_metadata`` checks are not used: they
    gave opposite answers (always no and always yes) for the same tools.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    entry = data.biotools
    operations = (
        None
        if entry is None
        else float(any(f.get("operation") for f in entry.get("function") or []))
    )
    return aspect_metric(
        "machine_readable_metadata",
        {
            "structured metadata": Aspect(
                {
                    "codemeta.json": has_file(
                        data, lambda f: file_name(f) == "codemeta.json"
                    ),
                    "CITATION.cff": has_file(
                        data, lambda f: file_name(f) == "citation.cff"
                    ),
                    "bio.tools entry": registry_lookup(data, data.biotools),
                    "RSFC CodeMeta completeness": resqui_verdict(
                        data, "codemeta_completeness"
                    ),
                    "FAIR-Checker F2A": fair_checker_score(data, "F2A"),
                    "FAIR-Checker I1": fair_checker_score(data, "I1"),
                    "FAIR-Checker I3": fair_checker_score(data, "I3"),
                    "FAIR-Checker R1.2": fair_checker_score(data, "R12"),
                },
                "Describe the software in structured metadata (e.g. a codemeta.json, "
                "or schema.org markup on its web page).",
            ),
            "community vocabularies": Aspect(
                {
                    "EDAM topics (bio.tools)": biotools_has(data, "topic"),
                    "EDAM operations (bio.tools)": operations,
                    "Bioschemas (OpenEBench)": verdict(
                        openebench_metric(data, "project.website.bioschemas")
                    ),
                    "FAIR-Checker F2B": fair_checker_score(data, "F2B"),
                    "FAIR-Checker I2": fair_checker_score(data, "I2"),
                    "FAIR-Checker R1.3": fair_checker_score(data, "R13"),
                },
                "Use community vocabularies in the metadata (e.g. EDAM terms in "
                "bio.tools, Bioschemas markup on the web page).",
            ),
        },
    )
