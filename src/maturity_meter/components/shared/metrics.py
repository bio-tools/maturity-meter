"""Metrics that belong to more than one dimension.

A dimension uses a shared metric by importing it into its own ``metrics``
module; the lineage then lists it under every dimension that does.
"""

from maturity_meter.components.utils.checks import (
    has_any_file,
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.files import DEPENDENCY_UPDATE_FILES
from maturity_meter.models import IngestedData, MetricResult


def dependency_management(data: IngestedData) -> MetricResult:
    """Whether dependencies are kept up to date by a tool.

    Combines resqui's OpenSSF Scorecard check and a Dependabot or Renovate
    configuration file in the repository with :func:`placeholder_reconcile`.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        1 if a dependency update tool is used, 0 if not, or ``value=None``
        without a check or file list.
    """
    return verdict_metric(
        "dependency_management",
        {
            "OpenSSF Scorecard": resqui_verdict(data, "dependency_management"),
            "Dependabot/Renovate config": has_any_file(data, DEPENDENCY_UPDATE_FILES),
        },
        suggestion="Configure a dependency update tool such as Dependabot or Renovate.",
        missing="No dependency check or file list available.",
    )
