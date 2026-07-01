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
        self.repo = None

        # Start with env overrides, then fall back to git config, then hard default
        self.user_name = user_name or os.getenv("GIT_AUTHOR_NAME") or ""
        self.user_email = user_email or os.getenv("GIT_AUTHOR_EMAIL") or ""

        if GIT_AVAILABLE:
            self._init_repo()

    # ── helpers ─────────────────────────────────────────────────

    def _init_repo(self):
        """Open the existing repo at *repo_path* — never create one.
        Also reads the real Git user identity from config."""
        if not GIT_AVAILABLE:
            return
        try:
            dot_git = self.repo_path / ".git"
            if dot_git.exists():
                self.repo = Repo(self.repo_path)
                self._read_git_user()
        except Exception as e:
            print(f"Git: could not open repo at {self.repo_path} — {e}")
            self.repo = None

    def _read_git_user(self):
        """Read user.name / user.email from repo config, falling back
        to global config, and finally to a sensible default."""
        if not self.repo:
            return
        reader = self.repo.config_reader()
        # Try repo-level first, then global
        name = self._cfg_get(reader, "user", "name")
        email = self._cfg_get(reader, "user", "email")

        # Only override if not already set via env/constructor
        if not self.user_name:
            self.user_name = name or "Unknown"
        if not self.user_email:
            self.user_email = email or "unknown@local"

        # If it's STILL the old hardcoded default from env, replace it
        if self.user_name == "FabInventory":
            self.user_name = name or "Unknown"

    @staticmethod
    def _cfg_get(reader, section, option):
        """Try repo config, then global config, then return None."""
        try:
            return reader.get_value(section, option)
        except Exception:
            pass
        # Try global git config
        try:
            from git import GitConfigParser
            global_cfg = GitConfigParser(
                os.path.expanduser("~/.gitconfig"), read_only=True
            )
            return global_cfg.get_value(section, option)
        except Exception:
            pass
        return None

    def is_active(self) -> bool:
        """True when Git is available AND a repo was found."""
        return GIT_AVAILABLE and self.repo is not None

    def commits_ahead(self, remote_name: str = "origin") -> int:
        """Number of local commits that haven't been pushed yet.  -1 if unknown."""
        if not self.is_active():
            return -1
        try:
            if remote_name not in [r.name for r in self.repo.remotes]:
                return -1
            branch = self.get_current_branch()
            remote_ref = f"{remote_name}/{branch}"
            if remote_ref not in [ref.name for ref in self.repo.refs]:
                return 0  # remote branch doesn't exist yet
            local_commit = self.repo.commit(branch)
            remote_commit = self.repo.commit(remote_ref)
            count = 0
            for c in self.repo.iter_commits(f"{remote_ref}..{branch}"):
                count += 1
            return count
        except Exception:
            return -1

    def is_ahead(self, remote_name: str = "origin") -> bool:
        """True when there are local commits not yet pushed to remote."""
        return self.commits_ahead(remote_name) > 0

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

    def push(self, remote_name: str = "origin") -> bool:
        """Push current branch to a configured remote."""
        if not self.is_active():
            return False
        try:
            if remote_name not in [r.name for r in self.repo.remotes]:
                return False
            branch = self.get_current_branch()
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

    def pull(self, remote_name: str = "origin") -> bool:
        """Pull current branch from a configured remote."""
        if not self.is_active():
            return False
        try:
            if remote_name not in [r.name for r in self.repo.remotes]:
                return False
            branch = self.get_current_branch()
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

    def get_remote_urls(self) -> Dict[str, str]:
        """Return {remote_name: url} for all configured remotes."""
        if not self.is_active():
            return {}
        return {r.name: list(r.urls)[0] for r in self.repo.remotes if r.urls}

    def get_current_branch(self) -> str:
        """Return the active branch name, or 'main' if detached."""
        if not self.is_active():
            return "main"
        try:
            if self.repo.active_branch:
                return self.repo.active_branch.name
            return "main"
        except Exception:
            return "main"

    def get_user(self) -> Dict[str, str]:
        """Return the current Git user identity being used for commits."""
        return {"name": self.user_name, "email": self.user_email}

    def set_user(self, name: str, email: str) -> bool:
        """Set git user.name and user.email in the repo config (persistent)."""
        if not self.is_active():
            return False
        try:
            with self.repo.config_writer() as cw:
                cw.set_value("user", "name", name)
                cw.set_value("user", "email", email)
            self.user_name = name
            self.user_email = email
            return True
        except Exception as e:
            print(f"Git user config error: {e}")
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
