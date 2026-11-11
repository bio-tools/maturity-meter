from maturity_meter.components.utils.scaling import placeholder_dimension_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    avg_issue_close_time_days,
    days_since_last_commit,
    has_contribution_guidelines,
    inverse_simpson_index,
    num_open_issues,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        avg_issue_close_time_days(data),
        num_open_issues(data),
        days_since_last_commit(data),
        inverse_simpson_index(data),
        has_contribution_guidelines(data),
    ]
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
