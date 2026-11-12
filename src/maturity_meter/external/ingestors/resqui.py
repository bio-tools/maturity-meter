"""
Runner for the EVERSE ``resqui`` quality pipeline.
Runs the ``resqui`` command-line tool on a repository and returns its parsed
JSON assessment. resqui clones the repository and runs its checks in Docker, so
``git`` and a running Docker daemon are required.

resqui runs its checks one after another, so the configuration is split by
plugin and one resqui process runs per plugin, several at a time. Their
assessments are merged into one. Given a local mirror of the repository, git
is told to clone from it instead of the network, so the resqui processes do
not each download the repository.

Every run labels the containers resqui starts, so they can be removed if
resqui hangs or is cancelled.

Inside :func:`shared_limit`, every resqui run shares one limit on the number of
resqui processes, so several evaluations at once (a batch) do not overload
Docker.
"""

import asyncio
import contextlib
import json
import logging
import os
import re
import shutil
import signal
import sys
import tempfile
import uuid
from collections.abc import Iterator
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from maturity_meter.external.protocols import Ingestor

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = Path(__file__).parent / "resqui_config.json"
TIMEOUT_SECONDS = 600
LABEL = "maturity-meter-run"
_CHECKING_SOFTWARE_NAMES = {
    "Gitleaks": "GitLeaks",
    "OpenSSFScorecard": "OpenSSF Scorecard",
}
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

# Placed first on resqui's PATH. resqui starts containers with a bare
# ``docker run``, so add --rm (no leftovers) and a label (to find them later).
_DOCKER_SHIM = """#!/bin/sh
if [ "$1" = "run" ]; then
  shift
  exec "{docker}" run --rm --label {label}={run_id} "$@"
fi
exec "{docker}" "$@"
"""

# Set by shared_limit: one limit on resqui processes for every run inside it.
_shared_slots: ContextVar[asyncio.Semaphore | None] = ContextVar(
    "resqui_slots", default=None
)


class ResquiError(Exception):
    """Raised when resqui is unavailable or its run fails."""


def plugin_count(config: Path = DEFAULT_CONFIG) -> int:
    """Return the number of resqui plugins (one process each) in ``config``."""
    indicators = json.loads(config.read_text())["indicators"]
    return len({indicator["plugin"] for indicator in indicators})


@contextlib.contextmanager
def shared_limit(limit: int) -> Iterator[None]:
    """Share one limit on resqui processes between all runs inside this block.

    Each :class:`ResquiIngestor` normally limits only its own plugins. Inside
    this block, the processes of every run (also in tasks started inside it)
    count towards ``limit`` together, and an ingestor's own ``parallel`` is
    ignored. Waiting for a free slot does not count towards a run's timeout.

    Parameters
    ----------
    limit : int
        Maximum number of resqui processes running at the same time.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    token = _shared_slots.set(asyncio.Semaphore(limit))
    try:
        yield
    finally:
        _shared_slots.reset(token)


def _executable() -> str:
    """Locate the resqui executable installed alongside this interpreter."""
    beside_python = Path(sys.executable).parent / "resqui"
    if beside_python.exists():
        return str(beside_python)
    found = shutil.which("resqui")
    if found is None:
        raise ResquiError("The resqui executable was not found")
    return found


async def _remove_containers(docker: str, run_id: str) -> None:
    """Force-remove any containers still running from this run."""
    list_process = await asyncio.create_subprocess_exec(
        docker,
        "ps",
        "-aq",
        "--filter",
        f"label={LABEL}={run_id}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await list_process.communicate()
    ids = stdout.decode().split()
    if ids:
        logger.warning(f"Removing {len(ids)} leftover resqui container(s)")
        remove = await asyncio.create_subprocess_exec(
            docker,
            "rm",
            "-f",
            *ids,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await remove.wait()


class ResquiIngestor(Ingestor):
    """
    Run resqui on a repository and return its quality assessment.

    Parameters
    ----------
    repository_url : str
        URL of the repository to assess.
    github_token : str, optional
        GitHub token; some checks (e.g. HowFairIs) are skipped without it.
    config : pathlib.Path, optional
        resqui configuration listing the indicators to run. Defaults to the
        configuration bundled with this package.
    parallel : int, optional
        Maximum number of plugins whose checks run at the same time; each
        runs its own Docker containers. All plugins run at once by default.
        Ignored inside :func:`shared_limit`, which sets one limit for all runs.
    mirror : pathlib.Path, optional
        Local clone of the repository for resqui to clone from instead of the
        network (see :class:`maturity_meter.external.repository.SharedClone`).
        Without it, every resqui process downloads the repository.
    """

    def __init__(
        self,
        repository_url: str,
        github_token: str | None = None,
        config: Path = DEFAULT_CONFIG,
        parallel: int | None = None,
        mirror: Path | None = None,
    ):
        if parallel is not None and parallel < 1:
            raise ValueError("parallel must be at least 1")
        self.repository_url = repository_url
        self.github_token = github_token
        self.config = config
        self.parallel = parallel
        self.mirror = mirror

    async def fetch(self) -> dict[str, Any]:
        """
        Run resqui and return its JSON assessment.

        Returns
        -------
        dict
            The resqui ``SoftwareQualityAssessment`` document, whose ``checks``
            list has one entry per indicator that ran. Indicators resqui had to
            skip (for example for a missing token), and those of a plugin whose
            run failed, are absent.

        Raises
        ------
        ResquiError
            If resqui or Docker is not installed, or the runs of all plugins
            fail, time out, or write no output.
        """
        docker = shutil.which("docker")
        if docker is None:
            raise ResquiError("Docker was not found; resqui needs it for its checks")

        configured = json.loads(self.config.read_text())["indicators"]
        run_id = uuid.uuid4().hex
        try:
            with tempfile.TemporaryDirectory() as directory:
                workdir = Path(directory)
                shim = workdir / "bin"
                shim.mkdir()
                (shim / "docker").write_text(
                    _DOCKER_SHIM.format(docker=docker, label=LABEL, run_id=run_id)
                )
                (shim / "docker").chmod(0o755)
                # resqui clones the repository into a temporary directory and
                # never deletes it; keep those clones here so they go too.
                clones = workdir / "tmp"
                clones.mkdir()
                env = {
                    **os.environ,
                    "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}",
                    "TMPDIR": str(clones),
                }
                if self.mirror is not None:
                    # Every ``git clone <url>`` reads the mirror instead. The
                    # clones' ``remote.origin.url`` stays the real URL, which
                    # resqui reports and passes to its checks.
                    env |= {
                        "GIT_CONFIG_COUNT": "1",
                        "GIT_CONFIG_KEY_0": f"url.{self.mirror}.insteadOf",
                        "GIT_CONFIG_VALUE_0": self.repository_url,
                    }
                assessment = await self._run_plugins(workdir, env, configured)
        finally:
            await _remove_containers(docker, run_id)

        logger.info(
            f"resqui ran {len(assessment.get('checks', []))} checks on "
            f"{self.repository_url}"
        )
        present = {
            (
                check.get("checkingSoftware", {}).get("name"),
                check.get("assessesIndicator", {}).get("@id"),
            )
            for check in assessment.get("checks", [])
        }
        missing = [
            f"{item['plugin']}.{item['name']}"
            for item in configured
            if (
                _CHECKING_SOFTWARE_NAMES.get(item["plugin"], item["plugin"]),
                item["@id"],
            )
            not in present
        ]
        if missing:
            logger.warning(
                "resqui did not report configured checks: %s", ", ".join(missing)
            )
        return assessment

    async def _run_plugins(
        self, workdir: Path, env: dict[str, str], indicators: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Run each plugin's indicators in its own resqui process, concurrently.

        Returns the merged assessment: the first successful run's document with
        the checks of all successful runs, in configuration order.
        """
        plugins: dict[str, list[dict[str, Any]]] = {}
        for indicator in indicators:
            plugins.setdefault(indicator["plugin"], []).append(indicator)
        semaphore = _shared_slots.get() or asyncio.Semaphore(
            self.parallel or len(plugins) or 1
        )

        async def run(plugin: str, group: list[dict[str, Any]]) -> dict[str, Any]:
            config = workdir / f"{plugin}.config.json"
            config.write_text(json.dumps({"indicators": group}))
            async with semaphore:
                return await self._run(workdir, env, plugin, config)

        results = await asyncio.gather(
            *(run(plugin, group) for plugin, group in plugins.items()),
            return_exceptions=True,
        )
        assessments: list[dict[str, Any]] = []
        errors: list[ResquiError] = []
        for plugin, result in zip(plugins, results, strict=True):
            if isinstance(result, ResquiError):
                logger.warning(f"Skipping resqui plugin {plugin}: {result}")
                errors.append(result)
            elif isinstance(result, BaseException):
                raise result
            else:
                assessments.append(result)
        if not assessments:
            raise errors[0] if errors else ResquiError("No resqui checks configured")
        return {
            **assessments[0],
            "checks": [check for a in assessments for check in a.get("checks", [])],
        }

    async def _run(
        self, workdir: Path, env: dict[str, str], plugin: str, config: Path
    ) -> dict[str, Any]:
        """Run one resqui process for ``plugin`` and parse its output file."""
        output = workdir / f"{plugin}.assessment.json"
        command = [
            _executable(),
            "-u",
            self.repository_url,
            "-c",
            str(config),
            "-o",
            str(output),
        ]
        if self.github_token:
            command += ["-t", self.github_token]

        logger.debug(f"Running resqui {plugin} checks on {self.repository_url}")
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env=env,
            # Own process group, so a hung run can be killed with its children.
            start_new_session=True,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=TIMEOUT_SECONDS
            )
        except BaseException as error:
            # Timeout or cancellation: stop resqui and everything it started.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            await process.wait()
            if isinstance(error, TimeoutError):
                raise ResquiError(
                    f"resqui timed out after {TIMEOUT_SECONDS}s"
                ) from error
            raise

        def redact(text: str) -> str:
            return (
                text.replace(self.github_token, "[redacted]")
                if self.github_token
                else text
            )

        stdout_text = _ANSI_ESCAPE.sub("", stdout.decode(errors="replace"))
        failures = [
            redact(line.strip())
            for line in stdout_text.splitlines()
            if (
                re.search(r"✖\s+[A-Za-z_][\w.]*:", line)
                or "⚠" in line
                or line.strip().startswith("Error")
            )
        ]
        if process.returncode != 0 or not output.exists():
            lines = stderr.decode(errors="replace").strip().splitlines()
            detail = (
                redact(lines[-1])
                if lines
                else (failures[-1] if failures else "no error output")
            )
            raise ResquiError(f"resqui failed (exit {process.returncode}): {detail}")
        if failures:
            logger.warning(
                "resqui %s reported check failures: %s", plugin, "; ".join(failures)
            )
        try:
            assessment: dict[str, Any] = json.loads(output.read_text())
        except ValueError as error:
            raise ResquiError(f"resqui wrote an invalid assessment: {error}") from error
        return assessment
