"""Compatibility metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`. When several sources measure the same thing, they are
combined with :func:`placeholder_reconcile`. ``dependency_management`` is
shared with the security dimension.
"""

from maturity_meter.components.shared.metrics import dependency_management

from .distribution import (
    available_in_galaxy,
    bioconda_package,
    biocontainer_image,
    debian_med_package,
    has_distribution_support,
)
from .formats import input_formats, output_formats

__all__ = [
    "available_in_galaxy",
    "bioconda_package",
    "biocontainer_image",
    "debian_med_package",
    "dependency_management",
    "has_distribution_support",
    "input_formats",
    "output_formats",
]
