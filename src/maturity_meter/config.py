"""Typed runtime configuration for Maturity meter.

Settings are read from environment variables prefixed with
``MATURITY_METER_``. A local ``.env`` file is supported
for development and is excluded from version control. Production deployments
should inject values through their platform or secrets manager.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings shared by generated runtime adapters.

    Parameters
    ----------
    log_level : {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        Application logging threshold.
    server_host : str
        Network interface on which the HTTP server listens.
    server_port : int
        TCP port on which the HTTP server listens.
    server_root_path : str
        Optional URL path used when the application is mounted by a proxy.
    server_reload : bool
        Whether the development server watches source files for changes.
    public_base_url : pydantic.AnyHttpUrl | None
        Optional externally visible URL published in API metadata.
    github_token : pydantic.SecretStr | None
        Optional GitHub personal access token. Requests are unauthenticated
        (and heavily rate limited) when omitted.
    gitlab_token : pydantic.SecretStr | None
        Optional GitLab personal access token. Public projects can be read
        without one.
    openalex_api_key : pydantic.SecretStr | None
        Optional OpenAlex API key for higher rate limits.
    resqui_parallel : int | None
        Maximum number of resqui plugins whose checks run at the same time.
        All configured plugins run at once when omitted. In a batch, the limit
        is shared by all tools in progress (one per plugin when omitted).
    batch_jobs : int
        Number of tools a batch evaluates at the same time, unless the
        command's ``--jobs`` option says otherwise.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MATURITY_METER_",
        extra="ignore",
        # ``.env.example`` lists every setting with an empty value; an empty
        # value means "not set" (e.g. no token), not an empty string.
        env_ignore_empty=True,
    )

    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    server_host: str = Field(default="127.0.0.1", min_length=1)
    server_port: int = Field(default=8000, ge=1, le=65535)
    server_root_path: str = ""
    server_reload: bool = False
    public_base_url: AnyHttpUrl | None = None
    github_token: SecretStr | None = None
    gitlab_token: SecretStr | None = None
    openalex_api_key: SecretStr | None = None
    resqui_parallel: int | None = Field(default=None, ge=1)
    batch_jobs: int = Field(default=4, ge=1)

    @field_validator("server_host")
    @classmethod
    def normalize_server_host(cls, value: str) -> str:
        """Strip surrounding whitespace from a non-empty bind host.

        Parameters
        ----------
        value : str
            Configured bind host.

        Returns
        -------
        str
            Normalized bind host.

        Raises
        ------
        ValueError
            If the host contains only whitespace.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError("Server host must not be empty")
        return normalized

    @field_validator("server_root_path")
    @classmethod
    def normalize_server_root_path(cls, value: str) -> str:
        """Normalize a non-empty proxy root path.

        Parameters
        ----------
        value : str
            Configured root path.

        Returns
        -------
        str
            Empty string or one slash-prefixed path without a trailing slash.
        """
        normalized = value.strip().strip("/")
        return f"/{normalized}" if normalized else ""


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings object for the current process.

    Returns
    -------
    Settings
        Validated runtime settings.
    """
    return Settings()
