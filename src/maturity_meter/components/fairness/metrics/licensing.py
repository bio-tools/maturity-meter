"""FAIRness metric on licensing: every licence-related item, in one metric."""

from typing import Any

from maturity_meter.components.utils.checks import (
    Aspect,
    Pool,
    aspect_metric,
    resqui_verdict,
)
from maturity_meter.components.utils.reliability import (
    aggregator,
    assessment_tool,
    registry,
    repository,
)
from maturity_meter.components.utils.sources import (
    biotools_has,
    fair_checker_score,
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

# HowFairIs's software_has_license verdict is not used: it reported "no
# licence" for most repositories that have a LICENSE (or LICENSE.md) file in
# the root, the very files it looks for. RSFC's and OEBFAIR's are.


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


def licensing(data: IngestedData) -> MetricResult:
    """How well the software's licensing is stated: every licence item.

    Aspects and their sources:

    - declared (any place): the repository (its GitHub/GitLab licence, a
      LICENSE/COPYING file and the RSFC and OEBFAIR ``software_has_license``
      checks, weighed as evidence), the bio.tools licence, or OpenEBench (its
      licence and source-licence checks, weighed as evidence);
    - open source (evidence): OpenEBench's OSI and open-source checks, and the
      GitHub/GitLab and bio.tools licences looked up in a list of common
      OSI-approved licences;
    - machine-readable (any): FAIR-Checker's licence-metadata test (R1.1) on
      the repository page, or a licence in the bio.tools entry;
    - per file (evidence): a REUSE setup (``REUSE.toml``, ``.reuse/dep5``, a
      ``LICENSES/`` folder) and HowFairIs's
      ``software_has_license_for_file_types`` check.

    Parameters
    ----------
    data : IngestedData
        Ingested data.

    Returns
    -------
    MetricResult
        The aspects combined, or ``value=None`` if no source could check.
    """
    repo = repo_record(data)
    biotools_license = (data.biotools or {}).get("license")
    return aspect_metric(
        "licensing",
        {
            "declared": Aspect(
                {
                    "repository": Pool(
                        {
                            "GitHub/GitLab licence": repository(
                                None if repo is None else verdict(repo.get("license"))
                            ),
                            "LICENSE file": repository(
                                has_file(
                                    data,
                                    lambda f: file_name(f).startswith(
                                        ("license", "licence", "copying")
                                    ),
                                )
                            ),
                            "RSFC": assessment_tool(
                                resqui_verdict(data, "software_has_license", {"RSFC"})
                            ),
                            "OEBFAIR": assessment_tool(
                                resqui_verdict(
                                    data, "software_has_license", {"OEBFAIR"}
                                )
                            ),
                        }
                    ),
                    "bio.tools": biotools_has(data, "license"),
                    "OpenEBench": Pool(
                        {
                            "licence": aggregator(openebench_tool_has(data, "license")),
                            "source licence": aggregator(
                                verdict(
                                    openebench_metric(
                                        data, "distribution.sourcecode.license"
                                    )
                                )
                            ),
                        }
                    ),
                },
                "Add a LICENSE file with an open-source licence.",
            ),
            "open source": Aspect(
                {
                    "OpenEBench OSI": aggregator(
                        verdict(openebench_metric(data, "project.license.osi"))
                    ),
                    "OpenEBench open source": aggregator(
                        verdict(openebench_metric(data, "project.license.open_source"))
                    ),
                    "repository licence": repository(_osi((repo or {}).get("license"))),
                    "bio.tools licence": registry(_osi(biotools_license)),
                },
                "Use an OSI-approved open-source licence.",
                rule="evidence",
            ),
            "machine-readable": Aspect(
                {
                    "FAIR-Checker R1.1": fair_checker_score(data, "R11"),
                    "bio.tools": biotools_has(data, "license"),
                },
                "State the licence in machine-readable metadata "
                "(e.g. a bio.tools entry or codemeta.json).",
            ),
            "per file": Aspect(
                {
                    "REUSE setup": repository(
                        has_file(
                            data,
                            lambda f: (
                                f in ("reuse.toml", ".reuse/dep5")
                                or f.startswith("licenses/")
                            ),
                        )
                    ),
                    "HowFairIs": assessment_tool(
                        resqui_verdict(data, "software_has_license_for_file_types")
                    ),
                },
                "Add SPDX licence headers to the files (e.g. with REUSE).",
                rule="evidence",
            ),
        },
    )
