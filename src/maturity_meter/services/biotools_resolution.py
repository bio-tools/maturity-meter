"""Resolve an evaluation request from a bio.tools entry."""

import logging
import re
from typing import Any

import httpx
from pydantic import ValidationError

from maturity_meter.external import (
    BiotoolsIngestor,
    EuropePMCIngestor,
    EuropePMCNotFoundError,
)
from maturity_meter.models import EvaluationRequest, SuppliedData, normalize_doi
from maturity_meter.services.repository_urls import repository_url

logger = logging.getLogger(__name__)


class BiotoolsResolutionError(ValueError):
    """A bio.tools entry could not be resolved into an evaluation request."""


def _repository_candidate(url: str) -> str | None:
    try:
        return repository_url(url)
    except ValueError:
        return None


async def resolve_biotools(
    identifier: str,
    *,
    dois: list[str] | None = None,
    data: SuppliedData | None = None,
) -> EvaluationRequest:
    """Resolve the first supported repository and publication DOIs from bio.tools."""
    try:
        identifier = EvaluationRequest.normalize_biotools_id(identifier) or ""
    except ValueError as error:
        raise BiotoolsResolutionError(str(error)) from error
    if not identifier:
        raise BiotoolsResolutionError("A bio.tools ID is required")
    supplied = data or SuppliedData()
    try:
        entry = (
            supplied.biotools
            if supplied.biotools is not None
            else await BiotoolsIngestor(identifier).fetch()
        )
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as error:
        raise BiotoolsResolutionError(
            f"Could not fetch bio.tools entry {identifier!r}: {error}"
        ) from error
    if not isinstance(entry, dict):
        raise BiotoolsResolutionError(f"Invalid bio.tools entry for {identifier!r}")

    candidates: list[Any] = [entry.get("homepage")]
    for field in ("link", "download"):
        links = entry.get(field) or []
        if not isinstance(links, list):
            raise BiotoolsResolutionError(
                f"Invalid {field} in bio.tools entry {identifier!r}"
            )
        candidates.extend(link.get("url") for link in links if isinstance(link, dict))
    repository = next(
        (
            candidate
            for value in candidates
            if isinstance(value, str)
            for candidate in [_repository_candidate(value)]
            if candidate is not None
        ),
        None,
    )
    if repository is None:
        raise BiotoolsResolutionError(
            f"No supported GitHub or GitLab repository root in bio.tools entry "
            f"{identifier!r}; provide a repository explicitly."
        )

    publications = entry.get("publication") or []
    if not isinstance(publications, list):
        raise BiotoolsResolutionError(
            f"Invalid publications in bio.tools entry {identifier!r}"
        )
    publication_dois = []
    pmc_records = dict(supplied.europe_pmc)
    for publication in publications:
        if not isinstance(publication, dict):
            raise BiotoolsResolutionError(
                f"Invalid publication in bio.tools entry {identifier!r}"
            )
        doi = publication.get("doi")
        if doi:
            if not isinstance(doi, str):
                raise BiotoolsResolutionError(
                    f"Invalid DOI in bio.tools entry {identifier!r}"
                )
            try:
                publication_dois.append(normalize_doi(doi))
            except ValueError as error:
                raise BiotoolsResolutionError(
                    f"Invalid publication DOI in bio.tools entry "
                    f"{identifier!r}: {doi!r}"
                ) from error
        elif publication.get("pmid") or publication.get("pmcid"):
            pmid, pmcid = publication.get("pmid"), publication.get("pmcid")
            if (
                pmid and (not isinstance(pmid, str) or not re.fullmatch(r"\d+", pmid))
            ) or (
                pmcid
                and (not isinstance(pmcid, str) or not re.fullmatch(r"PMC\d+", pmcid))
            ):
                raise BiotoolsResolutionError(
                    f"Invalid publication identifier in bio.tools entry {identifier!r}"
                )
            try:
                record = await EuropePMCIngestor(pmid=pmid, pmcid=pmcid).fetch()
            except (httpx.HTTPError, EuropePMCNotFoundError) as error:
                logger.warning(
                    "Could not resolve publication %s / %s in bio.tools entry %s: %s",
                    pmid,
                    pmcid,
                    identifier,
                    error,
                )
                continue
            found_doi = record.get("doi")
            if not isinstance(found_doi, str) or not found_doi:
                logger.warning(
                    "Publication %s / %s in bio.tools entry %s "
                    "has no DOI in Europe PMC",
                    pmid,
                    pmcid,
                    identifier,
                )
                continue
            try:
                found_doi = normalize_doi(found_doi)
            except ValueError as error:
                logger.warning("Invalid DOI returned by Europe PMC: %s", error)
                continue
            publication_dois.append(found_doi)
            pmc_records.setdefault(found_doi, record)
    try:
        return EvaluationRequest(
            repository=repository,
            dois=[*(dois or []), *publication_dois],
            biotools_id=identifier,
            data=supplied.model_copy(
                update={"biotools": entry, "europe_pmc": pmc_records}
            ),
        )
    except ValidationError as error:
        raise BiotoolsResolutionError(
            f"Invalid bio.tools entry {identifier!r}: {error}"
        ) from error
