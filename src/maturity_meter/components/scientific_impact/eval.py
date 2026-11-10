from maturity_meter.components.scaling import mean_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import citation_count, fork_count, fwci, star_count


def eval(data: IngestedData) -> DimensionResult:
    metrics = [star_count(data), fork_count(data), citation_count(data), fwci(data)]
    return DimensionResult(value=mean_score(metrics), metrics=metrics)
