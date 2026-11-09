"""
Infrastructure layer that handles all interactions with external systems and services.
"""

from .biotools import BiotoolsIngestor
from .github import GitHubIngestor

__all__ = [
    "GitHubIngestor",
    "BiotoolsIngestor",
]
