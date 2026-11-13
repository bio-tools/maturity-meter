from maturity_meter.components.utils.scaling import placeholder_dimension_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    containerization,
    dependency_management,
    input_formats,
    output_formats,
    package_availability,
    workflow_integration,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        input_formats(data),
        output_formats(data),
        package_availability(data),
        containerization(data),
        workflow_integration(data),
        dependency_management(data),
    ]
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
