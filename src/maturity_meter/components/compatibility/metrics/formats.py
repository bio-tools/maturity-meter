"""Compatibility metrics on data formats (bio.tools + EDAM)."""

from maturity_meter.models import IngestedData, MetricResult

_NO_BIOTOOLS = "No bio.tools entry (a bio.tools ID is needed)."


def _formats(data: IngestedData, direction: str) -> list[str]:
    """Unique EDAM format IRIs of the bio.tools entry's inputs or outputs."""
    iris: dict[str, None] = {}
    for function in (data.biotools or {}).get("function") or []:
        for io in function.get(direction) or []:
            for fmt in io.get("format") or []:
                if fmt.get("uri"):
                    iris[fmt["uri"]] = None
    return list(iris)


def _format_share(data: IngestedData, direction: str) -> MetricResult:
    """Share of the inputs' or outputs' formats that are specific EDAM terms."""
    name = f"{direction}_formats"
    if data.biotools is None:
        return MetricResult(name=name, value=None, note=_NO_BIOTOOLS)
    iris = _formats(data, direction)
    if not iris:
        return MetricResult(
            name=name,
            value=None,
            note=f"bio.tools lists no {direction} formats.",
            suggestions=[f"Annotate the {direction} formats in bio.tools with EDAM."],
        )
    terms = {iri: data.edam.get(iri) for iri in iris}
    known = {iri: term for iri, term in terms.items() if term is not None}
    if not known:
        return MetricResult(
            name=name, value=None, note="The formats could not be looked up in EDAM."
        )
    # A leaf term is a specific format (e.g. BAM); a term with children is a
    # broad class (e.g. "Sequence format"). Obsolete terms are not specific.
    specific = [
        iri
        for iri, term in known.items()
        if term.get("has_children") is False and not term.get("is_obsolete")
    ]
    value = len(specific) / len(known)
    broad = [str(known[iri].get("label")) for iri in known if iri not in specific]
    return MetricResult(
        name=name,
        value=value,
        note=(
            f"{len(specific)} of {len(known)} {direction} formats are specific "
            "EDAM terms"
            + (f"; broad or obsolete: {', '.join(broad)}" if broad else "")
            + "."
        ),
        suggestions=[]
        if value == 1
        else [f"Use specific EDAM formats for the {direction}s instead of broad ones."],
    )


def input_formats(data: IngestedData) -> MetricResult:
    """Share of the input formats that are specific EDAM terms (leaf nodes).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the bio.tools functions' inputs and their EDAM
        terms.

    Returns
    -------
    MetricResult
        The share in [0, 1], or ``value=None`` without a bio.tools entry,
        formats or EDAM terms.
    """
    return _format_share(data, "input")


def output_formats(data: IngestedData) -> MetricResult:
    """Share of the output formats that are specific EDAM terms (leaf nodes).

    Parameters
    ----------
    data : IngestedData
        Ingested data; uses the bio.tools functions' outputs and their EDAM
        terms.

    Returns
    -------
    MetricResult
        The share in [0, 1], or ``value=None`` without a bio.tools entry,
        formats or EDAM terms.
    """
    return _format_share(data, "output")
