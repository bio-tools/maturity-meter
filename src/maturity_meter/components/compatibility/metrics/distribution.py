"""Compatibility metrics on packaging and workflow integration."""

from maturity_meter.components.utils.checks import (
    Aspect,
    aspect_metric,
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.files import (
    PYTHON_PACKAGING_FILES,
    is_bioconda_file,
    is_workflow_file,
)
from maturity_meter.components.utils.sources import (
    biotools_types,
    file_name,
    has_file,
    openebench_metric,
    rsec_has,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult


def package_availability(data: IngestedData) -> MetricResult:
    """Whether the software can be installed with a package manager.

    Aspects and their sources:

    - published package: Bioconda and Debian Med entries in RSEc,
      OpenEBench's package check, and OpenSSF Scorecard's
      ``has_published_package`` check;
    - packaging recipe: a conda recipe (``meta.yaml``) or Python packaging
      file (``pyproject.toml``, ``setup.py``, ``setup.cfg``) in the repository.

    OEBFAIR's ``has_published_package`` check is not used: it reported "no
    package" for every tool, including Bioconda packages.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    return aspect_metric(
        "package_availability",
        {
            "published package": Aspect(
                {
                    "Bioconda (RSEc)": rsec_has(data, is_bioconda_file),
                    "Debian Med (RSEc)": rsec_has(
                        data, lambda n: n.endswith(".debian.yaml")
                    ),
                    "OpenEBench packages": verdict(
                        openebench_metric(data, "distribution.packages")
                    ),
                    "OpenSSF Scorecard": resqui_verdict(
                        data, "has_published_package", {"OpenSSF Scorecard"}
                    ),
                },
                "Publish a package (e.g. in Bioconda or PyPI).",
            ),
            "packaging recipe": Aspect(
                {
                    "conda recipe": has_file(
                        data, lambda f: file_name(f) == "meta.yaml"
                    ),
                    "Python packaging file": has_file(
                        data, lambda f: file_name(f) in PYTHON_PACKAGING_FILES
                    ),
                },
                "Add a packaging recipe (e.g. pyproject.toml or a conda recipe).",
            ),
        },
    )


def workflow_integration(data: IngestedData) -> MetricResult:
    """Whether the software can be used in workflow systems.

    Sources: a Galaxy entry in RSEc, a Galaxy service link in bio.tools, and
    workflow-manager files (Snakemake, Nextflow, CWL, WDL) in the repository.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    links = biotools_types(data, "link")
    return verdict_metric(
        "workflow_integration",
        {
            "Galaxy (RSEc)": rsec_has(data, lambda n: n.endswith(".galaxy.json")),
            "Galaxy service (bio.tools)": None
            if links is None
            else float("Galaxy service" in links),
            "workflow files": has_file(data, is_workflow_file),
        },
        suggestion="Make the tool usable in Galaxy or a workflow manager.",
    )
