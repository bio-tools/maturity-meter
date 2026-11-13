"""FAIRness metrics.

One metric per concept. Most combine several aspects (distinct questions about
the concept), each answered by every source that can: repository files and
record, README, bio.tools, OpenEBench, FAIR-Checker, publications, RSEc and
resqui checks. See :func:`~maturity_meter.components.utils.checks.aspect_metric`.
"""

from maturity_meter.components.shared import (
    containerization,
    contribution_and_governance,
    releases_and_versioning,
)

from .citation import citation_and_credit, publications
from .community import issue_tracking, project_website
from .documentation import documentation, installation_instructions
from .findability import (
    machine_readable_metadata,
    persistent_identifier,
    registry_listing,
)
from .licensing import licensing
from .source_code import (
    binary_distribution,
    software_tests,
    source_archival,
    source_availability,
)

__all__ = [
    "binary_distribution",
    "citation_and_credit",
    "containerization",
    "contribution_and_governance",
    "documentation",
    "installation_instructions",
    "issue_tracking",
    "licensing",
    "machine_readable_metadata",
    "persistent_identifier",
    "project_website",
    "publications",
    "registry_listing",
    "releases_and_versioning",
    "software_tests",
    "source_archival",
    "source_availability",
]
