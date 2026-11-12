from maturity_meter.components.utils.scaling import placeholder_dimension_score
from maturity_meter.models import DimensionResult, IngestedData

from .metrics import (
    available_in_galaxy,
    bioconda_package,
    biocontainer_image,
    debian_med_package,
    dependency_management,
    has_distribution_support,
    input_formats,
    output_formats,
)


def eval(data: IngestedData) -> DimensionResult:
    metrics = [
        input_formats(data),
        output_formats(data),
        has_distribution_support(data),
        dependency_management(data),
        bioconda_package(data),
        debian_med_package(data),
        biocontainer_image(data),
        available_in_galaxy(data),
    ]
    return DimensionResult(value=placeholder_dimension_score(metrics), metrics=metrics)
