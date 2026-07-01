"""FabInventory — API Blueprint"""
from flask import Blueprint, jsonify, request
from src.core import state, api_login_required

api_bp = Blueprint('api', __name__)


@api_bp.route('/order/<order_id>')
@api_login_required
def api_order_details(order_id):
    """API endpoint for order details"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500

    order = state.inventory_manager.file_manager.load_order(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404

    return jsonify(order.__dict__)


@api_bp.route('/project/<project_name>/components')
@api_login_required
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


@api_bp.route('/create-order', methods=['POST'])
@api_login_required
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


@api_bp.route('/projects-list')
@api_login_required
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


@api_bp.route('/orders')
@api_login_required
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


@api_bp.route('/projects')
@api_login_required
def api_projects():
    """REST API endpoint for projects"""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500

    projects = state.project_manager.list_projects()
    return jsonify(projects)


@api_bp.route('/inventory/add', methods=['POST'])
@api_login_required
def add_inventory_component():
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    data = request.json
    from src.models import MasterItem

    prefix = state.config.company_prefix.upper()
    next_id = state.file_manager.get_next_id()
    internal_id = f"{prefix}-ELE-{next_id:05d}"

    item = MasterItem(
        internal_id=internal_id,
        value=data.get('value', ''),
        footprint=data.get('footprint', ''),
        total_required=0,
        current_stock=int(data.get('current_stock', 0)),
        used_in_projects=[],
        associated_mpns=[data.get('mpn', '')] if data.get('mpn') else [],
    )

    state.inventory_manager.inventory.append(item)
    state.inventory_manager.file_manager.save_master_inventory(
        state.inventory_manager.inventory
    )

    if state.git_manager:
        state.git_manager.commit(f"Added inventory component {item.value}")

    return jsonify({'success': True})
