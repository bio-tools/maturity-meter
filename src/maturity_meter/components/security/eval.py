from maturity_meter.components.utils.scaling import placeholder_dimension_score
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
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
