"""FAIRness metrics.

One metric per merged indicator of the FAIRness sheet. Most are yes/no checks
that several sources answer (repository files and record, README, bio.tools,
OpenEBench, publications, RSEc and resqui checks); their verdicts are combined
with :func:`placeholder_reconcile` via :func:`verdict_metric`, so every source
with data contributes and the note names each one's verdict.
"""

from .citation import citation_information, publications_open_access
from .community import (
    code_quality_tooling,
    containerization,
    contribution_and_governance,
    issue_tracking,
    project_website,
)
from .documentation import documentation, installation_instructions, purpose_description
from .findability import (
    persistent_identifier,
    registry_listing,
    semantic_annotation,
    structured_metadata,
)
from .licensing import (
    copyright_and_attribution,
    license_declaration,
    open_source_license,
    per_file_licensing,
)
from .source_code import (
    automated_build,
    binary_distribution,
    releases_and_versioning,
    software_tests,
    source_archival,
    source_availability,
    version_control,
)

__all__ = [
    "automated_build",
    "binary_distribution",
    "citation_information",
    "code_quality_tooling",
    "containerization",
    "contribution_and_governance",
    "copyright_and_attribution",
    "documentation",
    "installation_instructions",
    "issue_tracking",
    "license_declaration",
    "open_source_license",
    "per_file_licensing",
    "persistent_identifier",
    "project_website",
    "publications_open_access",
    "purpose_description",
    "registry_listing",
    "releases_and_versioning",
    "semantic_annotation",
    "software_tests",
    "source_archival",
    "source_availability",
    "structured_metadata",
    "version_control",
]
