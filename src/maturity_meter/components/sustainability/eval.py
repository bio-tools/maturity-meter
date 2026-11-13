from maturity_meter.components.utils.importance import IMPORTANCE
from maturity_meter.components.utils.scaling import aggregate_dimension
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    contribution_and_governance,
    development_activity,
    inverse_simpson_index,
    issue_close_time,
    resolved_issue_share,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        development_activity(data),
        issue_close_time(data),
        resolved_issue_share(data),
        inverse_simpson_index(data),
        contribution_and_governance(data),
    ]
    return aggregate_dimension(metrics, IMPORTANCE["sustainability"])
