"""
Ingestors: one module per external source, each fetching raw metadata.
"""

from .biotools import BiotoolsIngestor
from .code_metrics import CodeMetricsError, CodeMetricsIngestor
from .edam import EDAMIngestor, formats_in_biotools
from .europe_pmc import EuropePMCIngestor, EuropePMCNotFoundError
from .fairchecker import FairCheckerError, FairCheckerIngestor
from .github import GitHubIngestor
from .gitlab import GitLabIngestor
from .openalex import OpenAlexIngestor
from .openebench import OpenEBenchIngestor
from .resqui import ResquiError, ResquiIngestor
from .rsec import RSEcIngestor

__all__ = [
    "BiotoolsIngestor",
    "CodeMetricsError",
    "CodeMetricsIngestor",
    "EDAMIngestor",
    "EuropePMCIngestor",
    "EuropePMCNotFoundError",
    "FairCheckerError",
    "FairCheckerIngestor",
    "GitHubIngestor",
    "GitLabIngestor",
    "OpenAlexIngestor",
    "OpenEBenchIngestor",
    "RSEcIngestor",
    "ResquiError",
    "ResquiIngestor",
    "formats_in_biotools",
]
