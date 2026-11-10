from maturity_meter.models import IngestedData

from .component1 import evaluate_component1
from .resqui import evaluate_resqui


def combine(data: IngestedData) -> dict[str, float | None]:
    """Evaluate every component; ``None`` means the component was not assessed."""
    return {
        "component1": evaluate_component1(data),
        "resqui": evaluate_resqui(data),
    }
