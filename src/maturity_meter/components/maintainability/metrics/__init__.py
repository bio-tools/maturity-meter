"""Maintainability metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`, scored with the scaling helpers in
:mod:`maturity_meter.components.utils.scaling`. ``releases_and_versioning`` is
shared with FAIRness.
"""

from maturity_meter.components.shared import releases_and_versioning

from .code import avg_ccn, duplicate_rate
from .practices import continuous_integration, linting
from .project import requirements_specified

__all__ = [
    "avg_ccn",
    "continuous_integration",
    "duplicate_rate",
    "linting",
    "releases_and_versioning",
    "requirements_specified",
]
