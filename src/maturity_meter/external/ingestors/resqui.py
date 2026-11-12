"""
Runner for the EVERSE ``resqui`` quality pipeline.
Runs the ``resqui`` command-line tool on a repository and returns its parsed
JSON assessment. resqui clones the repository and runs its checks in Docker, so
``git`` and a running Docker daemon are required.

Every run labels the containers resqui starts, so they can be removed if
resqui hangs or is cancelled.
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


class ResquiError(Exception):
    """Raised when resqui is unavailable or its run fails."""


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
    """

    def __init__(
        self,
        repository_url: str,
        github_token: str | None = None,
        config: Path = DEFAULT_CONFIG,
    ):
        self.repository_url = repository_url
        self.github_token = github_token
        self.config = config

    async def fetch(self) -> dict[str, Any]:
        """
        Run resqui and return its JSON assessment.

        Returns
        -------
        dict
            The resqui ``SoftwareQualityAssessment`` document, whose ``checks``
            list has one entry per indicator that ran. Indicators resqui had to
            skip (for example for a missing token) are absent.

        Raises
        ------
        ResquiError
            If resqui or Docker is not installed, or the run fails, times out,
            or writes no output.
        """
        docker = shutil.which("docker")
        if docker is None:
            raise ResquiError("Docker was not found; resqui needs it for its checks")

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
                env = {**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}"}
                assessment = await self._run(workdir, env)
        finally:
            await _remove_containers(docker, run_id)

        logger.info(
            f"resqui ran {len(assessment.get('checks', []))} checks on "
            f"{self.repository_url}"
        )
        configured = json.loads(self.config.read_text())["indicators"]
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

    async def _run(self, workdir: Path, env: dict[str, str]) -> dict[str, Any]:
        """Run the resqui process and parse its output file."""
        output = workdir / "assessment.json"
        command = [
            _executable(),
            "-u",
            self.repository_url,
            "-c",
            str(self.config),
            "-o",
            str(output),
        ]
        if self.github_token:
            command += ["-t", self.github_token]

        logger.debug(f"Running resqui on {self.repository_url}")
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
            logger.warning("resqui reported check failures: %s", "; ".join(failures))
        try:
            assessment: dict[str, Any] = json.loads(output.read_text())
        except ValueError as error:
            raise ResquiError(f"resqui wrote an invalid assessment: {error}") from error
        return assessment
