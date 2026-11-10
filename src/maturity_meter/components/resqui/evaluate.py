"""Score software quality from the resqui assessment."""

from maturity_meter.models import IngestedData

# resqui does not serialize a pass/fail flag. A check's ``status`` only says it
# ran, so the verdict is read from the plugin-specific ``output`` string.
PASSING_OUTPUTS = {"valid", "secure", "true"}
FAILING_OUTPUTS = {"invalid", "insecure", "false"}


def evaluate_resqui(data: IngestedData) -> float | None:
    """Return the fraction of resqui checks that passed.

    Parameters
    ----------
    data : IngestedData
        Ingested metadata; ``quality_checks`` holds the resqui assessment.

    Returns
    -------
    float | None
        Share of assessed checks that passed, or ``None`` when resqui did not
        run or no check gave a verdict ("not assessed"). Checks with an
        unrecognised output are ignored, not counted as failures.
    """
    if data.quality_checks is None:
        return None
    outputs = [
        str(check.get("output", "")).lower()
        for check in data.quality_checks.get("checks", [])
    ]
    verdicts = [
        o in PASSING_OUTPUTS for o in outputs if o in PASSING_OUTPUTS | FAILING_OUTPUTS
    ]
    return sum(verdicts) / len(verdicts) if verdicts else None
