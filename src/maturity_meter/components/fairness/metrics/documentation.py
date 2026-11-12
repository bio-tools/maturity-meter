"""FAIRness metrics on documentation."""

from maturity_meter.components.utils.checks import (
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.files import (
    DEPENDENCY_MANIFESTS,
)
from maturity_meter.components.utils.sources import (
    biotools_has,
    biotools_types,
    file_name,
    has_file,
    openebench_metric,
    readme_matches,
    repo_record,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult


def documentation(data: IngestedData) -> MetricResult:
    """Whether documentation is available.

    Sources: a README, a ``docs/`` folder, GitHub Pages, documentation links
    in bio.tools, OpenEBench's documentation checks and resqui's
    ``software_has_documentation`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repository = data.repository
    return verdict_metric(
        "documentation",
        {
            "README": verdict(repository.get("readme"))
            if "readme" in repository
            else None,
            "docs folder": has_file(data, lambda f: f.startswith(("docs/", "doc/"))),
            "GitHub Pages": verdict(repository.get("github_pages"))
            if "github_pages" in repository
            else None,
            "bio.tools documentation": biotools_has(data, "documentation"),
            "OpenEBench": verdict(
                openebench_metric(data, "project.documentation.general")
                or openebench_metric(data, "project.documentation.manual")
            ),
            "resqui check": resqui_verdict(data, "software_has_documentation"),
        },
        suggestion="Write a README and user documentation.",
    )


def purpose_description(data: IngestedData) -> MetricResult:
    """Whether a description of what the software is for is available.

    Sources: the GitHub/GitLab description, the bio.tools description and
    OpenEBench's description check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = repo_record(data)
    return verdict_metric(
        "purpose_description",
        {
            "repository description": None
            if repo is None
            else verdict(repo.get("description")),
            "bio.tools description": biotools_has(data, "description"),
            "OpenEBench": verdict(
                openebench_metric(data, "project.summary.description")
            ),
        },
        suggestion="Describe what the software does and what it is for.",
    )


def installation_instructions(data: IngestedData) -> MetricResult:
    """Whether installation and dependency information is provided.

    Sources: an installation section in the README, installation docs in
    bio.tools, a dependency manifest, and resqui's ``requirements_specified``
    check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    docs = biotools_types(data, "documentation")
    return verdict_metric(
        "installation_instructions",
        {
            "README": readme_matches(data, r"\binstall"),
            "bio.tools installation docs": None
            if docs is None
            else float("Installation instructions" in docs),
            "dependency manifest": has_file(
                data, lambda f: file_name(f) in DEPENDENCY_MANIFESTS
            ),
            "resqui check": resqui_verdict(data, "requirements_specified"),
        },
        suggestion="Add installation instructions and the dependencies to the README.",
    )
