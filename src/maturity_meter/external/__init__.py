"""
Infrastructure layer that handles all interactions with external systems and services.
"""

from .biotools import BiotoolsIngestor
from .code_metrics import CodeMetricsError, CodeMetricsIngestor
from .edam import EDAMIngestor, formats_in_biotools
from .europe_pmc import EuropePMCIngestor, EuropePMCNotFoundError
from .github import GitHubIngestor
from .gitlab import GitLabIngestor
from .openalex import OpenAlexIngestor
from .openebench import OpenEBenchIngestor
from .resqui import ResquiError, ResquiIngestor
from .rsec import RSEcIngestor

__all__ = [
    "CodeMetricsError",
    "CodeMetricsIngestor",
    "EDAMIngestor",
    "formats_in_biotools",
    "EuropePMCIngestor",
    "EuropePMCNotFoundError",
    "GitHubIngestor",
    "GitLabIngestor",
    "OpenAlexIngestor",
    "OpenEBenchIngestor",
    "ResquiError",
    "RSEcIngestor",
    "ResquiIngestor",
    "BiotoolsIngestor",
]
