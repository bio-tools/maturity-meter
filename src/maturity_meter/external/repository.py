"""One local clone of the evaluated repository, shared by the ingestors.

Several sources need the repository's files: code metrics analyse a working
tree, and every resqui process clones the repository again. Inside
:func:`shared_clone` the repository is downloaded at most once, on first use,
and removed when the block ends.
"""

import asyncio
import contextlib
import logging
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

CLONE_TIMEOUT_SECONDS = 600


class CloneError(Exception):
    """Raised when the repository cannot be cloned."""


async def _git(*args: str) -> None:
    """Run git, raising CloneError if it fails or times out."""
    try:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            # Never let git stop to ask for credentials (e.g. a missing repo).
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except FileNotFoundError as error:
        raise CloneError("git was not found") from error
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), CLONE_TIMEOUT_SECONDS)
    except TimeoutError as error:
        raise CloneError(f"git timed out after {CLONE_TIMEOUT_SECONDS}s") from error
    finally:
        if process.returncode is None:  # timed out or cancelled
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
    if process.returncode != 0:
        raise CloneError(stderr.decode(errors="replace").strip() or "git failed")


class SharedClone:
    """A repository cloned on first use, then reused.

    Parameters
    ----------
    url : str
        Repository to clone.
    directory : pathlib.Path
        Empty directory to clone into; the caller removes it.
    """

    def __init__(self, url: str, directory: Path):
        self.url = url
        self._mirror = directory / "mirror.git"
        self._checkout = directory / "checkout"
        self._lock = asyncio.Lock()
        # Outcome of each step that has run: None on success, else its error.
        self._outcomes: dict[str, CloneError | None] = {}

    async def _once(self, step: str, *git_args: str) -> None:
        """Run a git step the first time only; later calls share its outcome."""
        async with self._lock:
            if step not in self._outcomes:
                try:
                    await _git(*git_args)
                    self._outcomes[step] = None
                except CloneError as error:
                    self._outcomes[step] = CloneError(
                        f"Could not {step} {self.url}: {error}"
                    )
        if (failure := self._outcomes[step]) is not None:
            raise failure

    async def mirror(self) -> Path:
        """Bare clone with every branch and tag, for tools that clone it again.

        Raises
        ------
        CloneError
            If the repository cannot be cloned.
        """
        await self._once("clone", "clone", "--bare", "--", self.url, str(self._mirror))
        return self._mirror

    async def checkout(self) -> Path:
        """Working tree of the default branch.

        Raises
        ------
        CloneError
            If the repository cannot be cloned.
        """
        mirror = await self.mirror()
        await self._once(
            "check out",
            *("-C", str(mirror), "worktree", "add", "--detach", str(self._checkout)),
        )
        return self._checkout


@asynccontextmanager
async def shared_clone(url: str) -> AsyncIterator[SharedClone]:
    """Share one clone of ``url`` within this block, removing it afterwards.

    Nothing is downloaded until a caller asks for the clone.

    Yields
    ------
    SharedClone
        The repository's clone.
    """
    with tempfile.TemporaryDirectory(prefix="maturity-meter-") as directory:
        yield SharedClone(url, Path(directory))
