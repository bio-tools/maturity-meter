from maturity_meter.models import DimensionResult, IngestedData


def eval(data: IngestedData) -> DimensionResult:
    return DimensionResult(value=None)
