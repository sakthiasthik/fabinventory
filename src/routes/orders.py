"""FabInventory — Orders Blueprint"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
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

    projects_list = state.project_manager.list_projects()

    return render_template(

        'create_order.html',

        items_to_order=items_to_order,

        projects=projects_list
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
