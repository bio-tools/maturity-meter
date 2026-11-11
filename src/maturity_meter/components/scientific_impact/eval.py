from maturity_meter.components.utils.scaling import placeholder_dimension_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import citation_count, fork_count, fwci, star_count


def eval(data: IngestedData) -> DimensionResult:
    metrics = [star_count(data), fork_count(data), citation_count(data), fwci(data)]
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
