"""Main Flask Blueprint — auth routes and core pages."""
import os
import requests

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
from src.models import Config

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


@main_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Initial setup - configure company prefix"""
    if request.method == 'POST':
        company_prefix = request.form.get('company_prefix', '').upper()
        data_path = request.form.get('data_path', './fabinventory_data')

        if len(company_prefix) != 2:
            flash('Company prefix must be exactly 2 letters', 'error')
            return render_template('setup.html')

        # Save config
        config = Config(company_prefix=company_prefix, data_path=data_path)
        file_manager = FileManager(data_path)
        file_manager.save_config(config)

        flash('Setup complete! You can now start using FabInventory.', 'success')
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
