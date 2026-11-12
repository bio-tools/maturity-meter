from maturity_meter.components.utils.scaling import placeholder_dimension_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    avg_ccn,
    duplicate_rate,
    has_ci_tests,
    has_no_linting_issues,
    has_releases,
    requirements_specified,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        avg_ccn(data),
        duplicate_rate(data),
        has_ci_tests(data),
        has_releases(data),
        requirements_specified(data),
        has_no_linting_issues(data),
    ]
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
