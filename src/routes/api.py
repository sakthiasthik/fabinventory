"""FabInventory — API Blueprint"""
from pathlib import Path
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
    """API endpoint to get ALL components (elec, mech, pcb, 3d) for a project."""
    if not state.init_app():
        return jsonify({'error': 'Not initialized'}), 500

    project = state.project_manager.get_project(project_name)
    if not project:
        return jsonify({'error': 'Project not found'}), 404

    data_root = Path(state.data_path) / "projects" / project_name
    components = []
    seen_ids = set()

    # ── Electrical ──────────────────────────────────────────────
    inventory_items = state.inventory_manager.get_inventory()
    stock_lookup = {}
    for item in inventory_items:
        key = f"{item.value}|{item.footprint}"
        stock_lookup[key] = {
            'current_stock': item.current_stock,
            'internal_id': item.internal_id,
        }

    for bom_row in project.bom:
        if not bom_row.is_active():
            continue
        key = f"{bom_row.value}|{bom_row.footprint}"
        stock_info = stock_lookup.get(key, {'current_stock': 0, 'internal_id': None})
        cid = stock_info.get('internal_id') or key
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        components.append({
            'id': cid,
            'internal_id': stock_info.get('internal_id') or '',
            'category': 'electrical',
            'label': f"{bom_row.value} — {bom_row.footprint}",
            'value': bom_row.value,
            'footprint': bom_row.footprint,
            'mpn': bom_row.manufacturer_part_number,
            'qty': bom_row.qty,
            'to_order': max(0, bom_row.qty - stock_info.get('current_stock', 0)),
            'current_stock': stock_info.get('current_stock', 0),
            'reference': bom_row.reference,
        })

    # ── Mechanical ──────────────────────────────────────────────
    if project.mechanical_bom:
        from src.bom_parser import BOMParser
        mech_path = data_root / project.mechanical_bom
        if mech_path.exists():
            try:
                for row in BOMParser.parse_file(str(mech_path), bom_type='mechanical'):
                    cid = f"mech-{row.get('part_name','')}|{row.get('value','')}"
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    qty = int(row.get('quantity', 0))
                    mech_inv = state.inventory_manager.mech_inventory
                    stock = 0
                    int_id = ''
                    for mi in mech_inv:
                        if mi.get_aggregation_key() == f"{row.get('part_name','')}|{row.get('value','')}":
                            stock = mi.current_stock
                            int_id = mi.internal_id
                            break
                    components.append({
                        'id': cid,
                        'internal_id': int_id,
                        'category': 'mechanical',
                        'label': f"{row.get('part_name','')} — {row.get('value','')}",
                        'part_name': row.get('part_name', ''),
                        'value': row.get('value', ''),
                        'qty': qty,
                        'to_order': max(0, qty - stock),
                        'current_stock': stock,
                        'reference': '',
                    })
            except Exception as e:
                print(f"Mech parse error: {e}")

    # ── PCB ────────────────────────────────────────────────────
    if project.pcb_bom:
        from src.bom_parser import BOMParser
        pcb_path = data_root / project.pcb_bom
        if pcb_path.exists():
            try:
                for row in BOMParser.parse_file(str(pcb_path), bom_type='pcb'):
                    cid = f"pcb-{row.get('board_name','')}"
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    qty = int(row.get('quantity', 0))
                    pcb_inv = state.inventory_manager.pcb_inventory
                    stock = 0
                    int_id = ''
                    for pi in pcb_inv:
                        if pi.board_name == row.get('board_name', ''):
                            stock = pi.current_stock
                            int_id = pi.internal_id
                            break
                    components.append({
                        'id': cid,
                        'internal_id': int_id,
                        'category': 'pcb',
                        'label': f"PCB: {row.get('board_name','')}",
                        'board_name': row.get('board_name', ''),
                        'qty': qty,
                        'to_order': max(0, qty - stock),
                        'current_stock': stock,
                        'reference': '',
                    })
            except Exception as e:
                print(f"PCB parse error: {e}")

    # ── 3D Print ───────────────────────────────────────────────
    if project.print3d_bom:
        from src.bom_parser import BOMParser
        prn_path = data_root / project.print3d_bom
        if prn_path.exists():
            try:
                for row in BOMParser.parse_file(str(prn_path), bom_type='3dprint'):
                    cid = f"3d-{row.get('part_name','')}"
                    if cid in seen_ids:
                        continue
                    seen_ids.add(cid)
                    qty = int(row.get('quantity', 0))
                    prn_inv = state.inventory_manager.print3d_inventory
                    stock = 0
                    int_id = ''
                    for pi in prn_inv:
                        if pi.part_name == row.get('part_name', ''):
                            stock = pi.current_stock
                            int_id = pi.internal_id
                            break
                    components.append({
                        'id': cid,
                        'internal_id': int_id,
                        'category': '3dprint',
                        'label': f"3D: {row.get('part_name','')} ({row.get('material','')})",
                        'part_name': row.get('part_name', ''),
                        'material': row.get('material', ''),
                        'qty': qty,
                        'to_order': max(0, qty - stock),
                        'current_stock': stock,
                        'reference': '',
                    })
            except Exception as e:
                print(f"3D parse error: {e}")

    return jsonify({
        'project_name': project_name,
        'components': components,
        'total_components': len(components),
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
