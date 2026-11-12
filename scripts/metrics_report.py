#!/usr/bin/env python3
"""Create an ODS comparison of reported metrics in saved ingestion data."""

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from statistics import mean
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


class MetricCategory(Enum):
    COMPATIBILITY = "compatibility"
    FAIRNESS = "fairness"
    MAINTAINABILITY = "maintainability"
    SCIENTIFIC_IMPACT = "scientific impact"
    SECURITY = "security"
    SUSTAINABILITY = "sustainability"
    OTHER = "other"


EVERSE = "https://w3id.org/everse/i/indicators/"
FAIR = "https://w3id.org/fair/principles/terms/"
C = MetricCategory

# Categories per metric identifier. Bracketed list positions in identifiers
# (e.g. "[0]", "[doi=...]") are normalized to "[]" before lookup, so keys use "[]".
METRIC_CATEGORIES: dict[str, MetricCategory] = {
    **dict.fromkeys(
        [
            "input_formats_present",
            "output_formats_present",
            "container_distribution_file",
            "conda_distribution_file",
            "python_distribution_file",
            "rsec_debian_med",
            "rsec_bioconda",
            "rsec_biocontainers",
            "rsec_galaxy",
        ],
        C.COMPATIBILITY,
    ),
    **dict.fromkeys(
        [
            # EVERSE indicators
            f"{EVERSE}{name}"
            for name in (
                "software_has_citation",
                "software_has_license",
                "software_has_license_for_file_types",
                "descriptive_metadata",
                "listed_in_registry",
                "persistent_and_unique_identifier",
                "software_has_documentation",
                "archived_in_scholarly_repository",
                "archived_in_software_heritage",
                "codemeta_completeness",
                "software_has_tests",
                "version_control_use",
                "versioning_standards_use",
            )
        ]
        + [
            f"{FAIR}{name}"
            for name in ("F1A", "F1B", "F2A", "F2B", "I1", "I2", "I3", "R11")
        ]
        + [
            # OpenEBench
            "deprecated",
            "distribution.binaries.freeness",
            "distribution.binaries.registration",
            "distribution.packages",
            "distribution.source_packages",
            "distribution.sourcecode.free",
            "distribution.sourcecode.interpreted",
            "distribution.sourcecode.license",
            "distribution.sourcecode.public",
            "distribution.sourcecode.readme",
            "distribution.sourcecode.repository.anonymous",
            "distribution.sourcecode.repository.online",
            "project.documentation.api",
            "project.documentation.general",
            "project.documentation.manual",
            "project.license.open_source",
            "project.license.osi",
            "project.publications[].entries[].pmcid",
            "project.publications[].entries[].refs[].count",
            "project.readme",
            "project.summary.description",
            "project.website.access_time",
            "project.website.bioschemas",
            "project.website.copyright",
            "project.website.half_year_stat[].days",
            "project.website.half_year_stat[].serie[]",
            "project.website.half_year_stat[].status",
            "project.website.https",
            "project.website.last_check",
            "project.website.last_month_access.average_access_time",
            "project.website.last_month_access.downtime_days",
            "project.website.last_month_access.uptime_days",
            "project.website.license",
            "project.website.operational",
            "project.website.redirects[].status",
            "project.website.redirects[].url",
            "project.website.ssl",
            "support.email",
            "support.issue_tracking.public_tracker",
            "support.issue_tracking.resolve_time",
            # Publications
            "publication.isOpenAccess",
        ],
        C.FAIRNESS,
    ),
    **dict.fromkeys(
        [
            f"{EVERSE}{name}"
            for name in (
                "maintainability_index_ok",
                "has_ci-tests",
                "project_is_active",
                "has_active_communication_channels",
                "has_releases",
                "repository_workflows",
                "requirements_specified",
                "has_no_linting_issues",
            )
        ]
        + [
            # Lizard
            "avg_ccn",
            "duplicate_rate",
            "files",
            "functions",
            "nloc_per_file",
            "total_ccn",
            "total_nloc",
        ],
        C.MAINTAINABILITY,
    ),
    **dict.fromkeys(
        [
            "stars",
            "forks",
            "project.publications[].entries[].cit_count",
            "project.publications[].entries[].citations[].count",
            "publication.citationCount",
            "publication.citedByCount",
            "publication.cited_by_count",
            "publication.fwci",
        ],
        C.SCIENTIFIC_IMPACT,
    ),
    "project.publications[].entries[].ref_count": C.OTHER,
    **dict.fromkeys(
        [
            "default_branch_protected",
            *(
                f"{EVERSE}{name}"
                for name in (
                    "no_leaked_credentials",
                    "has_no_binary_artifacts",
                    "human_code_review_requirement",
                    "no_critical_vulnerability",
                    "static_analysis_common_vulnerabilities",
                    "uses_fuzzing",
                )
            ),
        ],
        C.SECURITY,
    ),
    **dict.fromkeys(
        [
            "open_issues",
            *(
                f"{EVERSE}{name}"
                for name in (
                    "dependency_management",
                    "has_published_package",
                    "has_contribution_guidelines",
                    "software_is_containerized",
                )
            ),
        ],
        C.SUSTAINABILITY,
    ),
}

FAIRNESS_INDICATORS: dict[str, tuple[str, ...]] = {
    "License declarations": (
        f"{EVERSE}software_has_license",
        "distribution.sourcecode.license",
        "project.website.license",
        "fair_license_file",
        "fair_biotools_license",
    ),
    "Open-source license recognition": (
        "project.license.open_source",
        "project.license.osi",
    ),
    "Copyright and attribution": (
        "project.website.copyright",
        "fair_biotools_credits",
        "fair_attribution_file",
    ),
    "Software citation information": (
        f"{EVERSE}software_has_citation",
        "project.documentation.citation",
        "fair_citation_file",
    ),
    "Associated publications and open access": (
        "publication.isOpenAccess",
        "project.publications[].entries[].pmcid",
        "fair_biotools_publications",
    ),
    "Software registry registration": (
        f"{EVERSE}listed_in_registry",
        "fair_biotools_registry",
        "fair_rsec_registry",
    ),
    "Persistent and unique identifiers": (f"{EVERSE}persistent_and_unique_identifier",),
    "Structured descriptive metadata": (
        f"{EVERSE}descriptive_metadata",
        f"{EVERSE}codemeta_completeness",
        "fair_codemeta_file",
    ),
    "Semantic metadata and community standards": (
        "project.website.bioschemas",
        "fair_biotools_topics",
        "fair_biotools_operations",
    ),
    "Documentation availability and quality signals": (
        f"{EVERSE}software_has_documentation",
        "project.documentation.api",
        "project.documentation.general",
        "project.documentation.manual",
        "project.readme",
        "distribution.sourcecode.readme",
        "fair_docs_directory",
        "fair_biotools_documentation",
    ),
    "Software purpose and design descriptions": (
        "project.summary.description",
        "fair_biotools_description",
    ),
    "Installation, build and dependency information": (
        f"{EVERSE}requirements_specified",
        "fair_dependency_manifest",
        "fair_biotools_installation_docs",
    ),
    "Source repository availability and version control": (
        f"{EVERSE}version_control_use",
        "distribution.sourcecode.repository.anonymous",
        "distribution.sourcecode.repository.online",
        "fair_repository_public",
    ),
    "Releases and versioning conventions": (
        f"{EVERSE}has_releases",
        f"{EVERSE}versioning_standards_use",
    ),
    "Software testing and installation checks": (
        f"{EVERSE}software_has_tests",
        f"{EVERSE}has_ci-tests",
        "fair_test_files",
    ),
    "Source distributions and access restrictions": (
        "distribution.source_packages",
        "distribution.sourcecode.free",
        "distribution.sourcecode.public",
        "fair_biotools_source_download",
    ),
    "Binaries, packages and distribution access": (
        "distribution.binaries.freeness",
        "distribution.binaries.registration",
        "distribution.packages",
        "fair_biotools_binary_download",
        "fair_release_assets",
    ),
    "Source archival and long-term preservation": (
        f"{EVERSE}archived_in_software_heritage",
        f"{EVERSE}archived_in_scholarly_repository",
    ),
    "Linting, static analysis and compiler warnings": (
        f"{EVERSE}has_no_linting_issues",
        f"{EVERSE}static_analysis_common_vulnerabilities",
        "fair_linter_config",
    ),
    "Issue tracking and resolution": (
        "support.issue_tracking.public_tracker",
        "support.issue_tracking.resolve_time",
        "open_issues",
        "fair_repository_issues",
    ),
    "Project website and discoverability": (
        "project.website.access_time",
        "project.website.operational",
        "project.website.https",
        "project.website.ssl",
        "project.website.last_check",
        "project.website.half_year_stat[].days",
        "project.website.half_year_stat[].serie[]",
        "project.website.half_year_stat[].status",
        "project.website.last_month_access.average_access_time",
        "project.website.last_month_access.downtime_days",
        "project.website.last_month_access.uptime_days",
        "project.website.redirects[].status",
        "project.website.redirects[].url",
    ),
    "Contribution policy and project governance": (
        f"{EVERSE}has_contribution_guidelines",
        "fair_contributing_file",
        "fair_governance_file",
    ),
}

FAIRNESS_BY_IDENTIFIER = {
    identifier: name
    for name, identifiers in FAIRNESS_INDICATORS.items()
    for identifier in identifiers
}
MAINTAINABILITY_INDICATORS = {
    "avg_ccn": "Average CC per function",
    "duplicate_rate": "Fraction of duplicate code",
    f"{EVERSE}has_ci-tests": "Continuous integration tests",
    f"{EVERSE}has_releases": "Software has releases",
    f"{EVERSE}requirements_specified": "Requirements specified",
    f"{EVERSE}has_no_linting_issues": "No linting issues",
}
SECURITY_INDICATORS = {
    "default_branch_protected": "If the default branch is protected",
    "has_security_policy": "Has security policy file",
    "has_gitignore": "Has gitignore file",
    f"{EVERSE}no_leaked_credentials": "No leaked credentials",
    f"{EVERSE}dependency_management": "Dependency management",
    f"{EVERSE}has_no_binary_artifacts": "No binary artifacts",
    f"{EVERSE}no_critical_vulnerability": "No critical vulnerabilities",
    f"{EVERSE}static_analysis_common_vulnerabilities": "Security static analysis",
    f"{EVERSE}human_code_review_requirement": "Human code review",
    f"{EVERSE}uses_fuzzing": "Uses fuzzing",
}
SUSTAINABILITY_INDICATORS = {
    "avg_issue_close_time_days": "Average issue closing time",
    "support.issue_tracking.resolve_time": "Issue resolution time (OpenEBench)",
    "open_issues": "Number of open issues",
    "days_since_last_push": "Days since last push",
    "days_since_last_project_activity": "Days since last project activity",
    "inverse_simpson_index": "Contributor diversity (inverse Simpson index)",
    f"{EVERSE}has_contribution_guidelines": "Contribution guidelines",
    "fair_contributing_file": "Contribution guidelines",
    f"{EVERSE}software_is_containerized": "Container build definition",
    f"{EVERSE}has_published_package": "Published software package",
}
FAIR_CHECKER_GROUPS = {
    "F1A": "Persistent and unique identifiers",
    "F1B": "Persistent and unique identifiers",
    "F2A": "Structured descriptive metadata",
    "I1": "Structured descriptive metadata",
    "F2B": "Semantic metadata and community standards",
    "I2": "Semantic metadata and community standards",
    "R13": "Semantic metadata and community standards",
    "R11": "License declarations",
}
DISCARDED_FAIRNESS_METRICS = {
    f"{EVERSE}software_has_license_for_file_types",
    f"{EVERSE}software_is_containerized",
    "project.build",
}


def fairness_indicator(source: str, identifier: str) -> str | None:
    normalized = re.sub(r"\[[^\]]*\]", "[]", identifier)
    if source in ("FAIRChecker", "FAIRChecker API"):
        return FAIR_CHECKER_GROUPS.get(identifier.rsplit("/", 1)[-1])
    return FAIRNESS_BY_IDENTIFIER.get(normalized)


def metric_category(identifier: str) -> MetricCategory | None:
    """Return the category of a metric, or None when unknown."""
    return METRIC_CATEGORIES.get(re.sub(r"\[[^\]]*\]", "[]", identifier))


@dataclass(frozen=True, order=True)
class Metric:
    source: str
    identifier: str
    expected_range: str = ""
    # Derived from the identifier, so it is excluded from comparison and hashing.
    category: MetricCategory | None = field(init=False, compare=False, default=None)

    def __post_init__(self) -> None:
        category = metric_category(self.identifier)
        if fairness_indicator(self.source, self.identifier):
            category = C.FAIRNESS
        elif self.identifier in SECURITY_INDICATORS:
            category = C.SECURITY
        elif self.identifier in SUSTAINABILITY_INDICATORS:
            category = C.SUSTAINABILITY
        elif (
            self.identifier in DISCARDED_FAIRNESS_METRICS
            or (
                self.source == "OpenEBench"
                and self.identifier.startswith("project.build.")
            )
            or category == C.FAIRNESS
            or (
                category == C.MAINTAINABILITY
                and self.identifier not in MAINTAINABILITY_INDICATORS
            )
            or self.source
            in (
                "FAIRChecker",
                "FAIRChecker API",
            )
        ):
            category = C.OTHER
        object.__setattr__(self, "category", category)


def category_label(metric: Metric) -> str | None:
    original = metric_category(metric.identifier)
    categories = [metric.category] if metric.category else []
    if (
        metric.category == C.FAIRNESS
        and original not in (None, C.FAIRNESS)
        and (
            (
                original != C.MAINTAINABILITY
                or metric.identifier in MAINTAINABILITY_INDICATORS
            )
            and (
                original != C.SUSTAINABILITY
                or metric.identifier in SUSTAINABILITY_INDICATORS
            )
        )
    ):
        categories.append(original)
    if metric.identifier in SECURITY_INDICATORS and C.SECURITY not in categories:
        categories.append(C.SECURITY)
    if metric.category == C.SECURITY and original not in (
        None,
        C.SECURITY,
        C.SUSTAINABILITY,
    ):
        categories.append(original)
    if (
        metric.identifier in SUSTAINABILITY_INDICATORS
        and C.SUSTAINABILITY not in categories
    ):
        categories.append(C.SUSTAINABILITY)
    return ", ".join(category.value.title() for category in categories) or None


SUPERLINTER_METRIC = Metric(
    "SuperLinter", f"{EVERSE}has_no_linting_issues", "true / false"
)


REPOSITORY_METRICS = {
    "stargazers_count": ("stars", ">= 0"),
    "star_count": ("stars", ">= 0"),
    "forks_count": ("forks", ">= 0"),
}
CODE_RANGES = {
    "files": ">= 0",
    "functions": ">= 0",
    "total_nloc": ">= 0",
    "total_ccn": ">= 0",
    "avg_ccn": ">= 0",
    "nloc_per_file": ">= 0",
    "duplicate_rate": "0–100%",
}
PUBLICATION_FIELDS = {
    "openalex": {"cited_by_count": ">= 0", "fwci": ">= 0"},
    "europe_pmc": {"citedByCount": ">= 0", "isOpenAccess": "Y / N"},
}
BOOLEAN_CHECKS = {
    "https://w3id.org/everse/i/indicators/software_has_citation",
    "https://w3id.org/everse/i/indicators/no_leaked_credentials",
    "https://w3id.org/everse/i/indicators/software_has_license",
    "https://w3id.org/everse/i/indicators/dependency_management",
    "https://w3id.org/everse/i/indicators/has_ci-tests",
    "https://w3id.org/everse/i/indicators/has_no_linting_issues",
    "https://w3id.org/everse/i/indicators/human_code_review_requirement",
}
METRIC_DESCRIPTIONS = {
    "input_formats_present": "Whether bio.tools lists an input format.",
    "output_formats_present": "Whether bio.tools lists an output format.",
    "container_distribution_file": (
        "Whether the repository file list contains a Dockerfile or Containerfile."
    ),
    "conda_distribution_file": "Whether the repository file list contains meta.yaml.",
    "python_distribution_file": (
        "Whether the repository file list contains pyproject.toml, setup.py "
        "or setup.cfg."
    ),
    "rsec_debian_med": "Whether RSEc lists a Debian Med metadata file.",
    "rsec_bioconda": "Whether RSEc lists a Bioconda metadata file.",
    "rsec_biocontainers": "Whether RSEc lists a BioContainers metadata file.",
    "rsec_galaxy": "Whether RSEc lists a Galaxy metadata file.",
    "stars": "Number of repository stars.",
    "forks": "Number of repository forks.",
    "open_issues": "Number of open issues, excluding pull requests.",
    "default_branch_protected": "Whether the default branch is protected.",
    "has_security_policy": (
        "Whether the repository file list contains a SECURITY.md file."
    ),
    "has_gitignore": "Whether the repository file list contains a .gitignore file.",
    "avg_issue_close_time_days": (
        "Mean days between creation and closure in the saved, capped issue sample."
    ),
    "days_since_last_push": (
        "Days since GitHub's last recorded push, as of report time."
    ),
    "days_since_last_project_activity": (
        "Days since GitLab's last project activity, as of report time; "
        "not a commit date."
    ),
    "inverse_simpson_index": (
        "Inverse Simpson index of saved contributor commit shares, excluding "
        "recognizable bot names; contributor lists may be capped."
    ),
    "files": "Number of files analyzed by Lizard.",
    "functions": "Number of functions analyzed by Lizard.",
    "total_nloc": "Total lines of code in analyzed functions.",
    "total_ccn": "Total cyclomatic complexity of analyzed functions.",
    "avg_ccn": "Average cyclomatic complexity per function.",
    "nloc_per_file": "Function lines of code per analyzed file.",
    "duplicate_rate": "Percentage of duplicate code reported by Lizard.",
    "publication.citationCount": "Citation count reported for each publication.",
    "publication.cited_by_count": "Citation count reported for each publication.",
    "publication.citedByCount": "Citation count reported for each publication.",
    "publication.fwci": "Field-weighted citation impact for each publication.",
    "publication.isOpenAccess": "Open-access status reported for each publication.",
    "project.publications[].entries[].cit_count": (
        "Citation count for each publication."
    ),
    "project.publications[].entries[].ref_count": (
        "Reference count for each publication."
    ),
    "project.publications[].entries[].citations[].count": (
        "Citation count by year for each publication."
    ),
    "project.website.access_time": "Website response time reported by OpenEBench.",
    "project.website.operational": "Website HTTP status reported by OpenEBench.",
    "project.website.last_month_access.uptime_days": (
        "Number of days the website was available in the last month."
    ),
    "project.website.last_month_access.downtime_days": (
        "Number of days the website was unavailable in the last month."
    ),
    "software_has_citation": "Whether a valid citation file was found.",
    "no_leaked_credentials": "Whether the credential scan found no leaks.",
    "software_has_license": "Whether a license file was found.",
    "dependency_management": "Whether dependency update tooling was detected.",
    "has_ci-tests": "Whether changes were checked by CI tests.",
    "human_code_review_requirement": "Whether changes received human review.",
    "has_no_linting_issues": (
        "Whether SuperLinter reported no linting issues; blank if not assessed."
    ),
    "F1A": "FAIR-Checker result for unique identifiers.",
    "F1B": "FAIR-Checker result for persistent identifiers.",
    "F2A": "FAIR-Checker result for structured metadata.",
    "F2B": "FAIR-Checker result for shared metadata vocabularies.",
    "I1": "FAIR-Checker result for machine-readable format.",
    "I2": "FAIR-Checker result for shared ontologies.",
    "I3": "FAIR-Checker result for external links.",
    "R11": "FAIR-Checker result for license metadata.",
}
NAMESPACES = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def tag(prefix: str, name: str) -> str:
    return f"{{{NAMESPACES[prefix]}}}{name}"


def scalar(value: Any) -> str | int | float | bool:
    if isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(f"Expected a scalar metric value, got {type(value).__name__}")


def metric_name(metric: Metric) -> str:
    identifier = metric.identifier.rsplit("/", 1)[-1]
    fair_names = {
        "F1A": "Unique identifiers",
        "F1B": "Persistent identifiers",
        "F2A": "Structured metadata",
        "F2B": "Shared metadata vocabularies",
        "I1": "Machine-readable format",
        "I2": "Shared ontologies",
        "I3": "External links",
        "R11": "License metadata",
    }
    if identifier in fair_names and metric.source in ("FAIRChecker", "FAIRChecker API"):
        name = fair_names[identifier]
    else:
        name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", identifier).replace("_", " ")
    groups = [
        group
        for group in (
            fairness_indicator(metric.source, metric.identifier),
            MAINTAINABILITY_INDICATORS.get(metric.identifier),
            SECURITY_INDICATORS.get(metric.identifier),
            SUSTAINABILITY_INDICATORS.get(metric.identifier),
        )
        if group
    ]
    return " — ".join([*groups, name])


def metric_description(metric: Metric) -> str:
    key = metric.identifier.rsplit("/", 1)[-1]
    if key.startswith("fair_"):
        name = key.removeprefix("fair_").replace("_", " ")
        return f"Derived presence of {name} in {metric.source}."
    return METRIC_DESCRIPTIONS.get(
        key, f"{metric.source} reported value for {metric_name(metric)}."
    )


def fairness_presence_metrics(data: dict[str, Any]) -> dict[Metric, bool]:
    """Derive separate presence evidence, without reconciling source results."""
    result: dict[Metric, bool] = {}

    def add(source: str, identifier: str, value: bool) -> None:
        result[Metric(source, identifier, "true / false")] = value

    repository = data.get("repository") or {}
    files = repository.get("files")
    if files is not None:
        if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
            raise ValueError("repository.files must be a list of paths")
        paths = [PurePosixPath(f.lower()) for f in files]
        names = [path.name for path in paths]
        file_types = {
            "fair_license_file": any(
                n.startswith(("license", "licence", "copying")) for n in names
            ),
            "fair_attribution_file": any(
                n.startswith(("authors", "contributors", "credits")) for n in names
            ),
            "fair_citation_file": any(n.startswith("citation") for n in names),
            "fair_codemeta_file": "codemeta.json" in names,
            "fair_docs_directory": any(
                path.parts and path.parts[0] in ("docs", "doc") for path in paths
            ),
            "fair_dependency_manifest": any(
                n
                in {
                    "requirements.txt",
                    "pyproject.toml",
                    "setup.py",
                    "setup.cfg",
                    "pipfile",
                    "environment.yml",
                    "environment.yaml",
                    "package.json",
                    "description",
                    "renv.lock",
                    "cargo.toml",
                    "go.mod",
                    "pom.xml",
                    "build.gradle",
                    "build.gradle.kts",
                    "gemfile",
                    "cpanfile",
                    "project.toml",
                    "conanfile.txt",
                    "vcpkg.json",
                }
                for n in names
            ),
            "fair_test_files": any(
                any(
                    part in ("test", "tests", "testing", "__tests__", "spec")
                    for part in path.parts[:-1]
                )
                or path.name.startswith("test_")
                or "_test." in path.name
                or ".test." in path.name
                for path in paths
            ),
            "fair_linter_config": any(
                n
                in {
                    ".pre-commit-config.yaml",
                    ".flake8",
                    "ruff.toml",
                    ".ruff.toml",
                    ".pylintrc",
                    ".golangci.yml",
                    ".golangci.yaml",
                    ".lintr",
                    ".clang-tidy",
                    ".clang-format",
                    ".rubocop.yml",
                    ".prettierrc",
                    "biome.json",
                    ".markdownlint.yaml",
                }
                or n.startswith(".eslintrc")
                for n in names
            ),
            "fair_contributing_file": any(n.startswith("contributing") for n in names),
            "fair_governance_file": any(n.startswith("governance") for n in names),
        }
        for identifier, found in file_types.items():
            if found or not repository.get("files_truncated"):
                add("Repository files", identifier, found)

    repo = repository.get("repo")
    if isinstance(repo, dict):
        if isinstance(repo.get("private"), bool):
            add("Repository", "fair_repository_public", not repo["private"])
        elif isinstance(repo.get("visibility"), str):
            add("Repository", "fair_repository_public", repo["visibility"] == "public")
        if isinstance(repo.get("has_issues"), bool):
            add("Repository", "fair_repository_issues", repo["has_issues"])
    release = repository.get("latest_release")
    if isinstance(release, dict):
        assets = release.get("assets")
        if isinstance(assets, dict):
            assets = assets.get("links")
        if isinstance(assets, list):
            add("Repository", "fair_release_assets", bool(assets))

    biotools = data.get("biotools")
    if biotools is not None:
        if not isinstance(biotools, dict):
            raise ValueError("biotools must be an object")
        if biotools:
            add("bio.tools", "fair_biotools_registry", True)
        for key, identifier in (
            ("license", "fair_biotools_license"),
            ("credit", "fair_biotools_credits"),
            ("publication", "fair_biotools_publications"),
            ("documentation", "fair_biotools_documentation"),
            ("description", "fair_biotools_description"),
            ("topic", "fair_biotools_topics"),
        ):
            if key in biotools and biotools[key] is not None:
                add("bio.tools", identifier, bool(biotools[key]))
        for key, identifiers in (
            (
                "documentation",
                {"installation instructions": "fair_biotools_installation_docs"},
            ),
            (
                "download",
                {
                    "source code": "fair_biotools_source_download",
                    "binaries": "fair_biotools_binary_download",
                },
            ),
        ):
            entries = biotools.get(key)
            if entries is not None:
                if not isinstance(entries, list) or not all(
                    isinstance(e, dict) for e in entries
                ):
                    raise ValueError(f"biotools.{key} must be a list of objects")
                types = set()
                for entry in entries:
                    value = entry.get("type")
                    if isinstance(value, str):
                        types.add(value.lower())
                    elif isinstance(value, list) and all(
                        isinstance(v, str) for v in value
                    ):
                        types.update(v.lower() for v in value)
                    elif value is not None:
                        raise ValueError(
                            f"biotools.{key} type must be a string or list of strings"
                        )
                for type_name, identifier in identifiers.items():
                    add("bio.tools", identifier, type_name in types)
        functions = biotools.get("function")
        if functions is not None:
            if not isinstance(functions, list) or not all(
                isinstance(f, dict) for f in functions
            ):
                raise ValueError("biotools.function must be a list of objects")
            add(
                "bio.tools",
                "fair_biotools_operations",
                any(f.get("operation") for f in functions),
            )
    rsec = data.get("rsec")
    if isinstance(rsec, dict) and isinstance(rsec.get("files"), list):
        add("RSEc", "fair_rsec_registry", True)
    return result


def security_presence_metrics(data: dict[str, Any]) -> dict[Metric, bool]:
    """Derive file presence without treating an incomplete list as absence."""
    repository = data.get("repository") or {}
    files = repository.get("files")
    if files is None:
        return {}
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise ValueError("repository.files must be a list of paths")
    names = {PurePosixPath(path.lower()).name for path in files}
    checks = {
        "has_security_policy": "security.md" in names,
        "has_gitignore": ".gitignore" in names,
    }
    return {
        Metric("Repository files", identifier, "true / false"): found
        for identifier, found in checks.items()
        if found or not repository.get("files_truncated")
    }


def parse_timestamp(value: str) -> datetime:
    """Parse an ISO timestamp with an explicit timezone."""
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise ValueError(f"Invalid timestamp: {value!r}") from error
    if timestamp.utcoffset() is None:
        raise ValueError(f"Timestamp must include a timezone: {value!r}")
    return timestamp.astimezone(UTC)


def sustainability_metrics(
    repository: dict[str, Any], host: str, as_of: datetime
) -> dict[Metric, float]:
    result: dict[Metric, float] = {}
    issues = repository.get("closed_issues")
    if issues is not None:
        if not isinstance(issues, list):
            raise ValueError("repository.closed_issues must be a list")
        durations = []
        for issue in issues:
            if not isinstance(issue, dict):
                raise ValueError("closed issue must be an object")
            created, closed = issue.get("created_at"), issue.get("closed_at")
            if created is None or closed is None:
                raise ValueError(
                    "closed issue is missing creation or closure timestamp"
                )
            days = (
                parse_timestamp(closed) - parse_timestamp(created)
            ).total_seconds() / 86400
            if days < 0:
                raise ValueError("closed issue predates its creation")
            durations.append(days)
        if durations:
            result[Metric(host, "avg_issue_close_time_days", ">= 0 days")] = mean(
                durations
            )

    record = repository.get("repo") or {}
    timestamp_field = "pushed_at" if host == "GitHub" else "last_activity_at"
    identifier = (
        "days_since_last_push"
        if host == "GitHub"
        else "days_since_last_project_activity"
    )
    timestamp = record.get(timestamp_field)
    if timestamp is not None:
        days = (as_of - parse_timestamp(timestamp)).total_seconds() / 86400
        if days < 0:
            raise ValueError(
                f"{timestamp_field} is later than the report reference time"
            )
        result[Metric(host, identifier, ">= 0 days")] = days

    contributors = repository.get("contributors")
    if contributors is not None:
        if not isinstance(contributors, list):
            raise ValueError("repository.contributors must be a list")
        counts = []
        for contributor in contributors:
            if not isinstance(contributor, dict):
                raise ValueError("contributor must be an object")
            count = contributor.get("contributions")
            name = contributor.get("name")
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ValueError(
                    "contributor contributions must be a non-negative integer"
                )
            if name is not None and not isinstance(name, str):
                raise ValueError("contributor name must be a string or null")
            lowered = (name or "").lower()
            is_bot = lowered.endswith(("[bot]", " bot")) or lowered == "bot"
            if count and not is_bot:
                counts.append(count)
        total = sum(counts)
        if total:
            result[Metric(host, "inverse_simpson_index", ">= 1")] = 1 / sum(
                (count / total) ** 2 for count in counts
            )
    return result


def compatibility_metrics(data: dict[str, Any]) -> dict[Metric, bool]:
    """Derive source-specific presence indicators from available source lists."""
    result: dict[Metric, bool] = {}

    def add(source: str, identifier: str, value: bool) -> None:
        result[Metric(source, identifier, "true / false")] = value

    biotools = data.get("biotools")
    if biotools is not None:
        if not isinstance(biotools, dict):
            raise ValueError("biotools must be an object")
        functions = biotools.get("function")
        if functions is not None:
            if not isinstance(functions, list):
                raise ValueError("biotools.function must be a list")
            for direction in ("input", "output"):
                found = False
                for function in functions:
                    if not isinstance(function, dict):
                        raise ValueError("biotools.function entries must be objects")
                    entries = function.get(direction)
                    if entries is None:
                        entries = []
                    if not isinstance(entries, list):
                        raise ValueError(
                            f"biotools.function.{direction} must be a list"
                        )
                    for entry in entries:
                        if not isinstance(entry, dict):
                            raise ValueError(
                                f"bio.tools {direction} entries must be objects"
                            )
                        formats = entry.get("format")
                        if formats is None:
                            formats = []
                        if not isinstance(formats, list):
                            raise ValueError(
                                f"bio.tools {direction} formats must be a list"
                            )
                        for fmt in formats:
                            if not isinstance(fmt, dict):
                                raise ValueError("bio.tools formats must be objects")
                            found |= any(
                                isinstance(fmt.get(key), str) and bool(fmt[key].strip())
                                for key in ("uri", "term")
                            )
                add("bio.tools", f"{direction}_formats_present", found)

    repository = data.get("repository") or {}
    files = repository.get("files")
    if files is not None:
        if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
            raise ValueError("repository.files must be a list of paths")
        names = [PurePosixPath(path.lower()).name for path in files]
        found_types = {
            "container_distribution_file": any(
                name.startswith(("dockerfile", "containerfile")) for name in names
            ),
            "conda_distribution_file": "meta.yaml" in names,
            "python_distribution_file": any(
                name in {"pyproject.toml", "setup.py", "setup.cfg"} for name in names
            ),
        }
        for identifier, found in found_types.items():
            if found or not repository.get("files_truncated"):
                add("Repository files", identifier, found)

    rsec = data.get("rsec")
    if rsec is not None:
        if not isinstance(rsec, dict):
            raise ValueError("rsec must be an object")
        files = rsec.get("files")
        if files is not None:
            if not isinstance(files, list) or not all(
                isinstance(f, str) for f in files
            ):
                raise ValueError("rsec.files must be a list of names")
            names = [name.lower() for name in files]
            add(
                "RSEc",
                "rsec_debian_med",
                any(n.endswith(".debian.yaml") for n in names),
            )
            add(
                "RSEc",
                "rsec_bioconda",
                any(n.startswith("bioconda_") and n.endswith(".yaml") for n in names),
            )
            add(
                "RSEc",
                "rsec_biocontainers",
                any(n.endswith("biocontainers.yaml") for n in names),
            )
            add("RSEc", "rsec_galaxy", any(n.endswith(".galaxy.json") for n in names))

    return result


def reported_metrics(
    data: dict[str, Any],
    *,
    input_path: Path | None = None,
    as_of: datetime | None = None,
) -> dict[Metric, str | int | float | bool]:
    """Extract reported values and source-specific compatibility evidence."""
    result: dict[Metric, str | int | float | bool] = {}
    publication_values: dict[Metric, list[dict[str, Any]]] = {}

    def add(source: str, identifier: str, value: Any, expected_range: str = "") -> None:
        if value is None:
            return
        metric = Metric(source, identifier, expected_range)
        reported = scalar(value)
        if metric in result and result[metric] != reported:
            raise ValueError(f"Conflicting values for {source}: {identifier}")
        result[metric] = reported

    def add_publication(
        source: str,
        identifier: str,
        value: Any,
        context: dict[str, Any],
        expected_range: str = "",
    ) -> None:
        if value is not None:
            metric = Metric(source, identifier, expected_range)
            publication_values.setdefault(metric, []).append(
                {**context, "value": scalar(value)}
            )

    request = data.get("request") or {}
    if not isinstance(request, dict) or not isinstance(request.get("repository"), str):
        raise ValueError("Missing request.repository in saved ingestion data")
    repository = data.get("repository") or {}
    if not isinstance(repository, dict):
        raise ValueError("repository must be an object")
    result.update(compatibility_metrics(data))
    result.update(fairness_presence_metrics(data))
    result.update(security_presence_metrics(data))
    host = (
        "GitHub"
        if request["repository"].split("/")[2].lower() == "github.com"
        else "GitLab"
    )
    result.update(sustainability_metrics(repository, host, as_of or datetime.now(UTC)))
    repo = repository.get("repo") or {}
    for field_name, (identifier, expected_range) in REPOSITORY_METRICS.items():
        if field_name in repo:
            add(host, identifier, repo[field_name], expected_range)
    add(host, "open_issues", repository.get("open_issues"), ">= 0")
    add(
        host,
        "default_branch_protected",
        repository.get("default_branch_protected"),
        "true / false",
    )

    for field_name, value in (data.get("code_metrics") or {}).items():
        add("Lizard", field_name, value, CODE_RANGES.get(field_name, ""))

    quality = data.get("quality_checks") or {}
    grouped_checks: dict[Metric, list[dict[str, Any]]] = {}
    for check in quality.get("checks", []):
        indicator = check.get("assessesIndicator", {}).get("@id")
        source = check.get("checkingSoftware", {}).get("name")
        if not indicator or not source:
            raise ValueError("A quality check is missing its indicator ID or source")
        value = check.get("output")
        expected = "true / false" if indicator in BOOLEAN_CHECKS else ""
        if value is not None:
            metric = Metric(source, indicator, expected)
            grouped_checks.setdefault(metric, []).append(
                {
                    "output": scalar(value),
                    "process": check.get("process"),
                    "status": check.get("status", {}).get("@id"),
                    "evidence": check.get("evidence"),
                }
            )
    for metric, checks in grouped_checks.items():
        result[metric] = (
            checks[0]["output"]
            if len(checks) == 1
            else json.dumps(checks, ensure_ascii=False)
        )

    # Keep direct API scores distinct from resqui's derived true/false outputs.
    for node in data.get("fair_checker") or []:
        if "https://w3id.org/ftr#TestResult" not in node.get("@type", []):
            continue
        tests = node.get("https://w3id.org/ftr#outputFromTest", [])
        values = node.get("http://www.w3.org/ns/prov#value", [])
        if not isinstance(tests, list) or not isinstance(values, list):
            raise ValueError("Invalid FAIR-Checker test result")
        if len(tests) != 1 or len(values) > 1:
            raise ValueError("FAIR-Checker test result has ambiguous test or value")
        test = tests[0].get("@id") if isinstance(tests[0], dict) else None
        if (
            not isinstance(test, str)
            or "/test/" not in test
            or test.rsplit("/test/", 1)[-1] in ("", "None")
        ):
            print(
                f"Warning: {input_path or request['repository']}: skipping "
                f"FAIR-Checker result {node.get('@id', '<no result ID>')}: "
                "no usable test ID",
                file=sys.stderr,
            )
            continue
        if values:
            if not isinstance(values[0], dict) or "@value" not in values[0]:
                raise ValueError("FAIR-Checker test result has an invalid value")
            add("FAIRChecker API", test.rsplit("/test/", 1)[-1], values[0]["@value"])

    # OpenEBench's metrics document is already a source-specific metric record.
    # DOI/year keys preserve the identity of publication and annual observations.
    def openebench(
        value: Any, path: str, context: dict[str, Any] | None = None
    ) -> None:
        if isinstance(value, dict):
            if context is not None:
                context = {
                    **context,
                    **{
                        key: value[key]
                        for key in ("doi", "pmid", "title", "year")
                        if value.get(key) is not None
                    },
                }
            for key, child in value.items():
                if key.startswith("@") or key in {"doi", "pmid", "title", "year"}:
                    continue
                child_path = f"{path}.{key}" if path else key
                child_context = {} if child_path == "project.publications" else context
                openebench(child, child_path, child_context)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                if context is not None:
                    openebench(
                        child,
                        f"{path}[]",
                        {**context, f"{path}.index": index},
                    )
                    continue
                if isinstance(child, dict) and child.get("doi"):
                    label = f"doi={child['doi']}"
                elif isinstance(child, dict) and child.get("year") is not None:
                    label = f"year={child['year']}"
                else:
                    label = str(index)
                openebench(child, f"{path}[{label}]", context)
        elif value is not None:
            if context is None:
                add("OpenEBench", path, value)
            else:
                add_publication("OpenEBench", path, value, context)

    openebench((data.get("openebench") or {}).get("metrics") or {}, "")

    publications = (data.get("biotools") or {}).get("publication") or []
    for index, publication in enumerate(publications):
        count = (publication.get("metadata") or {}).get("citationCount")
        context = (
            {"doi": publication["doi"]}
            if publication.get("doi")
            else (
                {"pmid": publication["pmid"]}
                if publication.get("pmid")
                else {"index": index}
            )
        )
        add_publication(
            "bio.tools", "publication.citationCount", count, context, ">= 0"
        )

    for source, fields in PUBLICATION_FIELDS.items():
        for doi, record in (data.get(source) or {}).items():
            if record is not None:
                for field_name, expected_range in fields.items():
                    add_publication(
                        source,
                        f"publication.{field_name}",
                        record.get(field_name),
                        {"doi": doi},
                        expected_range,
                    )
    for metric, values in publication_values.items():
        result[metric] = json.dumps(values, ensure_ascii=False)
    return result


def element(
    parent: ET.Element, prefix: str, name: str, **attributes: str
) -> ET.Element:
    return ET.SubElement(parent, tag(prefix, name), attributes)


def paragraph(parent: ET.Element, text: str) -> None:
    element(parent, "text", "p").text = text


def table(
    parent: ET.Element,
    name: str,
    rows: list[list[str | int | float | bool | None]],
) -> None:
    node = element(parent, "table", "table", **{tag("table", "name"): name})
    widths = (
        [
            "metric-name",
            "metric-source",
            "metric-identifier",
            "metric-range",
            "metric-description",
            "metric-category",
        ]
        if name == "Metric details"
        else ["tool", *(["metric"] * (len(rows[0]) - 1))]
    )
    for width in widths:
        element(node, "table", "table-column", **{tag("table", "style-name"): width})
    for values in rows:
        row = element(node, "table", "table-row")
        for value in values:
            attributes = {tag("table", "style-name"): "wrapped"}
            if isinstance(value, bool):
                attributes.update(
                    {
                        tag("office", "value-type"): "boolean",
                        tag("office", "boolean-value"): str(value).lower(),
                    }
                )
            elif isinstance(value, (int, float)):
                attributes.update(
                    {
                        tag("office", "value-type"): "float",
                        tag("office", "value"): str(value),
                    }
                )
            elif value is not None:
                attributes[tag("office", "value-type")] = "string"
            cell = element(row, "table", "table-cell", **attributes)
            if value is not None:
                paragraph(
                    cell, str(value).lower() if isinstance(value, bool) else str(value)
                )


def write_report(
    inputs: list[Path], output: Path, as_of: datetime | None = None
) -> None:
    as_of = as_of or datetime.now(UTC)
    datasets: list[tuple[str, dict[Metric, str | int | float | bool]]] = []
    for path in inputs:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a JSON object")
        try:
            metrics = reported_metrics(data, input_path=path, as_of=as_of)
        except (ValueError, TypeError, AttributeError, IndexError) as error:
            raise ValueError(f"{path}: invalid ingestion data: {error}") from error
        datasets.append((f"{data['request']['repository']} ({path})", metrics))
    metrics = sorted({metric for _, values in datasets for metric in values})
    if not metrics:
        raise ValueError("No reported metrics found in the input files")
    metrics = sorted({*metrics, SUPERLINTER_METRIC})
    labels = {metric: f"{metric.source}: {metric_name(metric)}" for metric in metrics}
    counts = Counter(labels.values())
    labels = {
        metric: label if counts[label] == 1 else f"{label} [{metric.identifier}]"
        for metric, label in labels.items()
    }

    root = ET.Element(
        tag("office", "document-content"), {tag("office", "version"): "1.2"}
    )
    column_styles = element(root, "office", "automatic-styles")
    cell_style = element(
        column_styles,
        "style",
        "style",
        **{tag("style", "name"): "wrapped", tag("style", "family"): "table-cell"},
    )
    element(
        cell_style,
        "style",
        "table-cell-properties",
        **{tag("fo", "wrap-option"): "wrap"},
    )
    for name, width in (
        ("metric-name", 9),
        ("metric-source", 5),
        ("metric-identifier", 20),
        ("metric-range", 4),
        ("metric-description", 15),
        ("metric-category", 6),
        ("tool", 7),
        ("metric", 6),
    ):
        style = element(
            column_styles,
            "style",
            "style",
            **{
                tag("style", "name"): name,
                tag("style", "family"): "table-column",
            },
        )
        element(
            style,
            "style",
            "table-column-properties",
            **{
                tag("style", "column-width"): f"{width}cm",
            },
        )
    body = element(element(root, "office", "body"), "office", "spreadsheet")
    table(
        body,
        "Metric details",
        [
            [
                "Metric",
                "Source",
                "Identifier",
                "Expected range",
                "Description",
                "Indicator category",
            ],
            *[
                [
                    labels[m],
                    m.source,
                    m.identifier,
                    m.expected_range,
                    metric_description(m)
                    + (
                        f" Reference: {as_of.isoformat()}."
                        if m.identifier
                        in ("days_since_last_push", "days_since_last_project_activity")
                        else ""
                    ),
                    category_label(m),
                ]
                for m in metrics
            ],
        ],
    )
    table(
        body,
        "Tool comparison",
        [
            ["Tool (input file)", *[labels[m] for m in metrics]],
            *[[name, *[values.get(m) for m in metrics]] for name, values in datasets],
        ],
    )

    styles = ET.Element(
        tag("office", "document-styles"), {tag("office", "version"): "1.2"}
    )
    manifest = ET.Element(
        tag("manifest", "manifest"), {tag("manifest", "version"): "1.2"}
    )
    for path, media in (
        ("/", "application/vnd.oasis.opendocument.spreadsheet"),
        ("content.xml", "text/xml"),
        ("styles.xml", "text/xml"),
    ):
        element(
            manifest,
            "manifest",
            "file-entry",
            **{
                tag("manifest", "full-path"): path,
                tag("manifest", "media-type"): media,
            },
        )
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "mimetype",
            "application/vnd.oasis.opendocument.spreadsheet",
            compress_type=ZIP_STORED,
        )
        for name, tree in (
            ("content.xml", root),
            ("styles.xml", styles),
            ("META-INF/manifest.xml", manifest),
        ):
            archive.writestr(
                name,
                ET.tostring(tree, encoding="utf-8", xml_declaration=True),
                compress_type=ZIP_DEFLATED,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs", nargs="+", type=Path, help="Saved --save-data JSON files"
    )
    parser.add_argument(
        "-o", "--output", required=True, type=Path, help="Output .ods file"
    )
    parser.add_argument(
        "--as-of",
        type=parse_timestamp,
        help="Reference ISO timestamp with timezone for activity (default: now)",
    )
    args = parser.parse_args()
    if args.output.suffix.lower() != ".ods":
        parser.error("output must have an .ods extension")
    if any(args.output.resolve() == path.resolve() for path in args.inputs):
        parser.error("output must not overwrite an input file")
    try:
        write_report(args.inputs, args.output, args.as_of)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
