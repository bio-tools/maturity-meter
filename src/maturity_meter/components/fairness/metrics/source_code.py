"""FAIRness metrics on the source code: access, binaries, tests, archival."""

from maturity_meter.components.utils.checks import (
    Aspect,
    aspect_metric,
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.files import is_test_path
from maturity_meter.components.utils.reliability import (
    aggregator,
    assessment_tool,
    repository,
)
from maturity_meter.components.utils.sources import (
    biotools_types,
    has_file,
    openebench_metric,
    readme_matches,
    repo_record,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult


def source_availability(data: IngestedData) -> MetricResult:
    """Whether the source code is public, version-controlled and downloadable.

    Aspects and their sources:

    - public repository (evidence): the GitHub/GitLab repository's visibility,
      OpenEBench's public, online-repository and anonymous-access checks, and
      RSFC's ``version_control_use`` check;
    - free download (any): OpenEBench's free-source and source-package checks, and
      source-code downloads in bio.tools.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    repo = repo_record(data)
    downloads = biotools_types(data, "download")
    return aspect_metric(
        "source_availability",
        {
            "public repository": Aspect(
                {
                    # Without a repository record (not ingested) the
                    # visibility is unknown, not "private".
                    "public GitHub/GitLab repository": repository(
                        None
                        if repo is None
                        else float(
                            repo.get("visibility") == "public"
                            or repo.get("private") is False
                        )
                    ),
                    "OpenEBench public source": aggregator(
                        verdict(
                            openebench_metric(data, "distribution.sourcecode.public")
                        )
                    ),
                    "OpenEBench online repository": aggregator(
                        verdict(
                            openebench_metric(
                                data, "distribution.sourcecode.repository.online"
                            )
                        )
                    ),
                    "OpenEBench anonymous access": aggregator(
                        verdict(
                            openebench_metric(
                                data, "distribution.sourcecode.repository.anonymous"
                            )
                        )
                    ),
                    "RSFC version control": assessment_tool(
                        resqui_verdict(data, "version_control_use")
                    ),
                },
                "Develop the software in a public version-controlled repository.",
                rule="evidence",
            ),
            "free download": Aspect(
                {
                    "OpenEBench free source": verdict(
                        openebench_metric(data, "distribution.sourcecode.free")
                    ),
                    "OpenEBench source packages": verdict(
                        openebench_metric(data, "distribution.source_packages")
                    ),
                    "bio.tools source download": None
                    if downloads is None
                    else float("Source code" in downloads),
                },
                "Offer the source code as a free download (e.g. release archives).",
            ),
        },
    )


def binary_distribution(data: IngestedData) -> MetricResult:
    """Whether ready-to-use binaries can be downloaded.

    Sources (any one suffices): assets of the latest GitHub/GitLab release,
    binary downloads in bio.tools, and OpenEBench's free-binaries check.
    Package managers (Bioconda, Debian, PyPI) are assessed by Compatibility's
    ``package_availability``.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo_data = data.repository
    assets = None
    if "latest_release" in repo_data:
        latest = repo_data.get("latest_release") or {}
        release_assets = latest.get("assets")
        # GitHub lists assets directly; GitLab under assets.links (its
        # assets.sources are the automatic source archives).
        if isinstance(release_assets, dict):
            release_assets = release_assets.get("links")
        assets = float(bool(release_assets))
    downloads = biotools_types(data, "download")
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
        },
        rule="any",
        suggestion="Attach ready-to-use binaries to the releases.",
    )


def software_tests(data: IngestedData) -> MetricResult:
    """Whether the software comes with tests.

    Sources (weighed as evidence): test files or folders in the repository
    and RSFC's ``software_has_tests`` check. Whether the tests run automatically is
    assessed by Maintainability's ``continuous_integration``.

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
            "test files": repository(has_file(data, is_test_path)),
            "RSFC": assessment_tool(resqui_verdict(data, "software_has_tests")),
        },
        rule="evidence",
        suggestion="Add automated tests.",
    )


def source_archival(data: IngestedData) -> MetricResult:
    """Whether the source is archived for the long term.

    Sources (any one suffices): Zenodo and Software Heritage references in
    the README, and RSFC's ``archived_in_software_heritage`` and
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
            "RSFC Software Heritage": resqui_verdict(
                data, "archived_in_software_heritage"
            ),
            "RSFC scholarly repository": resqui_verdict(
                data, "archived_in_scholarly_repository"
            ),
        },
        rule="any",
        suggestion="Archive the source code in Software Heritage and on Zenodo.",
    )
