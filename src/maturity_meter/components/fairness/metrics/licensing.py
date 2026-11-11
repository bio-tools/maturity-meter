"""FAIRness metrics on licensing, copyright and attribution."""

from typing import Any

from maturity_meter.components.utils.checks import (
    resqui_verdict,
    verdict_metric,
)
from maturity_meter.components.utils.sources import (
    biotools_has,
    file_name,
    has_file,
    openebench_metric,
    openebench_tool_has,
    repo_record,
    verdict,
)
from maturity_meter.models import IngestedData, MetricResult

# Common OSI-approved licences (SPDX identifiers, without -only/-or-later).
OSI_LICENSES = {
    "0bsd", "afl-3.0", "agpl-3.0", "apache-2.0", "artistic-2.0", "bsd-2-clause",
    "bsd-3-clause", "bsl-1.0", "cddl-1.0", "cecill-2.1", "ecl-2.0", "epl-1.0",
    "epl-2.0", "eupl-1.1", "eupl-1.2", "gpl-2.0", "gpl-3.0", "isc", "lgpl-2.1",
    "lgpl-3.0", "lppl-1.3c", "mit", "mit-0", "mpl-1.1", "mpl-2.0", "ms-pl", "ms-rl",
    "ncsa", "osl-3.0", "postgresql", "unlicense", "upl-1.0", "zlib",
}  # fmt: skip


def _spdx(value: Any) -> str | None:
    """Normalized SPDX id of a licence (string or GitHub/GitLab object)."""
    if isinstance(value, dict):
        value = value.get("spdx_id") or value.get("key")
    if not value or str(value).upper() in ("NOASSERTION", "OTHER"):
        return None
    text = str(value).lower()
    for suffix in ("-only", "-or-later", "+"):
        text = text.removesuffix(suffix)
    return text


def _osi(value: Any) -> float | None:
    """Whether a licence is OSI-approved; None if unknown."""
    spdx = _spdx(value)
    return None if spdx is None else float(spdx in OSI_LICENSES)


def license_declaration(data: IngestedData) -> MetricResult:
    """Whether the software declares a licence.

    Sources: the GitHub/GitLab licence, a LICENSE/COPYING file, the bio.tools
    and OpenEBench licences, and resqui's ``software_has_license`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    repo = repo_record(data)
    return verdict_metric(
        "license_declaration",
        {
            "repository licence": None
            if repo is None
            else verdict(repo.get("license")),
            "LICENSE file": has_file(
                data,
                lambda f: file_name(f).startswith(("license", "licence", "copying")),
            ),
            "bio.tools": biotools_has(data, "license"),
            "OpenEBench": openebench_tool_has(data, "license"),
            "resqui check": resqui_verdict(data, "software_has_license"),
        },
        suggestion="Add a LICENSE file with an open-source licence.",
    )


def per_file_licensing(data: IngestedData) -> MetricResult:
    """Whether individual files carry licence information (e.g. REUSE).

    Sources: a REUSE setup in the repository (``REUSE.toml``, ``.reuse/dep5``
    or a ``LICENSES/`` folder) and resqui's
    ``software_has_license_for_file_types`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "per_file_licensing",
        {
            "REUSE setup": has_file(
                data,
                lambda f: (
                    f in ("reuse.toml", ".reuse/dep5") or f.startswith("licenses/")
                ),
            ),
            "resqui check": resqui_verdict(data, "software_has_license_for_file_types"),
        },
        suggestion="Add SPDX licence headers to the files (e.g. with REUSE).",
    )


def open_source_license(data: IngestedData) -> MetricResult:
    """Whether the licence is an OSI-approved open-source licence.

    Sources: OpenEBench's OSI check, and the GitHub/GitLab and bio.tools
    licences looked up in a list of common OSI-approved licences.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no licence is known.
    """
    repo = repo_record(data) or {}
    return verdict_metric(
        "open_source_license",
        {
            "OpenEBench": verdict(openebench_metric(data, "project.license.osi")),
            "repository licence": _osi(repo.get("license")),
            "bio.tools licence": _osi((data.biotools or {}).get("license")),
        },
        yes="OSI-approved",
        no="not OSI-approved",
        suggestion="Use an OSI-approved open-source licence.",
        missing="No licence known.",
    )


def copyright_and_attribution(data: IngestedData) -> MetricResult:
    """Whether copyright and credits (who made it) are stated.

    Sources: OpenEBench's website copyright check, credits in bio.tools and
    OpenEBench, and an AUTHORS/CONTRIBUTORS/CITATION file.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The reconciled verdict, or ``value=None`` if no source could check.
    """
    return verdict_metric(
        "copyright_and_attribution",
        {
            "website copyright (OpenEBench)": verdict(
                openebench_metric(data, "project.website.copyright")
            ),
            "credits (bio.tools)": biotools_has(data, "credit"),
            "credits (OpenEBench)": openebench_tool_has(data, "credits"),
            "AUTHORS/CITATION file": has_file(
                data,
                lambda f: (
                    file_name(f).startswith(("authors", "contributors", "credits"))
                    or file_name(f) == "citation.cff"
                ),
            ),
        },
        suggestion="State the authors, funders and copyright (e.g. an AUTHORS file).",
    )
