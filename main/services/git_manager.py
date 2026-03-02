from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Raised when a git command fails."""


class GitManager:
    """Simple wrapper around git CLI for the FabInventory data repository."""

    repo_root: Path = Path(__file__).parent.parent.parent  # project root

    @classmethod
    def run_git_command(cls, args: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        cwd = cwd or cls.repo_root
        return subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )

    @classmethod
    def pull(cls) -> None:
        """Pull latest changes from remote. Raises :class:`GitError` on failure."""
        res = cls.run_git_command(["pull"])
        if res.returncode != 0:
            raise GitError(res.stderr.strip())

    @classmethod
    def add_commit_push(cls, message: str = "Auto update") -> None:
        """Stage all changes, commit with ``message`` and push.

        If there is nothing to commit the operation is a no‑op.
        """
        cls.run_git_command(["add", "."])
        res = cls.run_git_command(["commit", "-m", message])
        # git returns non-zero when there is nothing to commit; ignore that situation
        if res.returncode != 0 and "nothing to commit" not in res.stderr.lower():
            raise GitError(res.stderr.strip())
        res = cls.run_git_command(["push"])
        if res.returncode != 0:
            raise GitError(res.stderr.strip())
