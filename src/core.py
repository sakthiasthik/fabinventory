"""
Shared application state, auth decorators, and configuration.

Imported by both ``app.py`` and all route blueprints.
Kept separate to avoid circular imports.
"""
import os
from pathlib import Path
from functools import wraps
from flask import session, redirect, url_for, jsonify

from src.file_manager import FileManager
from src.git_manager import GitManager
from src.project_manager import ProjectManager
from src.inventory_manager import InventoryManager
from src.aggregator import Aggregator

# ── Configuration from environment ─────────────────────────────
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'fabinventory')
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')
GITHUB_OAUTH_ENABLED = bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)


# ── Auth decorators ────────────────────────────────────────────
def login_required(f):
    """Decorator to require authentication for page routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """Decorator for API routes — returns JSON error instead of redirect."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ── Global application state ───────────────────────────────────
class AppState:
    def __init__(self):
        self.data_path = os.environ.get('DATA_PATH', './fabinventory_data')
        self.file_manager = None
        self.git_manager = None
        self.project_manager = None
        self.inventory_manager = None
        self.aggregator = None
        self.config = None
        self.initialized = False

    def init_app(self):
        """Initialize all managers."""
        if not self.initialized:
            self.file_manager = FileManager(self.data_path)
            self.config = self.file_manager.load_config()

            if not self.config:
                return False

            import os as _os
            project_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
            self.git_manager = GitManager(project_root)
            self.aggregator = Aggregator(self.config.company_prefix)

            self.project_manager = ProjectManager(self.file_manager)
            self.inventory_manager = InventoryManager(self.file_manager, self.aggregator)

            projects = list(self.project_manager.projects.values())
            self.inventory_manager.update_inventory(projects)
            self.inventory_manager.update_non_elec_inventory(projects)

            self.initialized = True
        return True


state = AppState()
