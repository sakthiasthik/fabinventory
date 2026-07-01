"""FabInventory — Inventory Blueprint"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from src.core import state, login_required
from datetime import datetime
from werkzeug.utils import secure_filename

inventory_bp = Blueprint('inventory', __name__)


@inventory_bp.route('/')
def inventory():
    """View master inventory (tabbed: electrical|mechanical|pcb|3dprint)"""
    if not state.init_app():
        return redirect(url_for('main.setup'))

    tab = request.args.get('tab', 'electrical')

    if tab == 'mechanical':
        items = state.inventory_manager.mech_inventory
    elif tab == 'pcb':
        items = state.inventory_manager.pcb_inventory
    elif tab == '3dprint':
        items = state.inventory_manager.print3d_inventory
    else:
        items = state.inventory_manager.inventory

    return render_template('inventory.html', inventory=items, active_tab=tab)


@inventory_bp.route('/update-stock', methods=['POST'])
def update_stock():
    """Update stock for an item (any category)"""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    internal_id = request.form.get('internal_id', '').strip()
    category = request.form.get('category', 'electrical').strip()

    try:
        new_stock = int(request.form.get('stock', 0))
        if new_stock < 0:
            flash('Stock cannot be negative', 'error')
            return redirect(url_for('inventory.inventory', tab=category))
    except (ValueError, TypeError):
        flash('Invalid stock value', 'error')
        return redirect(url_for('inventory.inventory', tab=category))

    if category == 'mechanical':
        updated = state.inventory_manager.update_mechanical_stock(internal_id, new_stock)
    elif category == 'pcb':
        updated = state.inventory_manager.update_pcb_stock(internal_id, new_stock)
    elif category == '3dprint':
        updated = state.inventory_manager.update_print3d_stock(internal_id, new_stock)
    else:
        # Verify item exists for electrical
        item = state.inventory_manager.find_item(internal_id)
        if not item:
            flash(f'Item "{internal_id}" not found in inventory', 'error')
            return redirect(url_for('inventory.inventory', tab=category))
        updated = state.inventory_manager.update_stock(internal_id, new_stock)

    if updated:
        if state.git_manager:
            state.git_manager.commit(f"Updated stock for {internal_id} to {new_stock}")
        flash(f'Stock updated for {internal_id}!', 'success')
    else:
        flash(f'Failed to update stock for {internal_id}', 'error')

    return redirect(url_for('inventory.inventory', tab=category))


@inventory_bp.route('/import-stock', methods=['POST'])
def import_stock():
    """Bulk-import stock levels from Excel/CSV file."""
    if not state.init_app():
        return jsonify({'error': 'App not initialized'}), 500

    if 'stock_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('inventory.inventory'))

    file = request.files['stock_file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('inventory.inventory'))

    import pandas as pd
    import io

    filename = secure_filename(file.filename)
    try:
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(io.StringIO(file.read().decode('utf-8')))
        else:
            df = pd.read_excel(file, engine='openpyxl')
    except Exception as e:
        flash(f'Failed to read file: {e}', 'error')
        return redirect(url_for('inventory.inventory'))

    # Normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]

    updated_count = 0
    errors = []
    inv = state.inventory_manager

    for idx, row in df.iterrows():
        category = str(row.get('category', 'electrical')).strip().lower()

        try:
            stock = int(row.get('stock', 0))
        except (ValueError, TypeError):
            errors.append(f"Row {idx + 2}: invalid stock value")
            continue

        if category in ('electrical', 'ele'):
            value = str(row.get('value', '')).strip()
            footprint = str(row.get('footprint', '')).strip()
            if not value or not footprint:
                errors.append(f"Row {idx + 2}: missing value or footprint")
                continue
            matched = False
            for item in inv.inventory:
                if item.value == value and item.footprint == footprint:
                    item.current_stock = stock
                    item.last_updated = datetime.now().isoformat()
                    updated_count += 1
                    matched = True
                    break
            if not matched:
                errors.append(f"Row {idx + 2}: no match for {value}|{footprint}")

        elif category in ('mechanical', 'mec'):
            part_name = str(row.get('part_name', '')).strip()
            value = str(row.get('value', '')).strip()
            key = f"{part_name}|{value}"
            matched = False
            for item in inv.mech_inventory:
                if item.get_aggregation_key() == key:
                    item.current_stock = stock
                    item.last_updated = datetime.now().isoformat()
                    updated_count += 1
                    matched = True
                    break
            if not matched:
                errors.append(f"Row {idx + 2}: no match for mechanical {key}")

        elif category == 'pcb':
            board_name = str(row.get('board_name', '')).strip()
            matched = False
            for item in inv.pcb_inventory:
                if item.board_name == board_name:
                    item.current_stock = stock
                    item.last_updated = datetime.now().isoformat()
                    updated_count += 1
                    matched = True
                    break
            if not matched:
                errors.append(f"Row {idx + 2}: no match for PCB '{board_name}'")

        elif category in ('3dprint', 'print3d', '3d'):
            part_name = str(row.get('part_name', '')).strip()
            matched = False
            for item in inv.print3d_inventory:
                if item.part_name == part_name:
                    item.current_stock = stock
                    item.last_updated = datetime.now().isoformat()
                    updated_count += 1
                    matched = True
                    break
            if not matched:
                errors.append(f"Row {idx + 2}: no match for 3D print '{part_name}'")

        else:
            errors.append(f"Row {idx + 2}: unknown category '{category}'")

    # Persist all changes
    inv.file_manager.save_master_inventory(inv.inventory)
    inv.file_manager.save_mechanical_inventory(inv.mech_inventory)
    inv.file_manager.save_pcb_inventory(inv.pcb_inventory)
    inv.file_manager.save_print3d_inventory(inv.print3d_inventory)

    if state.git_manager:
        state.git_manager.commit(f"Bulk stock import: {updated_count} items updated")

    flash(f'Import complete. Updated {updated_count} items.', 'success')
    if errors:
        for err in errors[:10]:
            flash(err, 'warning')
        if len(errors) > 10:
            flash(f'... and {len(errors) - 10} more warnings.', 'warning')

    return redirect(url_for('inventory.inventory'))
