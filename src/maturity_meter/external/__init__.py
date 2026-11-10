"""
Infrastructure layer that handles all interactions with external systems and services.
"""

from .biotools import BiotoolsIngestor
from .europe_pmc import EuropePMCIngestor, EuropePMCNotFoundError
from .github import GitHubIngestor
from .gitlab import GitLabIngestor
from .openalex import OpenAlexIngestor
from .openebench import OpenEBenchIngestor
from .resqui import ResquiError, ResquiIngestor

__all__ = [
    "EuropePMCIngestor",
    "EuropePMCNotFoundError",
    "GitHubIngestor",
    "GitLabIngestor",
    "OpenAlexIngestor",
    "OpenEBenchIngestor",
    "ResquiError",
    "ResquiIngestor",
    "BiotoolsIngestor",
]
