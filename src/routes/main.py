"""Main Flask Blueprint — auth routes and core pages."""
import os
import re
import shutil
import requests

from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_from_directory,
)

from src.core import (
    state,
    login_required,
    ADMIN_PASSWORD,
    GITHUB_OAUTH_ENABLED,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
)

from src.file_manager import FileManager
from src.models import Config, derive_company_prefix

main_bp = Blueprint('main', __name__)


# ── Auth routes ───────────────────────────────────────────────────


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['authenticated'] = True
            flash('Logged in successfully!', 'success')
            return redirect(url_for('main.dashboard'))
        flash('Invalid password', 'error')
    return render_template('login.html')


@main_bp.route('/logout')
def logout():
    """Logout"""
    session.pop('authenticated', None)
    flash('Logged out.', 'info')
    return redirect(url_for('main.login'))


@main_bp.route('/login/github')
def login_github():
    """Redirect to GitHub for OAuth authorization."""
    if not GITHUB_OAUTH_ENABLED:
        flash('GitHub login is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env', 'error')
        return redirect(url_for('main.login'))
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={url_for('main.login_github_callback', _external=True)}"
        f"&scope=repo,user"
    )
    return redirect(github_auth_url)


@main_bp.route('/login/github/callback')
def login_github_callback():
    """Handle GitHub OAuth callback — exchange code for access token."""
    if not GITHUB_OAUTH_ENABLED:
        flash('GitHub login is not configured.', 'error')
        return redirect(url_for('main.login'))

    code = request.args.get('code')
    if not code:
        flash('GitHub authorization failed.', 'error')
        return redirect(url_for('main.login'))

    # Exchange code for access token
    try:
        token_resp = requests.post(
            'https://github.com/login/oauth/access_token',
            data={
                'client_id': GITHUB_CLIENT_ID,
                'client_secret': GITHUB_CLIENT_SECRET,
                'code': code,
            },
            headers={'Accept': 'application/json'},
            timeout=15,
        )
        token_data = token_resp.json()
        access_token = token_data.get('access_token')
        if not access_token:
            flash(f'GitHub auth failed: {token_data.get("error_description", "unknown error")}', 'error')
            return redirect(url_for('main.login'))
    except requests.RequestException as e:
        flash(f'Could not reach GitHub: {e}', 'error')
        return redirect(url_for('main.login'))

    # Get user info
    try:
        user_resp = requests.get(
            'https://api.github.com/user',
            headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'},
            timeout=15,
        )
        user_data = user_resp.json()
        github_username = user_data.get('login', 'unknown')
    except requests.RequestException:
        github_username = 'unknown'

    # Set session
    session['authenticated'] = True
    session['github_user'] = github_username
    session['github_token'] = access_token
    flash(f'Welcome, @{github_username}! Logged in via GitHub.', 'success')
    return redirect(url_for('main.dashboard'))


# ── Core pages ────────────────────────────────────────────────────


@main_bp.route('/')
def index():
    """Home page - redirect to dashboard or setup"""
    if not state.init_app():
        return redirect(url_for('main.setup'))
    return redirect(url_for('main.dashboard'))


def _normalize_link(link: str) -> str:
    """Return a clean http(s) URL, or '' for empty input."""
    link = link.strip()
    if not link:
        return ''
    if not re.match(r'^https?://', link, re.IGNORECASE):
        link = 'https://' + link
    return link


def _update_env_data_path(new_path: str) -> None:
    """Rewrite DATA_PATH in .env so restarts keep using the new folder."""
    try:
        # src/routes/main.py → repo root is three levels up
        env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        if not env_file.exists():
            return
        lines = env_file.read_text().splitlines()
        with env_file.open('w') as f:
            found = False
            for line in lines:
                if line.startswith('DATA_PATH='):
                    f.write(f'DATA_PATH={new_path}\n')
                    found = True
                else:
                    f.write(line + '\n')
            if not found:
                f.write(f'DATA_PATH={new_path}\n')
    except Exception as e:
        print(f'Could not update .env DATA_PATH: {e}')


@main_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Initial setup — company details, prefix, links."""
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        prefix = request.form.get('company_prefix', '').strip().upper()
        website = _normalize_link(request.form.get('website', ''))
        git_link = _normalize_link(request.form.get('git_link', ''))

        if not company_name:
            flash('Company name is required', 'error')
            return render_template('setup.html')

        # Prefix is optional — derive it from the company name when blank
        if not prefix:
            prefix = derive_company_prefix(company_name)
        else:
            prefix = ''.join(ch for ch in prefix if ch.isalnum())[:2].upper()
            if len(prefix) < 2:
                flash('Prefix must be at least 2 letters or numbers', 'error')
                return render_template('setup.html')

        # Data folder carries the prefix so it's recognizable on disk
        # (e.g. ~/fabinventory-data → ~/fabinventory-data-SA).
        # Never append twice: a folder already named -<PREFIX> is final.
        old_path = Path(state.data_path).resolve()
        if old_path.name.upper().endswith(f"-{prefix}"):
            new_path = old_path
        else:
            new_path = old_path.parent / f"{old_path.name}-{prefix}"

        if new_path != old_path:
            if old_path.exists():
                if new_path.exists():
                    # Merge leftovers from an earlier attempt
                    for item in old_path.iterdir():
                        shutil.move(str(item), str(new_path / item.name))
                    old_path.rmdir()
                else:
                    shutil.move(str(old_path), str(new_path))
            else:
                new_path.mkdir(parents=True, exist_ok=True)
            _update_env_data_path(str(new_path))
            state.data_path = str(new_path)

        # Save config through the SAME path the app state uses —
        # saving to a stray relative path is what made setup loop forever
        file_manager = FileManager(state.data_path)
        config = Config(
            company_prefix=prefix,
            company_name=company_name,
            website=website,
            git_link=git_link,
            data_path=state.data_path,
        )
        if not file_manager.save_config(config):
            flash('Failed to save configuration — check folder permissions', 'error')
            return render_template('setup.html')

        state.file_manager = file_manager
        state.config = config
        state.initialized = False  # force full re-init on the next request

        flash('Setup complete! Welcome to FabInventory.', 'success')
        return redirect(url_for('main.index'))

    return render_template('setup.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with overview"""
    if not state.init_app():
        return redirect(url_for('main.setup'))

    # Get statistics
    projects = state.project_manager.list_projects()
    inventory_summary = state.inventory_manager.get_inventory_summary()
    order_summary = state.inventory_manager.get_order_summary()

    # Get recent items to order
    items_to_order = state.inventory_manager.get_items_to_order()[:10]

    return render_template('dashboard.html',
                         projects=projects,
                         inventory_summary=inventory_summary,
                         order_summary=order_summary,
                         items_to_order=items_to_order)


@main_bp.route('/projects')
@login_required
def projects():
    """List all projects"""
    if not state.init_app():
        return redirect(url_for('main.setup'))

    projects = state.project_manager.list_projects()
    return render_template('projects.html', projects=projects)


@main_bp.route('/download-bom-template')
@login_required
def download_bom_template():
    # __file__ is src/routes/main.py → go up 2 levels to project root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, '..', '..', 'static', 'templates')

    return send_from_directory(
        directory=template_path,
        path='bom_template.xlsx',
        as_attachment=True
    )
