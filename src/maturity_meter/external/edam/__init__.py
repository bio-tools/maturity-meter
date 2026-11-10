"""
EDAM ontology integrations: async term lookup via EMBL-EBI OLS4.
"""

from .edam_ingestor import EDAMIngestor, formats_in_biotools

__all__ = [
    "EDAMIngestor",
    "formats_in_biotools",
]
