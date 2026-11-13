"""Compatibility metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`. ``containerization`` is shared with FAIRness and
``dependency_management`` with Security.
"""

from maturity_meter.components.shared import (
    containerization,
    dependency_management,
)

from .distribution import package_availability, workflow_integration
from .formats import input_formats, output_formats

__all__ = [
    "containerization",
    "dependency_management",
    "input_formats",
    "output_formats",
    "package_availability",
    "workflow_integration",
]
