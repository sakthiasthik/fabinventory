"""Tests for the order-page components helpers (Bug 1 fix).

Duplicate BOM rows sharing the same part key must SUM their quantities,
not keep only the first row (which caused order quantity mismatches).
"""
import sys
sys.path.insert(0, '.')
from src.routes.api import (
    _elec_components, _mech_components, _pcb_components, _prn_components,
)
from src.models import BomRow, MasterItemMech, MasterItemPcb, MasterItemPrn3D


def _bom_row(value="10k", footprint="0603", qty=1, reference="R1",
             mpn="MPN1", dnp=False):
    return BomRow(
        si_no=1, reference=reference, value=value, footprint=footprint,
        manufacturer_part_number=mpn, manufacturer_name="MFG",
        qty=qty, dnp=dnp,
    )


def test_elec_duplicate_rows_are_summed():
    """10 rows of the same part (one per reference) must total 10, not 1."""
    rows = [_bom_row(reference=f"R{i}") for i in range(1, 11)]
    components = _elec_components(rows, {})
    assert len(components) == 1
    assert components[0]['qty'] == 10
    assert components[0]['to_order'] == 10
    assert components[0]['reference'] == ", ".join(f"R{i}" for i in range(1, 11))


def test_elec_different_parts_stay_separate():
    rows = [_bom_row(value="10k"), _bom_row(value="100nF")]
    components = _elec_components(rows, {})
    assert len(components) == 2


def test_elec_uses_master_inventory_id_and_stock():
    rows = [_bom_row(value="10k", footprint="0603", qty=5)]
    stock_lookup = {
        "10k|0603": {"current_stock": 2, "internal_id": "SA-ELE-00001"},
    }
    components = _elec_components(rows, stock_lookup)
    assert components[0]['id'] == "SA-ELE-00001"
    assert components[0]['internal_id'] == "SA-ELE-00001"
    assert components[0]['to_order'] == 3  # 5 required - 2 stock


def test_elec_skips_dnp_rows():
    rows = [_bom_row(qty=5), _bom_row(qty=1, dnp=True, reference="R2")]
    components = _elec_components(rows, {})
    assert len(components) == 1
    assert components[0]['qty'] == 5


def test_mech_duplicate_rows_are_summed():
    rows = [
        {"part_name": "Bolt M3", "value": "10mm", "quantity": 4},
        {"part_name": "Bolt M3", "value": "10mm", "quantity": 6},
    ]
    inv = [MasterItemMech(internal_id="SA-MEC-00001", part_name="Bolt M3",
                           value="10mm", total_required=10, current_stock=3)]
    components = _mech_components(rows, inv)
    assert len(components) == 1
    assert components[0]['qty'] == 10
    assert components[0]['internal_id'] == "SA-MEC-00001"
    assert components[0]['to_order'] == 7


def test_pcb_duplicate_rows_are_summed():
    rows = [
        {"board_name": "MainBoard", "quantity": 2},
        {"board_name": "MainBoard", "quantity": 3},
    ]
    inv = [MasterItemPcb(internal_id="SA-PCB-00001", board_name="MainBoard",
                         total_required=5, current_stock=1)]
    components = _pcb_components(rows, inv)
    assert len(components) == 1
    assert components[0]['qty'] == 5
    assert components[0]['to_order'] == 4


def test_prn_duplicate_rows_are_summed():
    rows = [
        {"part_name": "Case", "material": "PLA", "quantity": 1},
        {"part_name": "Case", "material": "PLA", "quantity": 2},
    ]
    inv = [MasterItemPrn3D(internal_id="SA-PRN-00001", part_name="Case",
                           material="PLA", total_required=3, current_stock=0)]
    components = _prn_components(rows, inv)
    assert len(components) == 1
    assert components[0]['qty'] == 3
    assert components[0]['to_order'] == 3
