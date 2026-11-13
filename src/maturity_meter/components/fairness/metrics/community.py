"""FAIRness metrics on the project's public channels: issues and website."""

from maturity_meter.components.utils.checks import verdict_metric
from maturity_meter.components.utils.sources import (
    biotools_types,
    openebench_metric,
    repo_record,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult


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
