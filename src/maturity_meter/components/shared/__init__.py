"""Metrics that belong to more than one dimension.

A dimension uses a shared metric by importing it into its own ``metrics``
module; the lineage then lists it under every dimension that does.
"""

from .metrics import dependency_management

__all__ = ["dependency_management"]
