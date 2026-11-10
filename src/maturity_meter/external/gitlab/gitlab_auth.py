"""
Helper for constructing GitLab API request headers using configured credentials.
"""

from maturity_meter.config import get_settings


def get_gitlab_headers(host: str = "gitlab.com") -> dict[str, str]:
    """
    Construct headers for GitLab API requests.

    The ``PRIVATE-TOKEN`` header is only included for ``gitlab.com`` and only
    when a token is configured via ``MATURITY_METER_GITLAB_TOKEN``. The token is
    never sent to other hosts, since any GitLab instance can be requested.

    Parameters
    ----------
    host : str, default="gitlab.com"
        GitLab instance the request is for.

    Returns
    -------
    dict
        A dictionary containing the accept header and, if configured, the
        token header.
    """
    headers = {"Accept": "application/json"}
    token = get_settings().gitlab_token
    if token is not None and host == "gitlab.com":
        headers["PRIVATE-TOKEN"] = token.get_secret_value()
    return headers
