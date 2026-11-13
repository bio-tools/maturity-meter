"""FAIRness metrics on citation and publications."""

from maturity_meter.components.utils.checks import (
    Aspect,
    Pool,
    aspect_metric,
    resqui_verdict,
)
from maturity_meter.components.utils.reliability import (
    Evidence,
    assessment_tool,
    registry,
    repository,
)
from maturity_meter.components.utils.scaling import (
    placeholder_combine,
    reconcile_evidence,
)
from maturity_meter.components.utils.sources import (
    biotools_has,
    file_name,
    has_file,
    openebench_metric,
    openebench_tool_has,
    readme_matches,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult


def citation_and_credit(data: IngestedData) -> MetricResult:
    """Whether users are told how to cite the software, and who made it.

    Aspects and their sources:

    - how to cite (any place): a CITATION file (e.g. ``CITATION.cff``,
      weighed as evidence with RSFC's ``software_has_citation`` check),
      OpenEBench's citation check, or a citation section in the README;
    - credits (any place): an AUTHORS/CONTRIBUTORS/CREDITS file, or the
      credits in the bio.tools or OpenEBench entries.

    OpenEBench's website copyright check is not used: it inspects the
    homepage, which for most tools is the GitHub/GitLab page.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    return aspect_metric(
        "citation_and_credit",
        {
            "how to cite": Aspect(
                {
                    "CITATION file": Pool(
                        {
                            "file": repository(
                                has_file(
                                    data, lambda f: file_name(f).startswith("citation")
                                )
                            ),
                            "RSFC": assessment_tool(
                                resqui_verdict(data, "software_has_citation")
                            ),
                        }
                    ),
                    "OpenEBench": verdict(
                        openebench_metric(data, "project.documentation.citation")
                    ),
                    "README": readme_matches(data, r"\bcit(e|ing|ation)\b"),
                },
                "Add a CITATION.cff file describing how to cite the software.",
            ),
            "credits": Aspect(
                {
                    "AUTHORS file": has_file(
                        data,
                        lambda f: file_name(f).startswith(
                            ("authors", "contributors", "credits")
                        ),
                    ),
                    "bio.tools": biotools_has(data, "credit"),
                    "OpenEBench": openebench_tool_has(data, "credits"),
                },
                "State the authors and funders (e.g. an AUTHORS file).",
            ),
        },
    )


def _open_access(data: IngestedData) -> dict[str, float | None]:
    """Open-access verdict per publication (DOI), Europe PMC and OpenAlex weighed."""
    verdicts: dict[str, list[Evidence]] = {}
    for doi, record in data.europe_pmc.items():
        if record is not None and record.get("isOpenAccess") is not None:
            verdicts.setdefault(doi.lower(), []).append(
                registry(float(record["isOpenAccess"] == "Y"))
            )
    for doi, work in data.openalex.items():
        oa = ((work or {}).get("open_access") or {}).get("is_oa")
        if oa is not None:
            verdicts.setdefault(doi.lower(), []).append(registry(float(oa)))
    return {doi: reconcile_evidence(v) for doi, v in verdicts.items()}


def _publication_dois(data: IngestedData) -> set[str]:
    """DOIs of all known publications: request, bio.tools and OpenEBench."""
    dois = {doi.lower() for doi in data.request.dois}
    for publication in (data.biotools or {}).get("publication") or []:
        if publication.get("doi"):
            dois.add(str(publication["doi"]).lower())
    for publication in openebench_metric(data, "project.publications") or []:
        for entry in publication.get("entries") or []:
            if entry.get("doi"):
                dois.add(str(entry["doi"]).lower())
    return dois


def publications(data: IngestedData) -> MetricResult:
    """Whether publications describe the software, and are open access.

    Publications come from the request's DOIs, bio.tools and OpenEBench; the
    open-access status from Europe PMC and OpenAlex. The score reconciles
    "has publications" with the share of open-access publications.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled score.
    """
    dois = _publication_dois(data)
    if not dois and data.biotools is None and data.openebench is None:
        # Nowhere to look for publications: not assessed rather than none.
        return MetricResult(
            name="publications",
            value=None,
            note="No DOIs given and no bio.tools entry to list publications.",
            suggestions=["Add the DOIs of publications describing the software."],
        )
    if not dois:
        return MetricResult(
            name="publications",
            value=0.0,
            note="No publications found.",
            suggestions=[
                "Publish a paper about the software and list it in bio.tools."
            ],
        )
    access = _open_access(data)
    known = [v for v in access.values() if v is not None]
    share = sum(known) / len(known) if known else None
    value = placeholder_combine([1.0, share])
    note = f"{len(dois)} publication(s)"
    note += (
        f"; {sum(known):g} of {len(known)} with known status are open access."
        if known
        else "; open-access status unknown (add their DOIs to look it up)."
    )
    return MetricResult(
        name="publications",
        value=value,
        note=note,
        suggestions=[]
        if share in (None, 1.0)
        else ["Make the publications open access."],
    )
