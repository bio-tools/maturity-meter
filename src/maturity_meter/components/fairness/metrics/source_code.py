"""FAIRness metrics on source code, releases, builds, tests and archival."""

import re

from maturity_meter.components.utils.checks import (
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.files import (
    BUILD_FILES,
    is_test_path,
)
from maturity_meter.components.utils.sources import (
    biotools_types,
    file_name,
    has_file,
    openebench_metric,
    readme_matches,
    repo_record,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult


def version_control(data: IngestedData) -> MetricResult:
    """Whether the source is under version control in a public repository.

    Sources: the GitHub/GitLab repository itself, OpenEBench's online
    repository check and resqui's ``version_control_use`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict.
    """
    return verdict_metric(
        "version_control",
        {
            # A repository record means it is hosted on GitHub/GitLab; without
            # one (not ingested) the answer is unknown, not "no".
            "GitHub/GitLab repository": None if repo_record(data) is None else 1.0,
            "OpenEBench": verdict(
                openebench_metric(data, "distribution.sourcecode.repository.online")
            ),
            "resqui check": resqui_verdict(data, "version_control_use"),
        },
        suggestion="Develop the software in a public version-controlled repository.",
    )


_VERSION_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)?([-.+][\w.]+)?$", re.IGNORECASE)


def releases_and_versioning(data: IngestedData) -> MetricResult:
    """Whether there are releases with conventional version numbers.

    Sources: the latest GitHub/GitLab release and whether its tag looks like a
    version (e.g. ``v1.2.3``), and resqui's ``has_releases`` and
    ``versioning_standards_use`` checks.

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
    latest = repository.get("latest_release")
    known = "latest_release" in repository
    tag = str((latest or {}).get("tag_name") or "")
    return verdict_metric(
        "releases_and_versioning",
        {
            "repository releases": verdict(latest) if known else None,
            "version-like tag": float(bool(_VERSION_TAG.match(tag))) if tag else None,
            "resqui releases check": resqui_verdict(data, "has_releases"),
            "resqui versioning check": resqui_verdict(data, "versioning_standards_use"),
        },
        suggestion="Publish releases tagged with version numbers (e.g. v1.2.3).",
    )


def automated_build(data: IngestedData) -> MetricResult:
    """Whether an automated build system is configured.

    Sources: build configuration files (Makefile, CMake, pyproject.toml, ...)
    and OpenEBench's build information.

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
        "automated_build",
        {
            "build configuration": has_file(
                data, lambda f: file_name(f) in BUILD_FILES
            ),
            "OpenEBench": verdict(openebench_metric(data, "project.build")),
        },
        suggestion="Add a build configuration (e.g. a Makefile or pyproject.toml).",
    )


def software_tests(data: IngestedData) -> MetricResult:
    """Whether the software comes with tests.

    Sources: test files or folders in the repository and resqui's
    ``software_has_tests`` check.

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
        "software_tests",
        {
            "test files": has_file(data, is_test_path),
            "resqui check": resqui_verdict(data, "software_has_tests"),
        },
        suggestion="Add automated tests.",
    )


def source_availability(data: IngestedData) -> MetricResult:
    """Whether the source code is publicly and freely available.

    Sources: the repository's visibility, OpenEBench's public and free source
    checks, and source-code downloads in bio.tools.

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
    downloads = biotools_types(data, "download")
    return verdict_metric(
        "source_availability",
        {
            "public repository": None
            if repo is None
            else float(
                repo.get("visibility") == "public" or repo.get("private") is False
            ),
            "OpenEBench public source": verdict(
                openebench_metric(data, "distribution.sourcecode.public")
            ),
            "OpenEBench free source": verdict(
                openebench_metric(data, "distribution.sourcecode.free")
            ),
            "bio.tools source download": None
            if downloads is None
            else float("Source code" in downloads),
        },
        suggestion="Make the source code publicly available.",
    )


def binary_distribution(data: IngestedData) -> MetricResult:
    """Whether ready-to-use binaries or packages are distributed.

    Sources: assets of the latest GitHub/GitLab release, binary downloads in
    bio.tools, OpenEBench's binary and package checks, and Bioconda (RSEc).

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
    assets = None
    if "latest_release" in repository:
        latest = repository.get("latest_release") or {}
        release_assets = latest.get("assets")
        # GitHub lists assets directly; GitLab under assets.links (its
        # assets.sources are the automatic source archives).
        if isinstance(release_assets, dict):
            release_assets = release_assets.get("links")
        assets = float(bool(release_assets))
    downloads = biotools_types(data, "download")
    rsec_files = None if data.rsec is None else data.rsec.get("files") or []
    return verdict_metric(
        "binary_distribution",
        {
            "release assets": assets,
            "bio.tools binaries": None
            if downloads is None
            else float("Binaries" in downloads),
            "OpenEBench free binaries": verdict(
                openebench_metric(data, "distribution.binaries.freeness")
            ),
            "OpenEBench packages": verdict(
                openebench_metric(data, "distribution.packages")
            ),
            "Bioconda (RSEc)": None
            if rsec_files is None
            else float(any(str(f).lower().startswith("bioconda_") for f in rsec_files)),
        },
        suggestion="Distribute binaries or packages (e.g. release assets, Bioconda).",
    )


def source_archival(data: IngestedData) -> MetricResult:
    """Whether the source is archived for the long term.

    Sources: Zenodo and Software Heritage references in the README, and
    resqui's ``archived_in_software_heritage`` and
    ``archived_in_scholarly_repository`` checks.

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
        "source_archival",
        {
            "Zenodo in README": readme_matches(data, r"zenodo\.org|10\.5281/zenodo"),
            "Software Heritage in README": readme_matches(
                data, r"softwareheritage\.org|swh:1:"
            ),
            "resqui Software Heritage check": resqui_verdict(
                data, "archived_in_software_heritage"
            ),
            "resqui scholarly repository check": resqui_verdict(
                data, "archived_in_scholarly_repository"
            ),
        },
        suggestion="Archive the source code in Software Heritage and on Zenodo.",
    )
