"""FabInventory — Orders Blueprint"""
import csv
import io
import re

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, Response
from src.core import state, login_required
from datetime import datetime

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/orders')
def orders():
    """View all orders"""
    if not state.init_app():
        return redirect(url_for('main.setup'))

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


@orders_bp.route('/order/create', methods=['GET', 'POST'])
def create_order():
    """Create a new purchase order"""
    if not state.init_app():
        return redirect(url_for('main.setup'))

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
            return redirect(url_for('orders.create_order'))

        order = state.inventory_manager.create_order(supplier, items, notes)
        print("ORDER OBJECT:", order)
        if order:
            print("ORDER DATA:", order.__dict__)
            if state.git_manager:
                state.git_manager.commit(f"Created order {order.order_id}")
            flash(f'Order {order.order_id} created successfully!', 'success')
            return redirect(url_for('orders.orders'))
        else:
            print("ORDER CREATION FAILED ❌")
            flash('Failed to create order', 'error')

    # GET request - show form
    items_to_order = state.inventory_manager.get_items_to_order()
    mech_items = [i for i in state.inventory_manager.mech_inventory if i.to_order > 0]
    pcb_items = [i for i in state.inventory_manager.pcb_inventory if i.to_order > 0]
    prn_items = [i for i in state.inventory_manager.print3d_inventory if i.to_order > 0]
    projects_list = state.project_manager.list_projects()
    consolidations = state.file_manager.list_consolidations()

    return render_template(
        'create_order.html',
        items_to_order=items_to_order,
        mech_items=mech_items,
        pcb_items=pcb_items,
        prn_items=prn_items,
        projects=projects_list,
        consolidations=consolidations,
    )


@orders_bp.route('/order/<order_id>/receive', methods=['POST'])
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

    return redirect(url_for('orders.orders'))


@orders_bp.route('/order-summary')
def order_summary():
    """View order summary"""
    if not state.init_app():
        return redirect(url_for('main.setup'))

    summary = state.inventory_manager.get_order_summary()
    return render_template('order_summary.html', summary=summary)


@orders_bp.route('/order-tracking')
@login_required
def order_tracking():
    """Visual tracking of every purchase order's progress."""
    if not state.init_app():
        return redirect(url_for('main.setup'))

    STATUS_STEPS = ["draft", "ordered", "shipped", "received"]
    all_orders = state.inventory_manager.file_manager.list_orders()

    orders_data = []
    for order in all_orders:
        if order.status == order.STATUS_CANCELLED:
            step_index = -1
        else:
            step_index = (
                STATUS_STEPS.index(order.status)
                if order.status in STATUS_STEPS else 0
            )
        orders_data.append({
            'order_id': order.order_id,
            'supplier': order.supplier,
            'status': order.status,
            'step_index': step_index,
            'created_at': order.created_at,
            'shipped_at': order.shipped_at,
            'received_at': order.received_at,
            'tracking_info': order.tracking_info,
            'line_items': len(order.line_items),
            'total_qty': order.total_items,
            'cost': order.estimated_cost,
            'notes': order.notes,
            'consolidation_id': order.consolidation_id,
            'vendor_link': order.vendor_link,
        })

    return render_template(
        'order_tracking.html', orders_data=orders_data, steps=STATUS_STEPS
    )


# ── Vendors ────────────────────────────────────────────────────────

def _normalize_link(link: str) -> str:
    """Return a clean http(s) URL, or '' for empty input."""
    link = link.strip()
    if not link:
        return ''
    if not re.match(r'^https?://', link, re.IGNORECASE):
        link = 'https://' + link
    return link


@orders_bp.route('/vendors')
@login_required
def vendors_page():
    """Vendor management page."""
    if not state.init_app():
        return redirect(url_for('main.setup'))
    vendors = state.file_manager.list_vendors()
    return render_template('vendors.html', vendors=vendors)


@orders_bp.route('/vendors/add', methods=['POST'])
@login_required
def add_vendor():
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Vendor name is required', 'error')
        return redirect(url_for('orders.vendors_page'))

    vendors = state.file_manager.list_vendors()
    vendor = {
        'name': name,
        'contact': (request.form.get('contact') or '').strip(),
        'email': (request.form.get('email') or '').strip(),
        'website': _normalize_link(request.form.get('website', '')),
        'notes': (request.form.get('notes') or '').strip(),
    }
    # Update if the same name exists, otherwise append
    vendors = [v for v in vendors if v.get('name') != name]
    vendors.append(vendor)
    state.file_manager.save_vendors(vendors)
    flash(f'Vendor "{name}" saved', 'success')
    return redirect(url_for('orders.vendors_page'))


@orders_bp.route('/vendors/delete/<name>', methods=['POST'])
@login_required
def delete_vendor(name):
    vendors = [
        v for v in state.file_manager.list_vendors() if v.get('name') != name
    ]
    state.file_manager.save_vendors(vendors)
    flash(f'Vendor "{name}" removed', 'success')
    return redirect(url_for('orders.vendors_page'))


# ── Consolidation detail: per-line vendors → per-vendor orders ─────

@orders_bp.route('/order/consolidation/<consolidation_id>')
@login_required
def consolidation_detail(consolidation_id):
    """Open one saved consolidation: assign a vendor per line item,
    create one order per vendor, download the consolidated BOM."""
    if not state.init_app():
        return redirect(url_for('main.setup'))

    record = state.file_manager.load_consolidation(consolidation_id)
    if not record:
        flash(f'Consolidation {consolidation_id} not found', 'error')
        return redirect(url_for('orders.create_order'))

    vendors = state.file_manager.list_vendors()
    return render_template(
        'consolidation_detail.html', con=record, vendors=vendors
    )


@orders_bp.route('/order/consolidation/<consolidation_id>/set-vendors', methods=['POST'])
@login_required
def consolidation_set_vendors(consolidation_id):
    record = state.file_manager.load_consolidation(consolidation_id)
    if not record:
        flash(f'Consolidation {consolidation_id} not found', 'error')
        return redirect(url_for('orders.create_order'))

    for i, comp in enumerate(record.get('components', [])):
        comp['vendor'] = (request.form.get(f'vendor_{i}') or '').strip()
    record['components'][:] = record.get('components', [])

    state.file_manager.save_consolidation(record)
    flash('Vendors saved on all line items', 'success')
    return redirect(url_for('orders.consolidation_detail', consolidation_id=consolidation_id))


@orders_bp.route('/order/consolidation/<consolidation_id>/create-orders', methods=['POST'])
@login_required
def consolidation_create_orders(consolidation_id):
    """Split the consolidation by vendor and create ONE order per vendor."""
    record = state.file_manager.load_consolidation(consolidation_id)
    if not record:
        flash(f'Consolidation {consolidation_id} not found', 'error')
        return redirect(url_for('orders.create_order'))

    groups = {}
    unassigned = 0
    for comp in record.get('components', []):
        vendor = (comp.get('vendor') or '').strip()
        qty = int(comp.get('to_order') or comp.get('total_required') or 0)
        if qty <= 0:
            continue
        if vendor:
            groups.setdefault(vendor, []).append({
                'internal_id': comp.get('id') or comp.get('internal_id'),
                'qty': qty,
            })
        else:
            unassigned += 1

    if not groups:
        flash('Assign vendors to the line items first, then create orders', 'error')
        return redirect(url_for('orders.consolidation_detail', consolidation_id=consolidation_id))

    vendors = {v.get('name'): v for v in state.file_manager.list_vendors()}
    order_ids = []
    for vendor_name, items in groups.items():
        vendor_info = vendors.get(vendor_name, {})
        order = state.inventory_manager.create_order(
            vendor_name,
            items,
            f"From consolidation {consolidation_id}",
            consolidation_id=consolidation_id,
            vendor_link=vendor_info.get('website', ''),
        )
        if order:
            order_ids.append(order.order_id)

    if state.git_manager:
        state.git_manager.commit(
            f"Created orders {', '.join(order_ids)} from {consolidation_id}"
        )

    if unassigned:
        flash(
            f'Created {len(order_ids)} order(s) — {unassigned} line item(s) '
            'had no vendor and were skipped', 'warning'
        )
    else:
        flash(f'Created {len(order_ids)} order(s): {", ".join(order_ids)}', 'success')

    return redirect(url_for('orders.order_tracking'))


@orders_bp.route('/order/consolidation/<consolidation_id>/export')
@login_required
def consolidation_export(consolidation_id):
    """Download the consolidated BOM as CSV (one reference column per project)."""
    record = state.file_manager.load_consolidation(consolidation_id)
    if not record:
        flash(f'Consolidation {consolidation_id} not found', 'error')
        return redirect(url_for('orders.create_order'))

    project_names = [p.get('name', '') for p in record.get('projects', [])]

    buf = io.StringIO()
    writer = csv.writer(buf)
    header = ['Component', 'Footprint', 'MPN']
    header += [f'{n} Reference' for n in project_names]
    header += ['DNP', 'Required Qty', 'To Order', 'Vendor']
    writer.writerow(header)

    for comp in record.get('components', []):
        refs_by_project = {}
        for ref in comp.get('project_references', []):
            refs_by_project.setdefault(ref.get('project', ''), []).append(
                ref.get('reference', '')
            )
        row = [
            comp.get('value', ''),
            comp.get('footprint', ''),
            comp.get('mpn', ''),
        ]
        row += [
            ', '.join(r for r in refs_by_project.get(n, []) if r)
            for n in project_names
        ]
        row += [
            comp.get('dnp_raw', ''),
            comp.get('total_required', 0),
            comp.get('to_order', 0),
            comp.get('vendor', ''),
        ]
        writer.writerow(row)

    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename={consolidation_id}.csv'
        },
    )
