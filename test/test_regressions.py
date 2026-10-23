"""Regression tests for the 2026-10-23 code-review findings.

Each test names the finding it locks down.
"""
import sys
sys.path.insert(0, '.')

import shutil
import tempfile

import pytest

from src.file_manager import FileManager
from src.models import BomRow, Project
from src.routes.main import _merge_tree
from src.routes.orders import _component_fields, _order_qty
from src.routes.projects import _parse_bom_edit_payload


@pytest.fixture
def tmp_fm():
    tmp = tempfile.mkdtemp()
    fm = FileManager(tmp)
    yield fm, tmp
    shutil.rmtree(tmp, ignore_errors=True)


# Finding 1 — to_order == 0 must not fall back to total_required
def test_order_qty_zero_to_order_stays_zero():
    assert _order_qty({'to_order': 0, 'total_required': 100}) == 0


def test_order_qty_missing_falls_back_to_required():
    assert _order_qty({'total_required': 100}) == 100


def test_order_qty_garbage_is_zero():
    assert _order_qty({'to_order': 'abc'}) == 0


# Finding 2 — PCB gallery must survive save/load
def test_pcb_images_survive_save_load(tmp_fm):
    fm, _ = tmp_fm
    project = Project(name='BoardA')
    project.pcb_image = 'pcb_images/BoardA_pcb_img_1.png'
    project.pcb_images = [
        'pcb_images/BoardA_pcb_img_1.png',
        'pcb_images/BoardA_pcb_img_2.png',
    ]
    assert fm.save_project(project)

    loaded = fm.load_project('BoardA')
    assert loaded is not None
    assert loaded.pcb_images == project.pcb_images


# In-place BOM editing — posted rows replace the BOM safely
def _bom_row(**overrides):
    data = dict(
        si_no=1, reference='R1', value='10k', footprint='0603',
        manufacturer_part_number='MPN1', manufacturer_name='Yageo',
        manufacturer_part_number_lcsc='LC1', manufacturer_name_lcsc='LCSC',
        lcsc_sku='SKU1', qty=2, dnp=False, dnp_raw='',
    )
    data.update(overrides)
    return BomRow(**data)


def test_bom_edit_payload_updates_and_preserves_hidden_fields():
    base = [_bom_row()]
    rows = _parse_bom_edit_payload(base, {'rows': [{
        'orig_index': 0, 'si_no': '1', 'reference': 'R1', 'value': '22k',
        'footprint': '0603', 'manufacturer_part_number': 'MPN1',
        'manufacturer_name': 'Yageo', 'qty': '5', 'dnp': True,
    }]})
    assert len(rows) == 1
    assert rows[0].value == '22k'
    assert rows[0].qty == 5
    assert rows[0].dnp is True
    assert rows[0].dnp_raw == 'X'
    # Fields the editor doesn't show must survive
    assert rows[0].manufacturer_part_number_lcsc == 'LC1'
    assert rows[0].lcsc_sku == 'SKU1'


def test_bom_edit_payload_adds_rows_and_drops_blank_ones():
    base = [_bom_row()]
    rows = _parse_bom_edit_payload(base, {'rows': [
        {'orig_index': 0, 'reference': 'R1', 'value': '10k',
         'footprint': '0603', 'qty': '2', 'dnp': False},
        {'orig_index': None, 'reference': 'C9', 'value': '100nF',
         'footprint': '0603', 'manufacturer_part_number': '',
         'manufacturer_name': '', 'qty': '3', 'dnp': False},
        {'orig_index': None, 'reference': '', 'value': '', 'footprint': '',
         'qty': '1'},
    ]})
    assert len(rows) == 2
    assert rows[1].reference == 'C9'
    assert rows[1].qty == 3


def test_bom_edit_payload_rejects_bad_quantities():
    with pytest.raises(ValueError, match='qty must be a number'):
        _parse_bom_edit_payload([], {'rows': [
            {'reference': 'R1', 'qty': 'ten'}
        ]})


def test_bom_edit_payload_rejects_non_list_rows():
    with pytest.raises(ValueError, match='list of BOM rows'):
        _parse_bom_edit_payload([], {'rows': 'nope'})
    with pytest.raises(ValueError, match='JSON object'):
        _parse_bom_edit_payload([], None)


# Findings 10 & 12 — consolidation ids are validated / generated safely
def test_consolidation_load_rejects_bad_ids(tmp_fm):
    fm, _ = tmp_fm
    assert fm.load_consolidation('../master/electronics') is None
    assert fm.load_consolidation('CON-202610-001') is None


def test_consolidation_save_rejects_bad_ids(tmp_fm):
    fm, _ = tmp_fm
    assert not fm.save_consolidation({'id': '../evil', 'name': 'x'})


def test_create_consolidation_sequence(tmp_fm):
    fm, _ = tmp_fm
    first = fm.create_consolidation({'name': 'one'})
    second = fm.create_consolidation({'name': 'two'})

    assert first['id'].startswith('CON-')
    assert second['id'] != first['id']
    assert second['id'].endswith('-002')
    assert fm.load_consolidation(first['id'])['name'] == 'one'


# Finding 5 — every component category gets a readable label
def test_component_fields_per_category():
    assert _component_fields({
        'category': 'electrical', 'value': '100nF',
        'footprint': '0603', 'mpn': 'CL10B104',
    }) == ('100nF', '0603', 'CL10B104')

    assert _component_fields({
        'category': 'mechanical', 'part_name': 'M3 screw', 'value': 'M3x8',
    }) == ('M3 screw', 'M3x8', '')

    assert _component_fields({
        'category': 'pcb', 'board_name': 'Main',
    }) == ('PCB: Main', '', '')

    assert _component_fields({
        'category': '3dprint', 'part_name': 'Enclosure', 'material': 'PETG',
    }) == ('Enclosure', 'PETG', '')

    assert _component_fields({
        'category': 'custom', 'value': 'Solder paste', 'footprint': 'Custom',
    }) == ('Solder paste', 'Custom', '')


# Finding 11 — setup merge keeps colliding data instead of dropping it
def test_merge_tree_keeps_colliding_project(tmp_path):
    old = tmp_path / 'old'
    new = tmp_path / 'new'
    old.mkdir()
    new.mkdir()

    (old / 'projects' / 'BoardA').mkdir(parents=True)
    (new / 'projects' / 'BoardA').mkdir(parents=True)
    (old / 'projects' / 'BoardA' / 'meta.json').write_text('{"name": "old"}')
    (new / 'projects' / 'BoardA' / 'meta.json').write_text('{"name": "new"}')
    (old / 'master').mkdir()
    (old / 'master' / 'electronics.json').write_text('[]')

    renamed = []
    for item in list(old.iterdir()):
        renamed.extend(_merge_tree(item, new))
    old.rmdir()  # setup does this after the merge loop

    assert (new / 'projects' / 'BoardA' / 'meta.json').read_text() == '{"name": "new"}'
    migrated = new / 'projects' / 'BoardA-migrated-2'
    assert (migrated / 'meta.json').read_text() == '{"name": "old"}'
    assert migrated in renamed

    # Non-colliding folders merge normally, old folder is consumed
    assert (new / 'master' / 'electronics.json').read_text() == '[]'
    assert not old.exists()


# UI refresh — the orders page and dashboard must use the real lifecycle
# statuses (draft → ordered → shipped → received), not legacy "pending".
def test_order_summary_counts_active_statuses(tmp_fm):
    from src.aggregator import Aggregator
    from src.inventory_manager import InventoryManager
    from src.models import Order, OrderLineItem

    fm, _ = tmp_fm
    for i, status in enumerate(('draft', 'ordered', 'shipped'), start=1):
        fm.save_order(Order(
            order_id=f'PO-202610-{i:03d}',
            supplier='Mouser',
            status=status,
            line_items=[OrderLineItem(internal_id='E-0001', qty_ordered=2)],
        ))
    fm.save_order(Order(
        order_id='PO-202610-004',
        supplier='Mouser',
        status='received',
        line_items=[OrderLineItem(internal_id='E-0001', qty_ordered=1)],
    ))

    summary = InventoryManager(fm, Aggregator('SA')).get_order_summary()
    assert summary['pending_orders'] == 3
    assert summary['received_orders'] == 1


# UI refresh round 2 — vendor IDs, line edits on consolidations
def test_vendor_ids_are_assigned_uniquely():
    from src.routes.orders import _ensure_vendor_ids
    vendors = [
        {'name': 'Mouser'},
        {'name': 'LCSC', 'id': 'VEN-002'},
        {'name': 'O\'Brien'},
    ]
    changed = _ensure_vendor_ids(vendors)
    assert changed is True
    ids = [v['id'] for v in vendors]
    assert ids[0] == 'VEN-001'
    assert ids[1] == 'VEN-002'
    assert ids[2] == 'VEN-003'
    assert len(set(ids)) == 3
    # second pass is a no-op
    assert _ensure_vendor_ids(vendors) is False


def test_line_edits_apply_vendors_and_quantities():
    from src.routes.orders import _apply_line_edits
    record = {'components': [
        {'value': '100nF', 'to_order': 4, 'vendor': ''},
        {'value': '10k', 'to_order': 10, 'vendor': 'Mouser'},
        {'value': 'STM32', 'to_order': 2, 'vendor': ''},
    ]}
    form = {
        'vendor_0': 'LCSC',
        'qty_0': '12',
        'vendor_1': 'Mouser',   # unchanged
        'qty_1': '10',          # unchanged
        'qty_2': '0',           # plan change: zero it out
    }
    assert _apply_line_edits(record, form) is True
    assert record['components'][0]['vendor'] == 'LCSC'
    assert record['components'][0]['to_order'] == 12
    assert record['components'][2]['to_order'] == 0
    # unchanged form → nothing to persist
    assert _apply_line_edits(record, form) is False


def test_line_edits_ignore_junk_quantities():
    from src.routes.orders import _apply_line_edits
    record = {'components': [{'value': '100nF', 'to_order': 4}]}
    changed = _apply_line_edits(record, {'qty_0': 'abc'})
    assert changed is False
    assert record['components'][0]['to_order'] == 4
