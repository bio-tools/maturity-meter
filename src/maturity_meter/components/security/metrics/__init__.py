"""Security metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`. ``dependency_management`` is shared with Compatibility.
"""

from maturity_meter.components.shared import dependency_management

from .practices import (
    change_control,
    repository_hygiene,
    security_testing,
    vulnerability_management,
)

__all__ = [
    "change_control",
    "dependency_management",
    "repository_hygiene",
    "security_testing",
    "vulnerability_management",
]
