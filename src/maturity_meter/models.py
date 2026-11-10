"""Input models shared by every Maturity meter interface.

The library, CLI, and web API all describe what to evaluate with
:class:`EvaluationRequest`, so validation rules live in one place.
:class:`IngestedData` is the raw external metadata collected for a request and
handed to the maturity components.
"""

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Hosts that are not a public forge: the server fetches whatever host it is
# given, so refuse names and addresses that point at internal networks.
_INTERNAL_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home.arpa")

_HOSTNAME_PATTERN = re.compile(
    r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$"
)
_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")
_DOI_PREFIX_PATTERN = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.IGNORECASE
)
_BIOTOOLS_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]+$")


def normalize_doi(value: str) -> str:
    """Strip URL or ``doi:`` prefixes from a DOI and validate it.

    Parameters
    ----------
    value : str
        DOI in any common form (bare, ``doi:...``, or a doi.org URL).

    Returns
    -------
    str
        The bare ``10.xxxx/...`` DOI.

    Raises
    ------
    ValueError
        If ``value`` is not a valid DOI.
    """
    doi = _DOI_PREFIX_PATTERN.sub("", value.strip())
    if not _DOI_PATTERN.match(doi):
        raise ValueError(f"Invalid DOI: {value!r}")
    return doi


class SuppliedData(BaseModel):
    """Already-fetched data for any subset of sources.

    Values use the raw shapes the ingestors return. Whatever is supplied is
    used as-is; whatever is missing is fetched. For the per-DOI sources this
    holds per DOI: DOIs in ``dois`` without a supplied record are fetched, and
    supplied DOIs that are not in ``dois`` are kept. ``edam`` works the same
    per format IRI.

    Parameters
    ----------
    repository, biotools, openebench, quality_checks, rsec, code_metrics : dict | None
        Raw record for that source, or ``None`` to fetch it.
    europe_pmc, openalex : dict[str, dict | None]
        Records keyed by DOI (bare, ``doi:...`` or doi.org URL).
    edam : dict[str, dict | None]
        EDAM terms keyed by format IRI.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: dict[str, Any] | None = None
    biotools: dict[str, Any] | None = None
    openebench: dict[str, Any] | None = None
    quality_checks: dict[str, Any] | None = None
    rsec: dict[str, Any] | None = None
    code_metrics: dict[str, Any] | None = None
    europe_pmc: dict[str, dict[str, Any] | None] = Field(default_factory=dict)
    openalex: dict[str, dict[str, Any] | None] = Field(default_factory=dict)
    edam: dict[str, dict[str, Any] | None] = Field(default_factory=dict)

    @field_validator("europe_pmc", "openalex")
    @classmethod
    def normalize_doi_keys(
        cls, value: dict[str, dict[str, Any] | None]
    ) -> dict[str, dict[str, Any] | None]:
        """Normalize DOI keys so they match ``EvaluationRequest.dois``.

        Parameters
        ----------
        value : dict[str, dict | None]
            Records keyed by DOI in any common form.

        Returns
        -------
        dict[str, dict | None]
            Records keyed by bare DOI.
        """
        return {normalize_doi(doi): record for doi, record in value.items()}


class EvaluationRequest(BaseModel):
    """What to evaluate.

    Parameters
    ----------
    repository : str
        URL of a GitHub repository or of a repository on any GitLab instance
        (``github.com`` is GitHub; every other host is treated as GitLab).
        Normalized to
        ``https://<host>/<path>`` without a ``.git`` suffix or trailing slash.
    dois : list[str]
        Optional DOIs of publications about the software. Normalized to the
        bare ``10.xxxx/...`` form.
    biotools_id : str | None
        Optional bio.tools identifier of the software.
    data : SuppliedData
        Optional already-fetched data for any subset of sources; see
        :class:`SuppliedData`. Everything not supplied is fetched.
    """

    model_config = ConfigDict(frozen=True)

    repository: str
    dois: list[str] = Field(default_factory=list)
    biotools_id: str | None = None
    data: SuppliedData = Field(default_factory=SuppliedData)

    @field_validator("repository")
    @classmethod
    def normalize_repository(cls, value: str) -> str:
        """Validate and canonicalize a repository URL.

        Parameters
        ----------
        value : str
            Repository URL as supplied by the user.

        Returns
        -------
        str
            Canonical ``https`` repository URL.

        Raises
        ------
        ValueError
            If the host is not a public hostname or the path is not
            ``owner/repo``.
        """
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if parsed.scheme not in ("http", "https") or not host:
            raise ValueError("Repository must be an http(s) URL")
        if parsed.username or parsed.password or parsed.port:
            raise ValueError("Repository URL must not contain credentials or a port")
        try:
            ipaddress.ip_address(host)
            is_ip = True
        except ValueError:
            is_ip = False
        if (
            is_ip
            or "." not in host
            or host.endswith(_INTERNAL_SUFFIXES)
            or not _HOSTNAME_PATTERN.match(host)
        ):
            raise ValueError("Repository host must be a public hostname")
        path = parsed.path.strip("/").removesuffix(".git")
        if len(path.split("/")) < 2 or not all(path.split("/")):
            raise ValueError("Repository URL must include an owner and a repository")
        return f"https://{host}/{path}"

    @field_validator("dois")
    @classmethod
    def normalize_dois(cls, values: list[str]) -> list[str]:
        """Strip DOI URL prefixes, validate, and drop duplicates.

        Parameters
        ----------
        values : list[str]
            DOIs as supplied by the user.

        Returns
        -------
        list[str]
            Unique bare DOIs in their original order.

        Raises
        ------
        ValueError
            If an entry is not a valid DOI.
        """
        return list(dict.fromkeys(normalize_doi(value) for value in values))

    @field_validator("biotools_id")
    @classmethod
    def normalize_biotools_id(cls, value: str | None) -> str | None:
        """Validate a bio.tools identifier, treating blank as unset.

        Parameters
        ----------
        value : str | None
            bio.tools identifier as supplied by the user.

        Returns
        -------
        str | None
            Stripped identifier, or ``None`` when blank.

        Raises
        ------
        ValueError
            If the identifier contains unsupported characters.
        """
        if value is None or not value.strip():
            return None
        value = value.strip()
        if not _BIOTOOLS_ID_PATTERN.match(value):
            raise ValueError(f"Invalid bio.tools ID: {value!r}")
        return value

    @property
    def host(self) -> str:
        """Hosting platform domain, e.g. ``github.com``."""
        return urlparse(self.repository).hostname or ""

    @property
    def repo_path(self) -> str:
        """Repository path on the host, e.g. ``owner/repo``."""
        return urlparse(self.repository).path.strip("/")

    @property
    def owner(self) -> str:
        """Repository owner (namespace; may contain subgroups on GitLab)."""
        return self.repo_path.rsplit("/", 1)[0]

    @property
    def repo(self) -> str:
        """Repository name."""
        return self.repo_path.rsplit("/", 1)[1]


@dataclass(frozen=True)
class IngestedData:
    """Raw external metadata collected for one :class:`EvaluationRequest`.

    Optional sources are ``None`` (or map a DOI to ``None``) when they were not
    requested or could not be fetched, so components can tell "not assessed"
    apart from a poor score.

    Parameters
    ----------
    request : EvaluationRequest
        The request the data was collected for.
    repository : dict[str, Any]
        Raw GitHub or GitLab ingestor output (repository record, files,
        contributors, closed issues, ...).
    biotools : dict[str, Any] | None
        Raw bio.tools entry, if a bio.tools ID was given and found.
    openebench : dict[str, Any] | None
        OpenEBench ``tool`` record and ``metrics`` for the bio.tools ID, or None
        when no ID was given or OpenEBench does not know the tool.
    quality_checks : dict[str, Any] | None
        resqui quality assessment, or None when it was not run (non-GitHub
        repository) or failed.
    rsec : dict[str, Any] | None
        RSEc metadata file names for the bio.tools ID (Bioconda, Debian Med,
        BioContainers, Galaxy, ...), or None without an ID or RSEc entry.
    code_metrics : dict[str, Any] | None
        Lizard complexity and duplication metrics, or None if unavailable.
    europe_pmc : dict[str, dict[str, Any] | None]
        Europe PMC record per DOI.
    openalex : dict[str, dict[str, Any] | None]
        OpenAlex work per DOI.
    edam : dict[str, dict[str, Any] | None]
        EDAM term (label, ``has_children``, ``is_obsolete``) per format IRI
        used in the bio.tools entry.
    """

    request: EvaluationRequest
    repository: dict[str, Any]
    biotools: dict[str, Any] | None = None
    openebench: dict[str, Any] | None = None
    quality_checks: dict[str, Any] | None = None
    rsec: dict[str, Any] | None = None
    code_metrics: dict[str, Any] | None = None
    europe_pmc: dict[str, dict[str, Any] | None] = field(default_factory=dict)
    openalex: dict[str, dict[str, Any] | None] = field(default_factory=dict)
    edam: dict[str, dict[str, Any] | None] = field(default_factory=dict)


class MetricResult(BaseModel):
    """Result of one metric within a maturity dimension.

    Parameters
    ----------
    name : str
        Name of the metric, e.g. ``"star_count"``.
    value : float | None
        Score of the metric, or ``None`` when it was not assessed. Required,
        so "not assessed" is always stated explicitly.
    suggestions : list[str]
        Actionable ways to improve the score.
    note : str | None
        Optional remark, e.g. on missing data or caveats.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    value: float | None
    suggestions: list[str] = Field(default_factory=list)
    note: str | None = None


class DimensionResult(BaseModel):
    """Result of one maturity dimension: its score and its metrics.

    Parameters
    ----------
    value : float | None
        Score of the dimension, derived from its metrics, or ``None`` when it
        was not assessed. Required, so "not assessed" is always explicit.
    metrics : DimensionResult
        Results of the dimension's individual metrics; empty when none were
        computed.
    """

    model_config = ConfigDict(extra="forbid")

    value: float | None
    metrics: list[MetricResult] = Field(default_factory=list)


class Evaluation(BaseModel):
    """Results per maturity dimension for one evaluation.

    Compatibility, FAIRness, maintainability, security and sustainability
    follow the EVERSE quality dimensions
    (https://w3id.org/everse/i/dimensions); scientific impact is our own.
    """

    model_config = ConfigDict(extra="forbid")

    compatibility: DimensionResult
    fairness: DimensionResult
    maintainability: DimensionResult
    scientific_impact: DimensionResult
    security: DimensionResult
    sustainability: DimensionResult
