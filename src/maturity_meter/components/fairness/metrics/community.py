"""FAIRness metrics on quality tooling, issue tracking, website, governance
and containers.
"""

from maturity_meter.components.utils.checks import (
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.files import (
    LINTER_FILES,
)
from maturity_meter.components.utils.sources import (
    biotools_types,
    file_name,
    has_file,
    openebench_metric,
    repo_record,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult


def code_quality_tooling(data: IngestedData) -> MetricResult:
    """Whether linters or static analysis are used and pass.

    Sources: linter and formatter configuration files, and resqui's
    ``has_no_linting_issues`` and ``uses_tool_for_warnings_and_mistakes``
    checks.

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
        "code_quality_tooling",
        {
            "linter configuration": has_file(
                data,
                lambda f: (
                    file_name(f) in LINTER_FILES or file_name(f).startswith(".eslintrc")
                ),
            ),
            "resqui linting check": resqui_verdict(data, "has_no_linting_issues"),
            "resqui static analysis check": resqui_verdict(
                data, "uses_tool_for_warnings_and_mistakes"
            ),
        },
        suggestion="Use linters or static analysis (e.g. via pre-commit).",
    )


def issue_tracking(data: IngestedData) -> MetricResult:
    """Whether users can report issues in a public tracker.

    Sources: the GitHub/GitLab issue tracker, OpenEBench's public tracker check
    and an issue-tracker link in bio.tools.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = repo_record(data) or {}
    if "has_issues" in repo:
        tracker = verdict(repo.get("has_issues"))
    else:
        # GitLab: issue statistics are only available when issues are enabled.
        tracker = None if data.repository.get("open_issues") is None else 1.0
    links = biotools_types(data, "link")
    return verdict_metric(
        "issue_tracking",
        {
            "repository issues": tracker,
            "OpenEBench": verdict(
                openebench_metric(data, "support.issue_tracking.public_tracker")
            ),
            "bio.tools link": None
            if links is None
            else float("Issue tracker" in links),
        },
        suggestion="Enable a public issue tracker.",
    )


def project_website(data: IngestedData) -> MetricResult:
    """Whether the software has its own website.

    Sources: the GitHub homepage field, GitHub Pages, a bio.tools homepage
    other than the repository, and OpenEBench's website check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = repo_record(data) or {}
    repository = data.repository
    homepage = (data.biotools or {}).get("homepage")
    repo_url = data.request.repository.rstrip("/").lower()
    operational = openebench_metric(data, "project.website.operational")
    return verdict_metric(
        "project_website",
        {
            "repository homepage": verdict(repo.get("homepage"))
            if "homepage" in repo
            else None,
            "GitHub Pages": verdict(repository.get("github_pages"))
            if "github_pages" in repository
            else None,
            "bio.tools homepage": None
            if data.biotools is None
            else float(
                bool(homepage) and str(homepage).rstrip("/").lower() != repo_url
            ),
            "OpenEBench (website up)": None
            if operational is None
            else float(operational == 200),
        },
        suggestion="Provide a project website.",
    )


def contribution_and_governance(data: IngestedData) -> MetricResult:
    """Whether contribution guidelines and governance are described.

    Sources: CONTRIBUTING, GOVERNANCE and CODE_OF_CONDUCT files, and resqui's
    ``has_contribution_guidelines`` check.

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
        "contribution_and_governance",
        {
            "CONTRIBUTING file": has_file(
                data, lambda f: file_name(f).startswith("contributing")
            ),
            "GOVERNANCE file": has_file(
                data, lambda f: file_name(f).startswith("governance")
            ),
            "CODE_OF_CONDUCT file": has_file(
                data,
                lambda f: file_name(f).startswith(
                    ("code_of_conduct", "code-of-conduct")
                ),
            ),
            "resqui check": resqui_verdict(data, "has_contribution_guidelines"),
        },
        suggestion="Add contribution guidelines and describe the project's governance.",
    )


def containerization(data: IngestedData) -> MetricResult:
    """Whether the software can run in a container or isolated environment.

    Sources: container definitions (Dockerfile, Containerfile, Singularity),
    conda environment files, BioContainers (RSEc), and resqui's
    ``software_is_containerized`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    rsec_files = None if data.rsec is None else data.rsec.get("files") or []
    return verdict_metric(
        "containerization",
        {
            "container definition": has_file(
                data,
                lambda f: (
                    file_name(f).startswith(
                        ("dockerfile", "containerfile", "singularity")
                    )
                    or file_name(f) == "apptainer.def"
                ),
            ),
            "conda environment": has_file(
                data, lambda f: file_name(f) in ("environment.yml", "environment.yaml")
            ),
            "BioContainers (RSEc)": None
            if rsec_files is None
            else float(
                any(str(f).lower().endswith("biocontainers.yaml") for f in rsec_files)
            ),
            "resqui check": resqui_verdict(data, "software_is_containerized"),
        },
        suggestion="Provide a Dockerfile or a conda environment file.",
    )
