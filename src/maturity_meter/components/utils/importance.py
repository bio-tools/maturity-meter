"""How important each metric is to its dimension, defined in one place.

Every metric has an importance tier per dimension (a metric shared by two
dimensions can matter differently to each). The tier is the metric's weight
in the dimension's score (see :func:`aggregate_dimension`), and *essential*
metrics also cap it: strengths elsewhere cannot lift a dimension above its
essentials.

The tiers are informed judgements, not fitted to any data:

- the indicator guide's "keep" (*important*) and "maybe" (*supporting*);
- for FAIRness, the FAIR principles for research software (FAIR4RS, Barker et
  al. 2022): a licence (R1.1), accessible source code (A1) and documentation
  (R1) are what make reuse possible at all, so they are *essential*;
- for Security, OpenSSF Scorecard's own risk levels (High: vulnerabilities,
  branch protection, code review, dependency updates, binary artifacts;
  Medium: SAST, fuzzing, security policy);
- overlap: metrics measuring nearly the same thing (stars and forks, Borges
  et al. 2016) are not both weighted fully;
- coverage and robustness: metrics with known biases (code metrics depend on
  the language) or without an established benchmark are *supporting*.
"""

from enum import IntEnum


class Tier(IntEnum):
    """Importance of a metric to a dimension; the value is its weight."""

    SUPPORTING = 1
    IMPORTANT = 2
    ESSENTIAL = 3


IMPORTANCE: dict[str, dict[str, Tier]] = {
    "fairness": {
        # FAIR4RS R1.1: without a licence the software cannot legally be reused.
        "licensing": Tier.ESSENTIAL,
        # FAIR4RS A1: the source must be retrievable by its identifier.
        "source_availability": Tier.ESSENTIAL,
        # FAIR4RS R1: reuse needs a description of what it does and how.
        "documentation": Tier.ESSENTIAL,
        # FAIR4RS F1/F1.2: identifiers, and identified versions.
        "persistent_identifier": Tier.IMPORTANT,
        "releases_and_versioning": Tier.IMPORTANT,
        # FAIR4RS F2/I2 and F4: rich metadata, registered in a searchable place.
        "machine_readable_metadata": Tier.IMPORTANT,
        "registry_listing": Tier.IMPORTANT,
        # FAIR4RS R1.2 (provenance) and the software citation principles.
        "citation_and_credit": Tier.IMPORTANT,
        "installation_instructions": Tier.IMPORTANT,
        "software_tests": Tier.IMPORTANT,
        # Helpful but not required for reuse; several are "maybe" in the guide.
        "source_archival": Tier.SUPPORTING,
        "binary_distribution": Tier.SUPPORTING,
        "publications": Tier.SUPPORTING,
        "issue_tracking": Tier.SUPPORTING,
        "project_website": Tier.SUPPORTING,
        "contribution_and_governance": Tier.SUPPORTING,
        "containerization": Tier.SUPPORTING,
    },
    "compatibility": {
        # Standard (EDAM) data formats are what let tools be chained.
        "input_formats": Tier.IMPORTANT,
        "output_formats": Tier.IMPORTANT,
        "package_availability": Tier.IMPORTANT,
        "containerization": Tier.IMPORTANT,
        # "maybe" in the guide.
        "workflow_integration": Tier.SUPPORTING,
        # Keeps dependencies current rather than making the tool fit others.
        "dependency_management": Tier.SUPPORTING,
    },
    "maintainability": {
        "continuous_integration": Tier.IMPORTANT,
        "releases_and_versioning": Tier.IMPORTANT,
        "requirements_specified": Tier.IMPORTANT,
        # Code metrics depend strongly on the language and the code's purpose.
        "avg_ccn": Tier.SUPPORTING,
        "duplicate_rate": Tier.SUPPORTING,
        # Only the set-up is checked unless SuperLinter is enabled.
        "linting": Tier.SUPPORTING,
    },
    "scientific_impact": {
        # Field-normalized, so comparable across fields and publication years.
        "fwci": Tier.IMPORTANT,
        "citation_count": Tier.IMPORTANT,
        # Stars and forks correlate strongly; together they weigh like one.
        "star_count": Tier.SUPPORTING,
        "fork_count": Tier.SUPPORTING,
    },
    "security": {
        # Scorecard: Vulnerabilities is High risk, and a known critical
        # vulnerability is the most direct security problem.
        "vulnerability_management": Tier.ESSENTIAL,
        # Scorecard High: Branch-Protection, Code-Review.
        "change_control": Tier.IMPORTANT,
        # Scorecard High: Binary-Artifacts (and leaked credentials).
        "repository_hygiene": Tier.IMPORTANT,
        # Scorecard High: Dependency-Update-Tool.
        "dependency_management": Tier.IMPORTANT,
        # Scorecard Medium: SAST, Fuzzing (mostly memory-unsafe languages).
        "security_testing": Tier.SUPPORTING,
    },
    "sustainability": {
        # Not essential: mature, stable software may rightly be quiet.
        "development_activity": Tier.IMPORTANT,
        # The bus factor: a single developer is a sustainability risk.
        "inverse_simpson_index": Tier.IMPORTANT,
        "contribution_and_governance": Tier.IMPORTANT,
        # Only for tools with issues, and without an established benchmark.
        "issue_close_time": Tier.SUPPORTING,
        "resolved_issue_share": Tier.SUPPORTING,
    },
}
