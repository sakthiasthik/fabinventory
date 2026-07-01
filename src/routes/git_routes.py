"""FabInventory — Git Settings Blueprint"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from src.core import state, login_required

git_bp = Blueprint('git', __name__)


@git_bp.route('/git-settings', methods=['GET', 'POST'])
def git_settings():
    """Git configuration and operations"""
    if not state.init_app():
        return redirect(url_for('main.setup'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'commit':
            message = request.form.get('message', 'Manual commit')
            if not state.git_manager.is_active():
                flash('Git is not available — no repository found.', 'warning')
            elif state.git_manager.commit(message):
                flash('Changes committed!', 'success')
            else:
                flash('No changes to commit, or commit failed.', 'warning')

        elif action == 'push':
            if not state.git_manager.is_active():
                flash('Git is not available.', 'warning')
            elif not state.git_manager.get_remote_urls():
                flash('No remote configured. Set up a remote URL first.', 'error')
            elif state.git_manager.push():
                flash('Pushed to remote!', 'success')
            else:
                flash('Push failed — check remote URL, authentication, and network.', 'error')

        elif action == 'pull':
            if not state.git_manager.is_active():
                flash('Git is not available.', 'warning')
            elif not state.git_manager.get_remote_urls():
                flash('No remote configured.', 'error')
            elif state.git_manager.pull():
                flash('Pulled from remote! Refreshing data...', 'success')
                state.project_manager._load_all_projects()
                projects = list(state.project_manager.projects.values())
                state.inventory_manager.update_inventory(projects)
                state.inventory_manager.update_non_elec_inventory(projects)
            else:
                flash('Pull failed — check remote URL and authentication.', 'error')

        elif action == 'setup_remote':
            remote_url = request.form.get('remote_url', '').strip()
            if not remote_url:
                flash('Please enter a remote URL.', 'error')
            elif state.git_manager.setup_remote(remote_url):
                flash(f'Remote configured: {remote_url}', 'success')
            else:
                flash('Failed to configure remote. Is GitPython installed?', 'error')

        elif action == 'set_user':
            user_name = request.form.get('git_user_name', '').strip()
            user_email = request.form.get('git_user_email', '').strip()
            if user_name and user_email:
                if state.git_manager.set_user(user_name, user_email):
                    flash(f'Git user set to: {user_name} <{user_email}>', 'success')
                else:
                    flash('Failed to set Git user.', 'error')
            else:
                flash('Name and email are required.', 'error')

    # Get current status
    status = state.git_manager.get_status()
    status['repo_path'] = str(state.git_manager.repo_path)
    commits = state.git_manager.get_commit_history(max_count=20)
    remote_urls = state.git_manager.get_remote_urls()
    current_branch = state.git_manager.get_current_branch()
    git_active = state.git_manager.is_active()
    git_user = state.git_manager.get_user()
    commits_ahead = state.git_manager.commits_ahead()

    return render_template(
        'git_settings.html',
        status=status,
        commits=commits,
        remote_urls=remote_urls,
        current_branch=current_branch,
        git_active=git_active,
        git_user=git_user,
        commits_ahead=commits_ahead,
    )
