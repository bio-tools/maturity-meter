from maturity_meter.components.utils.scaling import placeholder_dimension_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    avg_issue_close_time_days,
    contribution_and_governance,
    development_activity,
    inverse_simpson_index,
    num_open_issues,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        development_activity(data),
        avg_issue_close_time_days(data),
        num_open_issues(data),
        inverse_simpson_index(data),
        contribution_and_governance(data),
    ]
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
