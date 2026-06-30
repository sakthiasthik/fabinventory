"""FabInventory Web Application"""
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from flask import send_from_directory

# Load .env before anything else
load_dotenv()
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory, Response, session
from werkzeug.utils import secure_filename
from functools import wraps
import json
import io
import requests
import pandas as pd

# Fix imports - use correct class names
from src.file_manager import FileManager
from src.git_manager import GitManager
from src.project_manager import ProjectManager
from src.inventory_manager import InventoryManager
from src.aggregator import Aggregator
from src.bom_parser import BOMParser
from src.models import Config
import zipfile
from flask_wtf.csrf import CSRFProtect

# Create Flask app
app = Flask(
    __name__,
    static_folder='../static',
    template_folder='../templates'
)


secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is required.\n"
        "Copy .env.example to .env and set a secure random key, or:\n"
        "  export SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    )
app.secret_key = secret_key
app.config['UPLOAD_FOLDER'] = Path('static/uploads')

# Enable CSRF protection for all POST routes
csrf = CSRFProtect(app)

# Load admin password for local authentication
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'fabinventory')

# GitHub OAuth configuration (optional — only if env vars are set)
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')
GITHUB_OAUTH_ENABLED = bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET)


def login_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Exempt API routes from login redirect (they return JSON instead)
def api_login_required(f):
    """Decorator for API routes — returns JSON error instead of redirect."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB limit
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
app.template_folder = template_dir
# Ensure upload folder exists
app.config['UPLOAD_FOLDER'].mkdir(parents=True, exist_ok=True)

# Global application state
class AppState:
    def __init__(self):
        self.repo_path = os.environ.get('REPO_PATH', './fabinventory_data')
        self.file_manager = None
        self.git_manager = None
        self.project_manager = None
        self.inventory_manager = None
        self.aggregator = None
        self.config = None
        self.initialized = False
    
    def init_app(self):
        """Initialize all managers"""
        if not self.initialized:
            self.file_manager = FileManager(self.repo_path)
            self.config = self.file_manager.load_config()
            
            # If no config, we need to set up first
            if not self.config:
                return False
            
            self.git_manager = GitManager(self.repo_path)
            self.aggregator = Aggregator(self.config.company_prefix)
            
            # Get next ID from file manager
            next_id = self.file_manager.get_next_id()
            self.aggregator.set_next_id(next_id)
            
            self.project_manager = ProjectManager(self.file_manager)
            self.inventory_manager = InventoryManager(self.file_manager, self.aggregator)
            
            # Load inventory
            projects = list(self.project_manager.projects.values())
            self.inventory_manager.update_inventory(projects)
            
            self.initialized = True
        return True

state = AppState()

# Public endpoints that don't require authentication
_PUBLIC_ENDPOINTS = {'login', 'login_github', 'login_github_callback', 'setup', 'static'}


@app.before_request
def _require_auth():
    """Require authentication for all pages except public endpoints."""
    if request.endpoint and request.endpoint not in _PUBLIC_ENDPOINTS:
        if not session.get('authenticated'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))


# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['authenticated'] = True
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid password', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout"""
    session.pop('authenticated', None)
    flash('Logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/login/github')
def login_github():
    """Redirect to GitHub for OAuth authorization."""
    if not GITHUB_OAUTH_ENABLED:
        flash('GitHub login is not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env', 'error')
        return redirect(url_for('login'))
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={url_for('login_github_callback', _external=True)}"
        f"&scope=repo,user"
    )
    return redirect(github_auth_url)


@app.route('/login/github/callback')
def login_github_callback():
    """Handle GitHub OAuth callback — exchange code for access token."""
    if not GITHUB_OAUTH_ENABLED:
        flash('GitHub login is not configured.', 'error')
        return redirect(url_for('login'))

    code = request.args.get('code')
    if not code:
        flash('GitHub authorization failed.', 'error')
        return redirect(url_for('login'))

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
            return redirect(url_for('login'))
    except requests.RequestException as e:
        flash(f'Could not reach GitHub: {e}', 'error')
        return redirect(url_for('login'))

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
    return redirect(url_for('dashboard'))


@app.route('/')
def index():
    """Home page - redirect to dashboard or setup"""
    if not state.init_app():
        return redirect(url_for('setup'))
    return redirect(url_for('dashboard'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Initial setup - configure company prefix"""
    if request.method == 'POST':
        company_prefix = request.form.get('company_prefix', '').upper()
        repo_path = request.form.get('repo_path', './fabinventory_data')
        
        if len(company_prefix) != 2:
            flash('Company prefix must be exactly 2 letters', 'error')
            return render_template('setup.html')
        
        # Save config
        config = Config(company_prefix=company_prefix, repo_path=repo_path)
        file_manager = FileManager(repo_path)
        file_manager.save_config(config)
        
        flash('Setup complete! You can now start using FabInventory.', 'success')
        return redirect(url_for('index'))
    
    return render_template('setup.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard with overview"""
    if not state.init_app():
        return redirect(url_for('setup'))
    
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

@app.route('/projects')
def projects():
    """List all projects"""
    if not state.init_app():
        return redirect(url_for('setup'))
    
    projects = state.project_manager.list_projects()
    return render_template('projects.html', projects=projects)

@app.route('/project/<name>')
def project_detail(name):
    """View project details"""
    if not state.init_app():
        return redirect(url_for('setup'))
    
    project = state.project_manager.get_project(name)
    if not project:
        flash(f'Project "{name}" not found', 'error')
        return redirect(url_for('projects'))
    
    summary = state.project_manager.get_project_summary(name)
    print3d_rows = []
    mechanical_rows = []
    pcb_rows = []

    if hasattr(project, 'print3d_bom') and project.print3d_bom:

        try:

            print3d_rows = BOMParser.parse_file(
                project.print3d_bom,
                bom_type="3dprint"
            )

            print("3D ROWS:", print3d_rows)

        except Exception as e:

            print("3D BOM ERROR:", e)

    if hasattr(project, 'mechanical_bom') and project.mechanical_bom:

        try:

            mechanical_rows = BOMParser.parse_file(
                project.mechanical_bom,
                bom_type="mechanical"
            )

            print("MECHANICAL ROWS:", mechanical_rows)

        except Exception as e:

            print("MECHANICAL BOM ERROR:", e)

    if hasattr(project, 'pcb_bom') and project.pcb_bom:

        try:

            pcb_rows = BOMParser.parse_file(
                project.pcb_bom,
                bom_type="pcb"
            )

            print("PCB ROWS:", pcb_rows)

        except Exception as e:

            print("PCB BOM ERROR:", e)

    return render_template(
        'project_details.html',
        project=project,
        summary=summary,
        print3d_rows=print3d_rows,
        mechanical_rows=mechanical_rows,
        pcb_rows=pcb_rows
    )


@app.route('/project/create', methods=['POST'])
def create_project():
    """Create a new project"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    name = request.form.get('name')
    description = request.form.get('description', '')

    try:
        # Step 1: Create project
        project = state.project_manager.create_project(name, description)

        if project:
            # Step 2: Handle BOM upload (optional)
            bom_file = request.files.get('bom_file')

            if bom_file and bom_file.filename != "":
                filename = secure_filename(bom_file.filename)
                filepath = app.config['UPLOAD_FOLDER'] / filename
                bom_file.save(filepath)

                try:
                    # Use your existing parser system ✅
                    state.project_manager.update_project_bom(name, str(filepath))
                except Exception as e:
                    flash(f'Error parsing BOM: {str(e)}', 'error')
                finally:
                    # Clean temp file
                    if filepath.exists():
                        filepath.unlink()

            # Step 3: Refresh inventory
            projects = list(state.project_manager.projects.values())
            state.inventory_manager.update_inventory(projects)

            # Step 4: Git commit
            if state.git_manager:
                state.git_manager.commit(f"Created project '{name}'")

            flash(f'Project "{name}" created successfully!', 'success')

        else:
            flash(f'Failed to create project "{name}"', 'error')

    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('projects'))

@app.route('/project/<name>/upload', methods=['POST'])
def upload_bom(name):
    """Upload BOM file to project"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500
    
    if 'bom_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('project_detail', name=name))
    
    file = request.files['bom_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('project_detail', name=name))
    
    if file:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = app.config['UPLOAD_FOLDER'] / filename
        file.save(filepath)
        
        try:
            # Parse and update BOM
            updated = state.project_manager.update_project_bom(name, str(filepath))
            if updated:
                # Refresh inventory
                projects = list(state.project_manager.projects.values())
                state.inventory_manager.update_inventory(projects)
                
                # Commit to Git
                if state.git_manager:
                    state.git_manager.commit(f"Updated BOM for project '{name}'")
                
                flash(f'BOM uploaded successfully to "{name}"!', 'success')
            else:
                flash(f'Failed to upload BOM to "{name}"', 'error')
        except Exception as e:
            flash(f'Error parsing BOM: {str(e)}', 'error')
        finally:
            # Clean up uploaded file
            if filepath.exists():
                filepath.unlink()
    
    return redirect(url_for('project_detail', name=name))
@app.route('/project/<name>/upload-image', methods=['POST'])
def upload_project_image(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")
        return redirect(url_for('projects'))

    if 'project_image' not in request.files:
        flash("No image uploaded", "danger")
        return redirect(url_for('project_detail', name=name))

    file = request.files['project_image']

    if file.filename == '':
        flash("No selected image", "danger")
        return redirect(url_for('project_detail', name=name))

    # SAVE TO PROJECT FOLDER
    filename = secure_filename(file.filename)
    saved = state.project_manager.file_manager.save_project_file(
        name, 'images', filename, file.read()
    )

    # SAVE IMAGE NAME INTO PROJECT
    project.image = filename

    # SAVE PROJECT METADATA
    state.project_manager.file_manager.save_project(project)

    flash("Project image uploaded successfully!", "success")

    return redirect(url_for('project_detail', name=name))


@app.route('/project/<name>/delete', methods=['POST'])
def delete_project(name):
    """Delete a project"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500
    
    if state.project_manager.delete_project(name):
        # Refresh inventory
        projects = list(state.project_manager.projects.values())
        state.inventory_manager.update_inventory(projects)
        
        # Commit to Git
        if state.git_manager:
            state.git_manager.commit(f"Deleted project '{name}'")
        
        flash(f'Project "{name}" deleted!', 'success')
    else:
        flash(f'Failed to delete project "{name}"', 'error')
    
    return redirect(url_for('projects'))

@app.route('/project/<name>/export')
def export_bom(name):
    """Export project BOM as CSV"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    project = state.project_manager.get_project(name)
    if not project:
        flash(f'Project "{name}" not found', 'error')
        return redirect(url_for('projects'))

    # Build CSV from project BOM
    data = []
    for row in project.bom:
        data.append({
            'SI.No': row.si_no,
            'Reference': row.reference,
            'Value': row.value,
            'Footprint': row.footprint,
            'Manufacturer_Part_Number': row.manufacturer_part_number,
            'Manufacturer_Name': row.manufacturer_name,
            'Qty': row.qty,
            'DNP': 'X' if row.dnp else ''
        })

    df = pd.DataFrame(data)
    output = io.StringIO()
    df.to_csv(output, index=False)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={name}_bom.csv'}
    )


@app.route('/download-bom-template')
def download_bom_template():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, '..', 'static', 'templates')

    print("Looking in:", template_path)

    return send_from_directory(
        directory=template_path,
        path='bom_template.xlsx',
        as_attachment=True
    )

@app.route('/inventory')
def inventory():
    """View master inventory"""
    if not state.init_app():
        return redirect(url_for('setup'))
    
    inventory = state.inventory_manager.get_inventory()
    return render_template('inventory.html', inventory=inventory)

@app.route('/inventory/update-stock', methods=['POST'])
def update_stock():
    """Update stock for an item"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    internal_id = request.form.get('internal_id', '').strip()

    # Validate stock value
    try:
        new_stock = int(request.form.get('stock', 0))
        if new_stock < 0:
            flash('Stock cannot be negative', 'error')
            return redirect(url_for('inventory'))
    except (ValueError, TypeError):
        flash('Invalid stock value', 'error')
        return redirect(url_for('inventory'))

    # Verify the item exists before updating
    item = state.inventory_manager.find_item(internal_id)
    if not item:
        flash(f'Item "{internal_id}" not found in inventory', 'error')
        return redirect(url_for('inventory'))

    updated = state.inventory_manager.update_stock(internal_id, new_stock)
    if updated:
        if state.git_manager:
            state.git_manager.commit(f"Updated stock for {internal_id} to {new_stock}")
        flash(f'Stock updated for {internal_id}!', 'success')
    else:
        flash(f'Failed to update stock for {internal_id}', 'error')

    return redirect(url_for('inventory'))

@app.route('/orders')
def orders():
    """View all orders"""
    if not state.init_app():
        return redirect(url_for('setup'))
   
    all_orders = state.inventory_manager.file_manager.list_orders()
   
    # Convert orders to dict for template (if they're objects)
    orders_data = []
    for order in all_orders:
        order_dict = {
            'order_id': order.order_id,
            'supplier': order.supplier,
            'status': order.status,
            'line_items': [{'internal_id': item.internal_id, 'qty_ordered': item.qty_ordered} for item in order.line_items],
            'total_items': order.total_items,
            'created_at': order.created_at,
            'received_at': order.received_at,
            'notes': order.notes
        }
        orders_data.append(order_dict)
   
    # Get list of projects for the dropdown
    projects_list = state.project_manager.list_projects()
   
    return render_template('orders.html', orders=orders_data, projects=projects_list)
 
@app.route('/order/create', methods=['GET', 'POST'])
def create_order():
    """Create a new purchase order"""
    if not state.init_app():
        return redirect(url_for('setup'))
   
    if request.method == 'POST':
        supplier = request.form.get('supplier')
        notes = request.form.get('notes', '')
       
        # Get selected items
        items = []
        for key, value in request.form.items():
            if key.startswith('qty_'):
                internal_id = key[4:]
                qty = int(value) if value else 0
                if qty > 0:
                    items.append({
                        'internal_id': internal_id,
                        'qty': qty
                    })
        print("FORM DATA:", request.form)
       
        if not items:
            flash('No items selected for order', 'error')
            return redirect(url_for('create_order'))
       
        order = state.inventory_manager.create_order(supplier, items, notes)
        print("ORDER OBJECT:", order)
        if order:
            print("ORDER DATA:", order.__dict__)
            if state.git_manager:
                state.git_manager.commit(f"Created order {order.order_id}")
            flash(f'Order {order.order_id} created successfully!', 'success')
            return redirect(url_for('orders'))
        else:
            print("ORDER CREATION FAILED ❌")
            flash('Failed to create order', 'error')
   
    # GET request - show form

    items_to_order = state.inventory_manager.get_items_to_order()

    projects_list = state.project_manager.list_projects()

    return render_template(

        'create_order.html',

        items_to_order=items_to_order,

        projects=projects_list
    )
 
@app.route('/order/<order_id>/receive', methods=['POST'])
def receive_order(order_id):
    """Mark order as received"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500
   
    if state.inventory_manager.receive_order(order_id):
        if state.git_manager:
            state.git_manager.commit(f"Received order {order_id}")
        flash(f'Order {order_id} marked as received!', 'success')
    else:
        flash(f'Failed to receive order {order_id}', 'error')
   
    return redirect(url_for('orders'))
 
@app.route('/order-summary')
def order_summary():
    """View order summary"""
    if not state.init_app():
        return redirect(url_for('setup'))
   
    summary = state.inventory_manager.get_order_summary()
    return render_template('order_summary.html', summary=summary)
 
@app.route('/git-settings', methods=['GET', 'POST'])
def git_settings():
    """Git configuration and operations"""
    if not state.init_app():
        return redirect(url_for('setup'))
   
    if request.method == 'POST':
        action = request.form.get('action')
       
        if action == 'commit':
            message = request.form.get('message', 'Manual commit')
            if state.git_manager.commit(message):
                flash('Changes committed!', 'success')
            else:
                flash('No changes to commit', 'warning')
       
        elif action == 'push':
            if state.git_manager.push():
                flash('Pushed to remote!', 'success')
            else:
                flash('Push failed. Check remote configuration.', 'error')
       
        elif action == 'pull':
            if state.git_manager.pull():
                flash('Pulled from remote! Refreshing data...', 'success')
                # Reload data
                state.project_manager._load_all_projects()
                projects = list(state.project_manager.projects.values())
                state.inventory_manager.update_inventory(projects)
            else:
                flash('Pull failed. Check remote configuration.', 'error')
       
        elif action == 'setup_remote':
            remote_url = request.form.get('remote_url')
            if state.git_manager.setup_remote(remote_url):
                flash(f'Remote configured: {remote_url}', 'success')
            else:
                flash('Failed to configure remote', 'error')
   
    # Get current status
    status = state.git_manager.get_status()
    status['repo_path'] = state.repo_path
    commits = state.git_manager.get_commit_history(max_count=20)
    remotes = [remote.name for remote in state.git_manager.repo.remotes] if state.git_manager.repo else []
   
    return render_template('git_settings.html',
                         status=status,
                         commits=commits,
                         remotes=remotes)
 
@app.context_processor
def inject_git_status():
    if state.initialized and state.git_manager:
        return {'git_status': state.git_manager.get_status()}
    return {'git_status': None}
 
 
# API endpoints
@app.route('/api/order/<order_id>')
def api_order_details(order_id):
    """API endpoint for order details"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
   
    order = state.inventory_manager.file_manager.load_order(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
   
    return jsonify(order.__dict__)
# Add these new API endpoints after your existing API endpoints
 
@app.route('/api/project/<project_name>/components')
def api_project_components(project_name):
    """API endpoint to get components for a specific project"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
   
    # Get the project
    project = state.project_manager.get_project(project_name)
    if not project:
        return jsonify({'error': 'Project not found'}), 404
   
    # Get inventory data to calculate stock levels
    inventory_items = state.inventory_manager.get_inventory()
   
    # Create a lookup dict for stock levels
    stock_lookup = {}
    for item in inventory_items:
        key = f"{item.value}|{item.footprint}"
        stock_lookup[key] = {
            'current_stock': item.current_stock,
            'total_required': item.total_required,
            'internal_id': item.internal_id
        }
   
    # Build components list
    components = []
    for bom_row in project.bom:
        if not bom_row.is_active():  # Skip DNP components
            continue
           
        key = f"{bom_row.value}|{bom_row.footprint}"
        stock_info = stock_lookup.get(key, {'current_stock': 0, 'total_required': 0, 'internal_id': None})
       
        # Use ONLY project BOM quantity
        project_qty = bom_row.qty

        to_order = max(
            0,
            project_qty - stock_info.get('current_stock', 0)
        )

        components.append({
            'id': key,
            'internal_id': stock_info.get(
                'internal_id',
                f"TEMP-{len(components)+1}"
            ),
            'value': bom_row.value,
            'footprint': bom_row.footprint,
            'mpn': bom_row.manufacturer_part_number,
            'manufacturer_part_number': bom_row.manufacturer_part_number,
            'manufacturer_name': bom_row.manufacturer_name,
            'qty': bom_row.qty,
            'dnp': bom_row.dnp,
            'dnp_raw': bom_row.dnp_raw,

            # IMPORTANT FIX
            'total_required': project_qty,

            'current_stock': stock_info.get(
                'current_stock',
                0
            ),

            'to_order': to_order,
            'reference': bom_row.reference
        })
   
    return jsonify({
        'project_name': project_name,
        'components': components,
        'total_components': len(components)
    })
 
@app.route('/api/create-order', methods=['POST'])
def api_create_order():
    """API endpoint to create an order from selected components"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
   
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
   
    supplier = data.get('supplier')
    project_name = data.get('project_name')
    items_data = data.get('items', [])
    notes = data.get('notes', '')
   
    if not supplier:
        return jsonify({'error': 'Supplier is required'}), 400
   
    if not items_data:
        return jsonify({'error': 'No items selected'}), 400
   
    # Convert items to the format expected by inventory_manager
    items = []
    for item in items_data:
        # Find the actual internal_id from inventory
        internal_id = item.get('id') or item.get('internal_id')
        qty = item.get('qty', 0)
       
        if qty > 0:
            items.append({
                'internal_id': internal_id,
                'qty': qty
            })
   
    if not items:
        return jsonify({'error': 'No valid items with quantity > 0'}), 400
   
    # Create the order
    order = state.inventory_manager.create_order(supplier, items, notes)
   
    if order:
        if state.git_manager:
            state.git_manager.commit(f"Created order {order.order_id} for project '{project_name}'")
       
        return jsonify({
            'success': True,
            'order_id': order.order_id,
            'message': f'Order {order.order_id} created successfully'
        })
    else:
        return jsonify({'error': 'Failed to create order'}), 500
 
@app.route('/api/projects-list')
def api_projects_list():
    """API endpoint to get list of all projects with their component counts"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
   
    projects = state.project_manager.list_projects()
   
    # Get component counts for each project
    projects_with_counts = []
    for project in projects:
        proj_obj = state.project_manager.get_project(project['name'])
        component_count = len([row for row in proj_obj.bom if row.is_active()]) if proj_obj else 0
        projects_with_counts.append({
            'name': project['name'],
            'description': project.get('description', ''),
            'component_count': component_count,
            'total_quantity': project.get('total_quantity', 0),
            'updated_at': project.get('updated_at', '')
        })
   
    return jsonify(projects_with_counts)
@app.route('/api/orders')
def api_orders():
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
   
    supplier = request.args.get('supplier')
    status_filter = request.args.get('status')
   
    orders = state.inventory_manager.file_manager.list_orders()
   
    if supplier:
        orders = [o for o in orders if o.supplier == supplier]
    if status_filter:
        orders = [o for o in orders if o.status == status_filter]
   
    return jsonify([o.to_dict() for o in orders])

@app.route('/api/projects')
def api_projects():
    """REST API endpoint for projects"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
    
    projects = state.project_manager.list_projects()
    return jsonify(projects)

@app.route('/project/<name>/upload_3d_bom', methods=['POST'])
def upload_3d_bom(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('projects'))

    file = request.files.get('print3d_file')

    if not file or file.filename == '':
        flash('No file selected', 'warning')
        return redirect(
            url_for(
                'project_detail',
                name=name,
                tab='3dprint'
            )
        )

    filename = secure_filename(file.filename)

    saved_path = state.project_manager.file_manager.save_project_file(
        name, '3dprint', filename, file.read()
    )

    # SAVE RELATIVE PATH IN PROJECT (from project dir)
    project.print3d_bom = f"3dprint/{filename}"

    state.project_manager.file_manager.save_project(project)
    state.project_manager.projects[name] = project

    flash('3D BOM uploaded successfully', 'success')

    return redirect(url_for('project_detail', name=name, tab='3dprint'))

@app.route('/project/<name>/upload_mechanical_bom', methods=['POST'])
def upload_mechanical_bom(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('projects'))

    file = request.files.get('mechanical_file')

    if not file or file.filename == '':
        flash('No file selected', 'warning')
        return redirect(
            url_for(
                'project_detail',
                name=name,
                tab='mechanical'
            )
        )

    filename = secure_filename(file.filename)

    saved_path = state.project_manager.file_manager.save_project_file(
        name, 'mechanical', filename, file.read()
    )

    project.mechanical_bom = f"mechanical/{filename}"

    state.project_manager.file_manager.save_project(project)
    state.project_manager.projects[name] = project

    flash('Mechanical BOM uploaded successfully', 'success')

    return redirect(url_for('project_detail', name=name, tab='mechanical'))

@app.route('/project/<name>/upload_pcb_bom', methods=['POST'])
def upload_pcb_bom(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('projects'))

    file = request.files.get('pcb_file')

    if not file or file.filename == '':
        flash('No file selected', 'warning')
        return redirect(
            url_for(
                'project_detail',
                name=name,
                tab='pcb'
            )
        )

    filename = secure_filename(file.filename)

    saved_path = state.project_manager.file_manager.save_project_file(
        name, 'pcb', filename, file.read()
    )

    project.pcb_bom = f"pcb/{filename}"

    state.project_manager.file_manager.save_project(project)
    state.project_manager.projects[name] = project

    flash('PCB BOM uploaded successfully', 'success')

    return redirect(url_for('project_detail', name=name, tab='pcb'))

@app.route('/project/<name>/upload_3d_image', methods=['POST'])
def upload_3d_image(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash('Project not found', 'danger')
        return redirect(url_for('projects'))

    file = request.files.get('model_3d_file')

    if not file or file.filename == '':
        flash('No image selected', 'warning')

        return redirect(
            url_for(
                'project_detail',
                name=name,
                tab='3dprint'
            )
        )

    filename = secure_filename(file.filename)

    saved_path = state.project_manager.file_manager.save_project_file(
        name, '3d_models', filename, file.read()
    )

    project.model_3d_file = f"3d_models/{filename}"

    state.project_manager.file_manager.save_project(project)
    state.project_manager.projects[name] = project

    flash('3D preview uploaded successfully', 'success')

    return redirect(url_for('project_detail', name=name, tab='3dprint'))

@app.route("/project/<name>/upload_gerber_zip", methods=["POST"])
def upload_gerber_zip(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")
        return redirect(url_for("dashboard"))

    if "gerber_zip" not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for("project_detail", name=name, tab="pcb"))

    file = request.files["gerber_zip"]

    if file.filename == "":
        flash("No file selected", "danger")
        return redirect(url_for("project_detail", name=name, tab="pcb"))

    filename = secure_filename(file.filename)

    # SAVE INSIDE PROJECT FOLDER
    state.project_manager.file_manager.save_project_file(
        name,
        "gerbers",
        filename,
        file.read()
    )

    # SAVE RELATIVE PATH
    project.pcb_gerber_zip = f"gerbers/{filename}"

    project.updated_at = datetime.now().isoformat()

    state.project_manager.file_manager.save_project(project)

    flash("Gerber ZIP uploaded successfully", "success")

    return redirect(url_for("project_detail", name=name, tab="pcb"))

@app.route('/project/<name>/download_gerber')
def download_gerber(name):

    import os
    from flask import send_from_directory

    project = state.file_manager.load_project(name)

    if not project or not project.pcb_gerber_zip:
        abort(404)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    project_dir = os.path.join(
        base_dir,
        "fabinventory_data",
        "projects",
        name
    )

    gerber_relative_path = project.pcb_gerber_zip

    gerber_folder = os.path.dirname(
        os.path.join(project_dir, gerber_relative_path)
    )

    gerber_filename = os.path.basename(gerber_relative_path)

    return send_from_directory(
        directory=gerber_folder,
        path=gerber_filename,
        as_attachment=True,
        download_name=gerber_filename
    )

@app.route(
    "/project/<name>/save_pcb_repo",
    methods=["POST"]
)
def save_pcb_repo(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")

        return redirect(url_for("projects"))

    repo_name = request.form.get(
        "pcb_repo_name",
        ""
    ).strip()

    repo_link = request.form.get(
        "pcb_repo_link",
        ""
    ).strip()

    # ======================================
    # APPEND NEW REPO
    # ======================================

    if repo_name and repo_link:

        project.github_links.append({

            "name": repo_name,

            "url": repo_link

        })

    # ======================================
    # SAVE PROJECT
    # ======================================

    state.project_manager.file_manager.save_project(project)

    state.project_manager.projects[name] = project

    flash(
        "PCB repository link saved",
        "success"
    )

    return redirect(
        url_for(
            "project_detail",
            name=name,
            tab="pcb"
        )
    )

@app.route(
    '/api/inventory/add',
    methods=['POST']
)
def add_inventory_component():

    if not state.init_app():
        return jsonify({
            'error': 'App not initialized'
        }), 500

    data = request.json

    from src.models import MasterItem

    inventory = state.inventory_manager.inventory

    internal_id = f"SA-ELE-{len(inventory)+1:05d}"

    item = MasterItem(

        internal_id=internal_id,

        value=data.get(
            'value',
            ''
        ),

        footprint=data.get(
            'footprint',
            ''
        ),

        total_required=0,

        current_stock=int(
            data.get(
                'current_stock',
                0
            )
        ),

        used_in_projects=[],

        associated_mpns=[
            data.get('mpn', '')
        ] if data.get('mpn') else []
    )

    # ADD ITEM
    inventory.append(item)

    # SAVE USING EXISTING INVENTORY MANAGER FLOW
    state.inventory_manager.inventory = inventory

    # OPTIONAL GIT COMMIT
    if state.git_manager:
        state.git_manager.commit(
            f"Added inventory component {item.value}"
        )

    return jsonify({
        'success': True
    })

@app.route("/project/<name>/upload_pcb_image", methods=["POST"])
def upload_pcb_image(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")
        return redirect(url_for("dashboard"))

    if "pcb_image" not in request.files:
        flash("No file uploaded", "danger")
        return redirect(url_for("project_detail", name=name, tab="pcb"))

    file = request.files["pcb_image"]

    if file.filename == "":
        flash("No file selected", "danger")
        return redirect(url_for("project_detail", name=name, tab="pcb"))

    filename = secure_filename(file.filename)

    # SAVE INSIDE PROJECT FOLDER
    state.project_manager.file_manager.save_project_file(
        name,
        "pcb_images",
        filename,
        file.read()
    )

    # SAVE RELATIVE PATH
    project.pcb_image = f"pcb_images/{filename}"

    project.updated_at = datetime.now().isoformat()

    state.project_manager.file_manager.save_project(project)

    flash("PCB image uploaded successfully", "success")

    return redirect(url_for("project_detail", name=name, tab="pcb"))

@app.route("/project/<name>/pcb_image/<filename>")
def serve_pcb_image(name, filename):

    project_dir = state.project_manager.file_manager._project_dir(name)

    image_dir = os.path.join(
        project_dir,
        "pcb_images"
    )

    return send_from_directory(
        image_dir,
        filename
    )

@app.route(
    '/project/<name>/remove_pcb_image',
    methods=['POST']
)
def remove_pcb_image(name):

    project = state.project_manager.get_project(name)

    if not project:
        flash("Project not found", "danger")
        return redirect(url_for('projects'))

    if project.pcb_image:

        project_dir = state.project_manager.file_manager._project_dir(name)

        image_path = os.path.join(
            project_dir,
            project.pcb_image
        )

        if os.path.exists(image_path):
            os.remove(image_path)

    project.pcb_image = None

    state.file_manager.save_project(project)

    flash("PCB image removed", "success")

    return redirect(
        url_for(
            'project_detail',
            name=name,
            tab='pcb'
        )
    )

@app.route('/project/<name>/files/<path:filepath>')
def serve_project_file(name, filepath):

    from flask import send_from_directory
    import os

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    project_dir = os.path.join(
        base_dir,
        "fabinventory_data",
        "projects",
        name
    )

    print("PROJECT DIR:", project_dir)
    print("FILEPATH:", filepath)

    return send_from_directory(project_dir, filepath)

def main():
    """Run the Flask application"""
    # Ensure initialization on startup
    state.init_app()
    
    # Run app
    app.run(debug=True, host='0.0.0.0', port=9000)

if __name__ == '__main__':
    main()