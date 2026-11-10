from maturity_meter.models import IngestedData

from .component1 import evaluate_component1


def combine(data: IngestedData) -> float:
    return evaluate_component1(data)
