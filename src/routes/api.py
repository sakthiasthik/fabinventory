"""FabInventory — API Blueprint"""
from pathlib import Path
from flask import Blueprint, jsonify, request
from src.core import state, api_login_required
from src.models import normalize_part_key

api_bp = Blueprint('api', __name__)


# ── Components-endpoint helpers ────────────────────────────────
# Group BOM rows by part key and SUM quantities. The order page must
# show the same totals as the master inventory (aggregator), so
# duplicate rows with the same value+footprint must accumulate —
# never be dropped.


def _elec_components(bom_rows, stock_lookup):
    """Aggregate electrical BOM rows by value|footprint (or internal id),
    summing quantities and collecting references + MPNs."""
    aggregated = {}
    for bom_row in bom_rows:
        if not bom_row.is_active():
            continue
        key = normalize_part_key(bom_row.value, bom_row.footprint)
        stock_info = stock_lookup.get(key, {'current_stock': 0, 'internal_id': None})
        cid = stock_info.get('internal_id') or key
        entry = aggregated.get(cid)
        if entry is None:
            entry = aggregated[cid] = {
                'stock_info': stock_info,
                'value': bom_row.value,
                'footprint': bom_row.footprint,
                'qty': 0,
                'references': [],
                'mpns': [],
            }
        entry['qty'] += bom_row.qty
        if bom_row.reference and bom_row.reference not in entry['references']:
            entry['references'].append(bom_row.reference)
        if (bom_row.manufacturer_part_number
                and bom_row.manufacturer_part_number not in entry['mpns']):
            entry['mpns'].append(bom_row.manufacturer_part_number)

    components = []
    for cid, entry in aggregated.items():
        stock = entry['stock_info'].get('current_stock', 0)
        components.append({
            'id': cid,
            'internal_id': entry['stock_info'].get('internal_id') or '',
            'category': 'electrical',
            'label': f"{entry['value']} — {entry['footprint']}",
            'value': entry['value'],
            'footprint': entry['footprint'],
            'mpn': ', '.join(entry['mpns']),
            'qty': entry['qty'],
            'to_order': max(0, entry['qty'] - stock),
            'current_stock': stock,
            'reference': ', '.join(entry['references']),
        })
    return components


def _mech_components(rows, mech_inventory):
    """Sum mechanical BOM rows sharing the same part_name|value key."""
    aggregated = {}
    for row in rows:
        raw_key = normalize_part_key(row.get('part_name', ''), row.get('value', ''))
        cid = f"mech-{raw_key}"
        entry = aggregated.get(cid)
        if entry is None:
            stock, int_id = 0, ''
            for mi in mech_inventory:
                if mi.get_aggregation_key() == raw_key:
                    stock, int_id = mi.current_stock, mi.internal_id
                    break
            entry = aggregated[cid] = {
                'stock': stock,
                'int_id': int_id,
                'qty': 0,
                'part_name': row.get('part_name', ''),
                'value': row.get('value', ''),
            }
        entry['qty'] += int(row.get('quantity', 0))

    return [
        {
            'id': cid,
            'internal_id': entry['int_id'],
            'category': 'mechanical',
            'label': f"{entry['part_name']} — {entry['value']}",
            'part_name': entry['part_name'],
            'value': entry['value'],
            'qty': entry['qty'],
            'to_order': max(0, entry['qty'] - entry['stock']),
            'current_stock': entry['stock'],
            'reference': '',
        }
        for cid, entry in aggregated.items()
    ]


def _pcb_components(rows, pcb_inventory):
    """Sum PCB BOM rows sharing the same board_name."""
    aggregated = {}
    for row in rows:
        board_name = row.get('board_name', '')
        cid = f"pcb-{board_name}"
        entry = aggregated.get(cid)
        if entry is None:
            stock, int_id = 0, ''
            for pi in pcb_inventory:
                if pi.get_aggregation_key() == normalize_part_key(board_name):
                    stock, int_id = pi.current_stock, pi.internal_id
                    break
            entry = aggregated[cid] = {
                'stock': stock,
                'int_id': int_id,
                'qty': 0,
                'board_name': board_name,
            }
        entry['qty'] += int(row.get('quantity', 0))

    return [
        {
            'id': cid,
            'internal_id': entry['int_id'],
            'category': 'pcb',
            'label': f"PCB: {entry['board_name']}",
            'board_name': entry['board_name'],
            'qty': entry['qty'],
            'to_order': max(0, entry['qty'] - entry['stock']),
            'current_stock': entry['stock'],
            'reference': '',
        }
        for cid, entry in aggregated.items()
    ]


def _prn_components(rows, prn_inventory):
    """Sum 3D-print BOM rows sharing the same part_name."""
    aggregated = {}
    for row in rows:
        part_name = row.get('part_name', '')
        cid = f"3d-{part_name}"
        entry = aggregated.get(cid)
        if entry is None:
            stock, int_id = 0, ''
            for pi in prn_inventory:
                if pi.get_aggregation_key() == normalize_part_key(part_name):
                    stock, int_id = pi.current_stock, pi.internal_id
                    break
            entry = aggregated[cid] = {
                'stock': stock,
                'int_id': int_id,
                'qty': 0,
                'part_name': part_name,
                'material': row.get('material', ''),
            }
        entry['qty'] += int(row.get('quantity', 0))

    return [
        {
            'id': cid,
            'internal_id': entry['int_id'],
            'category': '3dprint',
            'label': f"3D: {entry['part_name']} ({entry['material']})",
            'part_name': entry['part_name'],
            'material': entry['material'],
            'qty': entry['qty'],
            'to_order': max(0, entry['qty'] - entry['stock']),
            'current_stock': entry['stock'],
            'reference': '',
        }
        for cid, entry in aggregated.items()
    ]


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

    # ── Electrical ──────────────────────────────────────────────
    inventory_items = state.inventory_manager.get_inventory()
    stock_lookup = {}
    for item in inventory_items:
        key = normalize_part_key(item.value, item.footprint)
        stock_lookup[key] = {
            'current_stock': item.current_stock,
            'internal_id': item.internal_id,
        }

    # Sum ALL rows per value|footprint — duplicate rows (one row per
    # reference) must accumulate, matching the master inventory totals.
    components.extend(_elec_components(project.bom, stock_lookup))

    # ── Mechanical ──────────────────────────────────────────────
    if project.mechanical_bom:
        from src.bom_parser import BOMParser
        mech_path = data_root / project.mechanical_bom
        if mech_path.exists():
            try:
                rows = BOMParser.parse_file(str(mech_path), bom_type='mechanical')
                components.extend(
                    _mech_components(rows, state.inventory_manager.mech_inventory)
                )
            except Exception as e:
                print(f"Mech parse error: {e}")

    # ── PCB ────────────────────────────────────────────────────
    if project.pcb_bom:
        from src.bom_parser import BOMParser
        pcb_path = data_root / project.pcb_bom
        if pcb_path.exists():
            try:
                rows = BOMParser.parse_file(str(pcb_path), bom_type='pcb')
                components.extend(
                    _pcb_components(rows, state.inventory_manager.pcb_inventory)
                )
            except Exception as e:
                print(f"PCB parse error: {e}")

    # ── 3D Print ───────────────────────────────────────────────
    if project.print3d_bom:
        from src.bom_parser import BOMParser
        prn_path = data_root / project.print3d_bom
        if prn_path.exists():
            try:
                rows = BOMParser.parse_file(str(prn_path), bom_type='3dprint')
                components.extend(
                    _prn_components(rows, state.inventory_manager.print3d_inventory)
                )
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
