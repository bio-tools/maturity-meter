"""
Infrastructure layer that handles all interactions with external systems and services.
"""

from .ingestors import (
    BiotoolsIngestor,
    CodeMetricsError,
    CodeMetricsIngestor,
    EDAMIngestor,
    EuropePMCIngestor,
    EuropePMCNotFoundError,
    FairCheckerError,
    FairCheckerIngestor,
    GitHubIngestor,
    GitLabIngestor,
    OpenAlexIngestor,
    OpenEBenchIngestor,
    ResquiError,
    ResquiIngestor,
    RSEcIngestor,
    formats_in_biotools,
)
from .repository import CloneError, SharedClone, shared_clone

__all__ = [
    "CloneError",
    "SharedClone",
    "shared_clone",
    "CodeMetricsError",
    "CodeMetricsIngestor",
    "EDAMIngestor",
    "formats_in_biotools",
    "EuropePMCIngestor",
    "EuropePMCNotFoundError",
    "FairCheckerError",
    "FairCheckerIngestor",
    "GitHubIngestor",
    "GitLabIngestor",
    "OpenAlexIngestor",
    "OpenEBenchIngestor",
    "ResquiError",
    "RSEcIngestor",
    "ResquiIngestor",
    "BiotoolsIngestor",
]
