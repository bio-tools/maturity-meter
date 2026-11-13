"""Metrics that belong to more than one dimension.

A dimension uses a shared metric by importing it into its own ``metrics``
module; the lineage then lists it under every dimension that does.
"""

import re

from maturity_meter.components.utils.checks import (
    Aspect,
    aspect_metric,
    has_any_file,
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.files import DEPENDENCY_UPDATE_FILES
from maturity_meter.components.utils.sources import (
    biotools_types,
    file_name,
    has_file,
    openebench_metric,
    rsec_has,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult

_VERSION_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)?([-.+][\w.]+)?$", re.IGNORECASE)

# bio.tools link types that are a channel to reach the developers.
_CHANNEL_LINKS = {"Mailing list", "Helpdesk", "Discussion forum", "Social media"}


def dependency_management(data: IngestedData) -> MetricResult:
    """Whether dependencies are kept up to date by a tool.

    Sources: OpenSSF Scorecard's ``dependency_management`` check and a
    Dependabot or Renovate configuration file in the repository.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if a dependency update tool is used, 0 if not, or ``value=None``
        without a check or file list.
    """
    return verdict_metric(
        "dependency_management",
        {
            "OpenSSF Scorecard": resqui_verdict(data, "dependency_management"),
            "Dependabot/Renovate config": has_any_file(data, DEPENDENCY_UPDATE_FILES),
        },
        suggestion="Configure a dependency update tool such as Dependabot or Renovate.",
        missing="No dependency check or file list available.",
    )


def releases_and_versioning(data: IngestedData) -> MetricResult:
    """Whether the software is released, with conventional version numbers.

    Aspects and their sources:

    - releases: the latest GitHub/GitLab release and RSFC's ``has_releases``
      check;
    - version numbers: whether the latest release's tag looks like a version
      (e.g. ``v1.2.3``) and RSFC's ``versioning_standards_use`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if release information is
        unavailable.
    """
    repository = data.repository
    latest = repository.get("latest_release")
    tag = str((latest or {}).get("tag_name") or "")
    return aspect_metric(
        "releases_and_versioning",
        {
            "releases": Aspect(
                {
                    "repository releases": verdict(latest)
                    if "latest_release" in repository
                    else None,
                    "RSFC": resqui_verdict(data, "has_releases"),
                },
                "Publish versioned releases (e.g. tagged GitHub/GitLab releases).",
            ),
            "version numbers": Aspect(
                {
                    "version-like tag": float(bool(_VERSION_TAG.match(tag)))
                    if tag
                    else None,
                    "RSFC": resqui_verdict(data, "versioning_standards_use"),
                },
                "Tag releases with version numbers (e.g. v1.2.3).",
            ),
        },
        missing="Release information unavailable.",
    )


def contribution_and_governance(data: IngestedData) -> MetricResult:
    """Whether people can contribute and reach the developers.

    Aspects and their sources:

    - contribution guidelines: a CONTRIBUTING file and RSFC's
      ``has_contribution_guidelines`` check;
    - governance: GOVERNANCE and CODE_OF_CONDUCT files;
    - communication channels: RSFC's ``has_active_communication_channels``
      check, OpenEBench's support e-mail, and mailing-list, helpdesk or forum
      links in bio.tools.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    links = biotools_types(data, "link")
    return aspect_metric(
        "contribution_and_governance",
        {
            "contribution guidelines": Aspect(
                {
                    "CONTRIBUTING file": has_file(
                        data, lambda f: file_name(f).startswith("contributing")
                    ),
                    "RSFC": resqui_verdict(data, "has_contribution_guidelines"),
                },
                "Add a CONTRIBUTING.md describing how to contribute.",
            ),
            "governance": Aspect(
                {
                    "GOVERNANCE file": has_file(
                        data, lambda f: file_name(f).startswith("governance")
                    ),
                    "CODE_OF_CONDUCT file": has_file(
                        data,
                        lambda f: file_name(f).startswith(
                            ("code_of_conduct", "code-of-conduct")
                        ),
                    ),
                },
                "Describe the project's governance and a code of conduct.",
            ),
            "communication channels": Aspect(
                {
                    "RSFC": resqui_verdict(data, "has_active_communication_channels"),
                    "OpenEBench support e-mail": verdict(
                        openebench_metric(data, "support.email")
                    ),
                    "bio.tools links": None
                    if links is None
                    else float(bool(links & _CHANNEL_LINKS)),
                },
                "Offer a way to reach the developers (e.g. a forum or mailing list).",
            ),
        },
    )


def containerization(data: IngestedData) -> MetricResult:
    """Whether the software can run in a container or isolated environment.

    Sources: container definitions (Dockerfile, Containerfile, Singularity),
    conda environment files, BioContainers (RSEc), and RSFC's
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
            "BioContainers (RSEc)": rsec_has(
                data, lambda n: n.endswith("biocontainers.yaml")
            ),
            "RSFC": resqui_verdict(data, "software_is_containerized"),
        },
        suggestion="Provide a Dockerfile or a conda environment file.",
    )
