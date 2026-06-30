"""Git integration for FabInventory"""

import os
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from datetime import datetime

# Try to import GitPython, handle if not installed
try:
    from git import Repo, Actor, GitCommandError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    print("Warning: GitPython not installed. Run: pip install GitPython")


class GitManager:
    """Handles all Git operations for version control"""
    
    def __init__(self, repo_path: str, user_name: Optional[str] = None, 
                 user_email: Optional[str] = None):
        self.repo_path = Path(repo_path)
        self.user_name = user_name or os.getenv("GIT_AUTHOR_NAME", "FabInventory User")
        self.user_email = user_email or os.getenv("GIT_AUTHOR_EMAIL", "user@fabinventory.local")
        self.repo = None
        
        if GIT_AVAILABLE:
            self._init_repo()
        else:
            print("Git functionality disabled - install GitPython to enable")
    
    def _init_repo(self):
        """Initialize or load Git repository"""
        if not GIT_AVAILABLE:
            return
        
        try:
            if self.repo_path.exists() and (self.repo_path / ".git").exists():
                self.repo = Repo(self.repo_path)
            else:
                self.repo_path.mkdir(parents=True, exist_ok=True)
                self.repo = Repo.init(self.repo_path)
                # Create initial .gitignore
                gitignore = self.repo_path / ".gitignore"
                if not gitignore.exists():
                    gitignore.write_text("__pycache__/\n*.pyc\n*.pyo\n.DS_Store\n")
                self.commit("Initial commit")
        except Exception as e:
            print(f"Error initializing Git repository: {e}")
            self.repo = None
    
    def commit(self, message: str, author=None) -> bool:
        """Commit all changes in the repository"""
        if not GIT_AVAILABLE or not self.repo:
            print("Git not available - changes not committed")
            return False
        
        try:
            # Add all changes
            self.repo.index.add("*")
            
            # Check if there are changes to commit
            if not self.repo.index.diff("HEAD"):
                # No changes to commit
                return True
            
            # Create commit
            if author is None and GIT_AVAILABLE:
                author_obj = Actor(self.user_name, self.user_email)
                self.repo.index.commit(message, author=author_obj, committer=author_obj)
            elif GIT_AVAILABLE:
                self.repo.index.commit(message, author=author, committer=author)
            else:
                return False
            return True
        except Exception as e:
            print(f"Error committing changes: {e}")
            return False
    
    def push(self, remote_name: str = "origin", branch: str = "main") -> bool:
        """Push changes to remote repository"""
        if not GIT_AVAILABLE or not self.repo:
            print("Git not available - cannot push")
            return False
        
        try:
            # Ensure remote exists
            if remote_name not in [remote.name for remote in self.repo.remotes]:
                print(f"Remote '{remote_name}' not found. Use setup_remote() first.")
                return False
            
            # Push to remote
            remote = self.repo.remote(remote_name)
            push_info = remote.push(refspec=f"{branch}:{branch}")
            
            # Check if push was successful
            for info in push_info:
                if hasattr(info, 'flags') and info.flags & info.ERROR:
                    print(f"Push error: {info.summary}")
                    return False
            
            return True
        except Exception as e:
            print(f"Error pushing to remote: {e}")
            return False
    
    def pull(self, remote_name: str = "origin", branch: str = "main") -> bool:
        """Pull changes from remote repository"""
        if not GIT_AVAILABLE or not self.repo:
            print("Git not available - cannot pull")
            return False
        
        try:
            remote = self.repo.remote(remote_name)
            pull_info = remote.pull(refspec=f"{branch}:{branch}")
            
            # Check if pull was successful
            for info in pull_info:
                if hasattr(info, 'flags') and info.flags & info.ERROR:
                    print(f"Pull error: {info.summary}")
                    return False
            
            return True
        except Exception as e:
            print(f"Error pulling from remote: {e}")
            return False
    
    def setup_remote(self, remote_url: str, remote_name: str = "origin") -> bool:
        """Setup a remote repository"""
        if not GIT_AVAILABLE or not self.repo:
            print("Git not available - cannot setup remote")
            return False
        
        try:
            # Remove existing remote if it exists
            if remote_name in [remote.name for remote in self.repo.remotes]:
                self.repo.delete_remote(remote_name)
            
            # Create new remote
            self.repo.create_remote(remote_name, remote_url)
            return True
        except Exception as e:
            print(f"Error setting up remote: {e}")
            return False
    
    def get_status(self) -> dict:
        """Get repository status"""
        if not GIT_AVAILABLE or not self.repo:
            return {
                "git_available": False,
                "is_dirty": False,
                "untracked_files": [],
                "current_branch": "git_not_available",
                "has_remotes": False,
                "remotes": []
            }
        
        try:
            status = {
                "git_available": True,
                "is_dirty": self.repo.is_dirty(),
                "untracked_files": self.repo.untracked_files,
                "current_branch": self.repo.active_branch.name if self.repo.active_branch else "detached",
                "has_remotes": len(self.repo.remotes) > 0,
                "remotes": [remote.name for remote in self.repo.remotes]
            }
            return status
        except Exception as e:
            print(f"Error getting git status: {e}")
            return {
                "git_available": True,
                "error": str(e),
                "is_dirty": False,
                "untracked_files": [],
                "current_branch": "unknown",
                "has_remotes": False,
                "remotes": []
            }
    
    def get_commit_history(self, max_count: int = 10) -> List[Dict]:
        """Get commit history"""
        if not GIT_AVAILABLE or not self.repo:
            return []
        
        try:
            commits = []
            for commit in self.repo.iter_commits(max_count=max_count):
                commits.append({
                    "hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": datetime.fromtimestamp(commit.committed_date).isoformat()
                })
            return commits
        except Exception as e:
            print(f"Error getting commit history: {e}")
            return []
    
    def clone_repository(self, remote_url: str, local_path: str) -> bool:
        """Clone a remote repository"""
        if not GIT_AVAILABLE:
            print("Git not available - cannot clone")
            return False
        
        try:
            self.repo = Repo.clone_from(remote_url, local_path)
            self.repo_path = Path(local_path)
            return True
        except Exception as e:
            print(f"Error cloning repository: {e}")
            return False
