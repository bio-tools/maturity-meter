from maturity_meter.components.utils.importance import IMPORTANCE
from maturity_meter.components.utils.scaling import aggregate_dimension
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    avg_ccn,
    continuous_integration,
    duplicate_rate,
    linting,
    releases_and_versioning,
    requirements_specified,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        avg_ccn(data),
        duplicate_rate(data),
        continuous_integration(data),
        linting(data),
        releases_and_versioning(data),
        requirements_specified(data),
    ]
    return aggregate_dimension(metrics, IMPORTANCE["maintainability"])
