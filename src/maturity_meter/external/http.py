"""Shared HTTP helpers for the ingestors.

All requests go through :func:`get_json`. Inside :func:`shared_client` every
request reuses one connection pool, so an evaluation's many calls (about 15 to
GitHub alone) do not each open a new connection; outside it, each request uses
a short-lived client, so ingestors also work on their own.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Collection
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15

_client: ContextVar[httpx.AsyncClient | None] = ContextVar("http_client", default=None)


@asynccontextmanager
async def shared_client() -> AsyncIterator[httpx.AsyncClient]:
    """Reuse one connection pool for every request made inside this block.

    The client is held in a context variable, so tasks started inside the
    block (e.g. by ``asyncio.gather``) share it too. Nesting reuses the outer
    client.

    Yields
    ------
    httpx.AsyncClient
        The shared client.
    """
    current = _client.get()
    if current is not None:
        yield current
        return
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
        token = _client.set(client)
        try:
            yield client
        finally:
            _client.reset(token)


@asynccontextmanager
async def _client_for_request() -> AsyncIterator[httpx.AsyncClient]:
    """The shared client if there is one, otherwise a short-lived client."""
    current = _client.get()
    if current is not None:
        yield current
    else:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            yield client


async def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    follow_redirects: bool = False,
) -> Any:
    """GET ``url`` and return its parsed body.

    Parameters
    ----------
    url : str
        URL to request.
    params : dict, optional
        Query parameters.
    headers : dict, optional
        Request headers.
    timeout : float, default=DEFAULT_TIMEOUT_SECONDS
        Request timeout in seconds.
    follow_redirects : bool, default=False
        Whether to follow redirects.

    Returns
    -------
    Any
        Parsed JSON for JSON responses, the text for other responses (e.g. a
        raw README), or None for 204 No Content.

    Raises
    ------
    httpx.HTTPStatusError, httpx.RequestError
        For HTTP error statuses and network failures; both are logged.
    """
    try:
        async with _client_for_request() as client:
            response = await client.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                follow_redirects=follow_redirects,
            )
        response.raise_for_status()
    except httpx.RequestError as e:
        logger.error(f"Network error while fetching {url}: {e}")
        raise
    except httpx.HTTPStatusError as e:
        logger.debug(f"HTTP error {e.response.status_code} from {url}")
        raise
    if response.status_code == 204:
        return None
    if "json" in response.headers.get("content-type", ""):
        return response.json()
    return response.text


async def get_json_optional(
    url: str,
    *,
    missing: Collection[int] | Callable[[httpx.Response], bool] = (404,),
    **kwargs: Any,
) -> Any:
    """Like :func:`get_json`, but return None when the resource is missing.

    Parameters
    ----------
    url : str
        URL to request.
    missing : collection of int or callable, default=(404,)
        Statuses meaning "not there", or a predicate on the error response for
        cases a status alone cannot decide (e.g. GitHub's 403 that is not a
        rate limit). Other errors still raise.
    **kwargs
        Passed to :func:`get_json`.

    Returns
    -------
    Any
        As :func:`get_json`, or None when missing.
    """
    try:
        return await get_json(url, **kwargs)
    except httpx.HTTPStatusError as e:
        is_missing = (
            missing(e.response)
            if callable(missing)
            else e.response.status_code in missing
        )
        if not is_missing:
            logger.warning(f"HTTP error {e.response.status_code} from {url}")
            raise
        return None


async def get_pages(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    per_page: int = 100,
    max_pages: int = 3,
    **kwargs: Any,
) -> list[Any] | None:
    """Fetch up to ``max_pages`` pages of a list endpoint (``page``/``per_page``).

    The first page is fetched alone; if it is full, the remaining pages are
    fetched concurrently and the list ends at the first short page.

    Parameters
    ----------
    url : str
        List endpoint.
    params : dict, optional
        Query parameters besides the pagination ones.
    per_page : int, default=100
        Page size.
    max_pages : int, default=3
        Maximum number of pages, which caps the list length.
    **kwargs
        Passed to :func:`get_json_optional` (e.g. ``headers``, ``missing``).

    Returns
    -------
    list | None
        The items, or None if the endpoint is missing.
    """

    async def page(number: int) -> list[Any] | None:
        result: list[Any] | None = await get_json_optional(
            url,
            params={**(params or {}), "per_page": per_page, "page": number},
            **kwargs,
        )
        return result

    first = await page(1)
    if first is None:
        return None
    items = list(first)
    if len(first) < per_page or max_pages < 2:
        return items
    for batch in await asyncio.gather(*(page(n) for n in range(2, max_pages + 1))):
        items.extend(batch or [])
        if batch is None or len(batch) < per_page:
            break
    return items
