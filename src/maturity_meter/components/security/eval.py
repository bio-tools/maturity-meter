from maturity_meter.components.utils.scaling import placeholder_dimension_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    default_branch_protected,
    dependency_management,
    human_code_review_requirement,
    no_leaked_credentials,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        default_branch_protected(data),
        no_leaked_credentials(data),
        dependency_management(data),
        human_code_review_requirement(data),
    ]
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
