"""Validation of supported repository root URLs."""

from urllib.parse import urlsplit


class SkippedURL(ValueError):
    """The URL points inside a repository instead of to its root."""


def repository_url(url: str) -> str:
    """Return a GitHub or GitLab repository root, rejecting other URLs."""
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    parts = parsed.path.strip("/").split("/")
    if (
        parsed.scheme not in {"http", "https"}
        or host not in {"github.com", "gitlab.com"}
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.query
        or parsed.fragment
        or any(not part for part in parts)
        or len(parts) < 2
    ):
        raise ValueError(f"not a GitHub or GitLab repository URL: {url!r}")
    if host == "github.com" and len(parts) != 2:
        raise SkippedURL(f"GitHub URL has a path beyond the repository: {url!r}")
    if host == "gitlab.com" and "-" in parts:
        raise SkippedURL(f"GitLab URL points inside a repository: {url!r}")
    return url.strip()
