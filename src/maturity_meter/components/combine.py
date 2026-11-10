from maturity_meter.models import Evaluation, IngestedData

from .compatibility import eval_compatibility
from .fairness import eval_fairness
from .maintainability import eval_maintainability
from .scientific_impact import eval_scientific_impact
from .security import eval_security
from .sustainability import eval_sustainability


def combine(data: IngestedData) -> Evaluation:
    """Evaluate every dimension; ``None`` means it was not assessed."""
    return Evaluation(
        compatibility=eval_compatibility(data),
        fairness=eval_fairness(data),
        maintainability=eval_maintainability(data),
        scientific_impact=eval_scientific_impact(data),
        security=eval_security(data),
        sustainability=eval_sustainability(data),
    )
