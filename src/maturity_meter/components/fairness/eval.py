from maturity_meter.components.utils.scaling import placeholder_dimension_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    binary_distribution,
    citation_and_credit,
    containerization,
    contribution_and_governance,
    documentation,
    installation_instructions,
    issue_tracking,
    licensing,
    machine_readable_metadata,
    persistent_identifier,
    project_website,
    publications,
    registry_listing,
    releases_and_versioning,
    software_tests,
    source_archival,
    source_availability,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        licensing(data),
        citation_and_credit(data),
        publications(data),
        registry_listing(data),
        persistent_identifier(data),
        machine_readable_metadata(data),
        documentation(data),
        installation_instructions(data),
        source_availability(data),
        releases_and_versioning(data),
        binary_distribution(data),
        software_tests(data),
        source_archival(data),
        issue_tracking(data),
        project_website(data),
        contribution_and_governance(data),
        containerization(data),
    ]
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
