from maturity_meter.components.utils.importance import IMPORTANCE
from maturity_meter.components.utils.scaling import aggregate_dimension
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    change_control,
    dependency_management,
    repository_hygiene,
    security_testing,
    vulnerability_management,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        change_control(data),
        vulnerability_management(data),
        security_testing(data),
        repository_hygiene(data),
        dependency_management(data),
    ]
    return aggregate_dimension(metrics, IMPORTANCE["security"])
