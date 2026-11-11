"""Metrics that belong to more than one dimension.

A dimension uses a shared metric by importing it into its own ``metrics``
module; the lineage then lists it under every dimension that does.
"""

from maturity_meter.components.utils.checks import (
    findings_note,
    has_any_file,
    resqui_verdict,
)
from maturity_meter.components.utils.files import DEPENDENCY_UPDATE_FILES
from maturity_meter.components.utils.scaling import placeholder_reconcile
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
    findings = {
        "OpenSSF Scorecard": resqui_verdict(data, "dependency_management"),
        "Dependabot/Renovate config": has_any_file(data, DEPENDENCY_UPDATE_FILES),
    }
    value = placeholder_reconcile(list(findings.values()))
    if value is None:
        return MetricResult(
            name="dependency_management",
            value=None,
            note="No dependency check or file list available.",
        )
    return MetricResult(
        name="dependency_management",
        value=value,
        note=findings_note(findings, "found", "not found"),
        # Only suggest one when no source found a tool.
        suggestions=[]
        if value > 0
        else ["Configure a dependency update tool such as Dependabot or Renovate."],
    )
