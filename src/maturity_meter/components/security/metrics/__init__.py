"""Security metrics.

Each function computes one metric from the ingested data and returns its
:class:`MetricResult`. Verdicts are 1 (pass) or 0 (fail); when several sources
check the same thing, they are combined with :func:`placeholder_reconcile`.
``dependency_management`` is shared with the compatibility dimension.
"""

from maturity_meter.components.shared.metrics import dependency_management

from .repository import default_branch_protected
from .resqui_checks import human_code_review_requirement, no_leaked_credentials

__all__ = [
    "default_branch_protected",
    "dependency_management",
    "human_code_review_requirement",
    "no_leaked_credentials",
]
