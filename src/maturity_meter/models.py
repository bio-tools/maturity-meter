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
    """

    model_config = ConfigDict(frozen=True)

    repository: str
    dois: list[str] = Field(default_factory=list)
    biotools_id: str | None = None

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
        normalized: dict[str, None] = {}
        for value in values:
            doi = _DOI_PREFIX_PATTERN.sub("", value.strip())
            if not _DOI_PATTERN.match(doi):
                raise ValueError(f"Invalid DOI: {value!r}")
            normalized[doi] = None
        return list(normalized)

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
        Raw GitHub or GitLab ingestor output.
    biotools : dict[str, Any] | None
        Raw bio.tools entry, if a bio.tools ID was given and found.
    europe_pmc : dict[str, dict[str, Any] | None]
        Europe PMC record per DOI.
    openalex : dict[str, dict[str, Any] | None]
        OpenAlex work per DOI.
    """

    request: EvaluationRequest
    repository: dict[str, Any]
    biotools: dict[str, Any] | None = None
    europe_pmc: dict[str, dict[str, Any] | None] = field(default_factory=dict)
    openalex: dict[str, dict[str, Any] | None] = field(default_factory=dict)
