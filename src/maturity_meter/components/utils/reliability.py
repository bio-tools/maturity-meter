"""How much each kind of source is trusted, defined in one place.

When several sources answer the same yes/no question, their answers are
combined by accuracy-weighted voting (see :func:`reconcile_evidence`): each
source votes with weight ``ln(A / (1 - A))``, where ``A`` is the accuracy of
its kind of source. This is the vote count of the ACCU data-fusion model
(Dong, Berti-Equille & Srivastava, PVLDB 2009) for two possible values, and
equivalent to a logarithmic opinion pool of the sources.

No published accuracies exist for most of these sources (OpenSSF Scorecard
and SOMEF/RSFC describe their checks as heuristics with false positives and
negatives), so the accuracies are informed judgements of how directly each
kind of source observes the software. They are not fitted to any data set.
"""

import math
from dataclasses import dataclass
from enum import StrEnum


class SourceKind(StrEnum):
    """How a source obtains its answer."""

    REPOSITORY = "repository"
    """Read from the repository itself: its files, or the GitHub/GitLab record."""

    REGISTRY = "registry"
    """Curated metadata: bio.tools, RSEc, Europe PMC, OpenAlex."""

    ASSESSMENT_TOOL = "assessment tool"
    """An automated check run on the repository (resqui plugins)."""

    AGGREGATOR = "aggregator"
    """Derived second-hand from other registries (OpenEBench)."""

    WEB_METADATA = "web metadata"
    """Metadata embedded in the repository's web page (FAIR-Checker)."""

    README_TEXT = "README text"
    """A keyword pattern found in the README."""


ACCURACY: dict[SourceKind, float] = {
    # Observes the artefact directly; errors only from unusual file names or a
    # truncated file list.
    SourceKind.REPOSITORY: 0.95,
    # Curated, but self-reported and possibly not updated after a release.
    SourceKind.REGISTRY: 0.85,
    # Heuristic checks with known false positives and negatives.
    SourceKind.ASSESSMENT_TOOL: 0.80,
    # Automated second-hand derivation, possibly stale.
    SourceKind.AGGREGATOR: 0.75,
    # Describes the hosting page's markup more than the software.
    SourceKind.WEB_METADATA: 0.70,
    # A keyword match cannot tell context (e.g. "cite" in passing).
    SourceKind.README_TEXT: 0.65,
}


def vote_weight(kind: SourceKind) -> float:
    """Weight of a source's vote: the log-odds ``ln(A / (1 - A))`` of its kind."""
    accuracy = ACCURACY[kind]
    return math.log(accuracy / (1.0 - accuracy))


@dataclass(frozen=True)
class Evidence:
    """One source's answer to a yes/no question, and how it was obtained.

    Parameters
    ----------
    value : float | None
        1 (yes), 0 (no), a graded score in between, or None without an answer.
    kind : SourceKind
        How the source obtains its answer, which sets its vote weight.
    """

    value: float | None
    kind: SourceKind


def repository(value: float | None) -> Evidence:
    """Evidence read from the repository's files or GitHub/GitLab record."""
    return Evidence(value, SourceKind.REPOSITORY)


def registry(value: float | None) -> Evidence:
    """Evidence from curated metadata (bio.tools, RSEc, Europe PMC, OpenAlex)."""
    return Evidence(value, SourceKind.REGISTRY)


def assessment_tool(value: float | None) -> Evidence:
    """Evidence from an automated check (a resqui plugin)."""
    return Evidence(value, SourceKind.ASSESSMENT_TOOL)


def aggregator(value: float | None) -> Evidence:
    """Evidence derived second-hand (OpenEBench)."""
    return Evidence(value, SourceKind.AGGREGATOR)


def web_metadata(value: float | None) -> Evidence:
    """Evidence from the repository page's embedded metadata (FAIR-Checker)."""
    return Evidence(value, SourceKind.WEB_METADATA)


def readme_text(value: float | None) -> Evidence:
    """Evidence from a keyword pattern in the README."""
    return Evidence(value, SourceKind.README_TEXT)
