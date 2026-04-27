"""FabInventory Web Application"""

import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
import json

# Fix imports - use correct class names
from src.file_manager import FileManager
from src.git_manager import GitManager
from src.project_manager import ProjectManager
from src.inventory_manager import InventoryManager
from src.aggregator import Aggregator
from src.bom_parser import BOMParser
from src.models import Config

# Create Flask app
app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'fabinventory-secret-key-change-this')
app.config['UPLOAD_FOLDER'] = Path('static/uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
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

# Routes
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
    return render_template('project_detail.html', project=project, summary=summary)

@app.route('/project/create', methods=['POST'])
def create_project():
    """Create a new project"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    
    try:
        project = state.project_manager.create_project(name, description)
        if project:
            # Refresh inventory
            projects = list(state.project_manager.projects.values())
            state.inventory_manager.update_inventory(projects)
            
            # Commit to Git
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
    
    import io
    import pandas as pd
    from flask import Response
    
    project = state.project_manager.get_project(name)
    if not project:
        flash(f'Project "{name}" not found', 'error')
        return redirect(url_for('projects'))
    
    # Create CSV
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
    
    internal_id = request.form.get('internal_id')
    new_stock = int(request.form.get('stock', 0))
    
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
    return render_template('orders.html', orders=all_orders)

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
        
        if not items:
            flash('No items selected for order', 'error')
            return redirect(url_for('create_order'))
        
        order = state.inventory_manager.create_order(supplier, items, notes)
        if order:
            if state.git_manager:
                state.git_manager.commit(f"Created order {order.order_id}")
            flash(f'Order {order.order_id} created successfully!', 'success')
            return redirect(url_for('orders'))
        else:
            flash('Failed to create order', 'error')
    
    # GET request - show form
    items_to_order = state.inventory_manager.get_items_to_order()
    return render_template('create_order.html', items_to_order=items_to_order)

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

# API endpoints
@app.route('/api/order/<order_id>')
def api_order_details(order_id):
    """API endpoint for order details"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
    
    order = state.inventory_manager.file_manager.load_order(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    return jsonify(order.dict())

@app.route('/api/orders')
def api_orders():
    """API endpoint for orders with filtering"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
    
    supplier = request.args.get('supplier')
    status_filter = request.args.get('status')
    
    orders = state.inventory_manager.file_manager.list_orders()
    
    if supplier:
        orders = [o for o in orders if o.supplier == supplier]
    if status_filter:
        orders = [o for o in orders if o.status == status_filter]
    
    return jsonify([o.dict() for o in orders])

@app.route('/api/inventory')
def api_inventory():
    """REST API endpoint for inventory"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
    
    inventory = state.inventory_manager.get_inventory()
    return jsonify([item.to_dict() for item in inventory])

@app.route('/api/projects')
def api_projects():
    """REST API endpoint for projects"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500
    
    projects = state.project_manager.list_projects()
    return jsonify(projects)

def main():
    """Run the Flask application"""
    # Ensure initialization on startup
    state.init_app()
    
    # Run app
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main()