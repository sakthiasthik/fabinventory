"""Git integration for FabInventory"""

import os
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

try:
    from git import Repo, Actor, GitCommandError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class GitManager:
    """Handles Git operations for version-controlling inventory data.

    Targets the *project root* repo (where the application code lives),
    NOT a separate data-only repo.  This keeps everything in one place
    and avoids nested-.git / submodule headaches.

    When GitPython is unavailable or no .git exists (e.g. after a
    ``pip install``), all methods degrade gracefully — they log and
    return False / empty results rather than raising.
    """

    def __init__(self, repo_path: str = ".", user_name: Optional[str] = None,
                 user_email: Optional[str] = None):
        self.repo_path = Path(repo_path).resolve()
        self.user_name = user_name or os.getenv("GIT_AUTHOR_NAME", "FabInventory")
        self.user_email = user_email or os.getenv("GIT_AUTHOR_EMAIL", "fabinventory@local")
        self.repo = None

        if GIT_AVAILABLE:
            self._init_repo()

    # ── helpers ─────────────────────────────────────────────────

    def _init_repo(self):
        """Open the existing repo at *repo_path* — never create one."""
        if not GIT_AVAILABLE:
            return
        try:
            dot_git = self.repo_path / ".git"
            if dot_git.exists():
                self.repo = Repo(self.repo_path)
        except Exception as e:
            print(f"Git: could not open repo at {self.repo_path} — {e}")
            self.repo = None

    def is_active(self) -> bool:
        """True when Git is available AND a repo was found."""
        return GIT_AVAILABLE and self.repo is not None

    # ── public API ──────────────────────────────────────────────

    def commit(self, message: str, author=None) -> bool:
        """Stage and commit all changes."""
        if not self.is_active():
            return False
        try:
            self.repo.index.add("*")
            if not self.repo.index.diff("HEAD"):
                return True                      # nothing to commit
            committer = author or Actor(self.user_name, self.user_email)
            self.repo.index.commit(message, author=committer, committer=committer)
            return True
        except Exception as e:
            print(f"Git commit error: {e}")
            return False

    def push(self, remote_name: str = "origin", branch: str = "main") -> bool:
        """Push to a configured remote."""
        if not self.is_active():
            return False
        try:
            if remote_name not in [r.name for r in self.repo.remotes]:
                print(f"Git: remote '{remote_name}' not configured.")
                return False
            remote = self.repo.remote(remote_name)
            push_info = remote.push(refspec=f"{branch}:{branch}")
            for info in push_info:
                if hasattr(info, "flags") and info.flags & info.ERROR:
                    print(f"Git push error: {info.summary}")
                    return False
            return True
        except Exception as e:
            print(f"Git push error: {e}")
            return False

    def pull(self, remote_name: str = "origin", branch: str = "main") -> bool:
        """Pull from a configured remote."""
        if not self.is_active():
            return False
        try:
            remote = self.repo.remote(remote_name)
            pull_info = remote.pull(refspec=f"{branch}:{branch}")
            for info in pull_info:
                if hasattr(info, "flags") and info.flags & info.ERROR:
                    print(f"Git pull error: {info.summary}")
                    return False
            return True
        except Exception as e:
            print(f"Git pull error: {e}")
            return False

    def setup_remote(self, remote_url: str, remote_name: str = "origin") -> bool:
        """Add or update a remote."""
        if not self.is_active():
            return False
        try:
            if remote_name in [r.name for r in self.repo.remotes]:
                self.repo.delete_remote(remote_name)
            self.repo.create_remote(remote_name, remote_url)
            return True
        except Exception as e:
            print(f"Git remote setup error: {e}")
            return False

    def get_status(self) -> dict:
        """Return repo status as a template-friendly dict."""
        if not self.is_active():
            return {
                "git_available": False,
                "is_dirty": False,
                "untracked_files": [],
                "current_branch": "no_repo",
                "has_remotes": False,
                "remotes": [],
            }
        try:
            return {
                "git_available": True,
                "is_dirty": self.repo.is_dirty(),
                "untracked_files": self.repo.untracked_files,
                "current_branch": (
                    self.repo.active_branch.name if self.repo.active_branch else "detached"
                ),
                "has_remotes": len(self.repo.remotes) > 0,
                "remotes": [r.name for r in self.repo.remotes],
            }
        except Exception as e:
            print(f"Git status error: {e}")
            return {
                "git_available": True,
                "error": str(e),
                "is_dirty": False,
                "untracked_files": [],
                "current_branch": "unknown",
                "has_remotes": False,
                "remotes": [],
            }

    def get_commit_history(self, max_count: int = 10) -> List[Dict]:
        """Return recent commits."""
        if not self.is_active():
            return []
        try:
            commits = []
            for commit in self.repo.iter_commits(max_count=max_count):
                commits.append({
                    "hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
                })
            return commits
        except Exception as e:
            print(f"Git history error: {e}")
            return []
