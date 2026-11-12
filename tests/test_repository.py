import asyncio
import subprocess
from unittest.mock import AsyncMock

import pytest

from maturity_meter.external import repository
from maturity_meter.external.repository import CloneError, shared_clone


def _git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


@pytest.fixture
def origin(tmp_path):
    """A local repository with one commit and an extra branch."""
    path = tmp_path / "origin"
    path.mkdir()
    (path / "main.py").write_text("print('hi')\n")
    _git("-C", str(path), "init", "-q")
    _git("-C", str(path), "add", ".")
    _git(
        "-C",
        str(path),
        *("-c", "user.name=t", "-c", "user.email=t@t"),
        *("commit", "-q", "-m", "init"),
    )
    _git("-C", str(path), "branch", "other")
    return path


def test_clones_once_for_concurrent_callers(origin, monkeypatch):
    calls = []
    real_git = repository._git

    async def counting_git(*args):
        calls.append(args[0] if args[0] != "-C" else args[2])
        await real_git(*args)

    monkeypatch.setattr(repository, "_git", counting_git)

    async def main():
        async with shared_clone(str(origin)) as clone:
            mirror, checkout, again = await asyncio.gather(
                clone.mirror(), clone.checkout(), clone.mirror()
            )
            branches = subprocess.run(
                ["git", "-C", str(mirror), "branch", "--format=%(refname:short)"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
            return mirror, checkout, again, branches, (checkout / "main.py").exists()

    mirror, checkout, again, branches, has_file = asyncio.run(main())
    assert calls == ["clone", "worktree"]
    assert mirror == again
    assert has_file
    # The mirror keeps every branch, for tools that check out other refs.
    assert "other" in branches
    # Everything is removed afterwards.
    assert not mirror.exists() and not checkout.exists()


def test_failed_clone_is_shared_and_not_retried(tmp_path, monkeypatch):
    git = AsyncMock(side_effect=CloneError("fatal: not found"))
    monkeypatch.setattr(repository, "_git", git)

    async def main():
        async with shared_clone(str(tmp_path / "missing")) as clone:
            return await asyncio.gather(
                clone.mirror(), clone.checkout(), return_exceptions=True
            )

    results = asyncio.run(main())
    assert all(isinstance(result, CloneError) for result in results)
    assert "fatal: not found" in str(results[0])
    git.assert_awaited_once()


def test_nothing_is_cloned_unless_asked(monkeypatch):
    git = AsyncMock()
    monkeypatch.setattr(repository, "_git", git)

    async def main():
        async with shared_clone("https://github.com/x/y"):
            pass

    asyncio.run(main())
    git.assert_not_awaited()
