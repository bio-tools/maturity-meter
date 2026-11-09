"""
Helper for constructing GitHub API request headers using configured credentials.
"""

from maturity_meter.config import get_settings


def get_github_headers() -> dict[str, str]:
    """
    Construct headers for GitHub API requests.

    The ``Authorization`` header is only included when a token is configured
    via ``MATURITY_METER_GITHUB_TOKEN``.

    Returns
    -------
    dict
        A dictionary containing the accept header and, if configured, the
        authorization header.
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = get_settings().github_token
    if token is not None:
        headers["Authorization"] = f"Bearer {token.get_secret_value()}"
    return headers
