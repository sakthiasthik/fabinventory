"""Tests for the Inventory Manager."""
import sys
sys.path.insert(0, '.')
import pytest
import tempfile
import shutil
import os
from src.file_manager import FileManager
from src.aggregator import Aggregator
from src.inventory_manager import InventoryManager
from src.models import Project, BomRow


@pytest.fixture
def tmp_inventory():
    tmp = tempfile.mkdtemp()
    fm = FileManager(tmp)
    agg = Aggregator("SA")
    im = InventoryManager(fm, agg)
    yield im, fm, agg
    shutil.rmtree(tmp)


def test_empty_inventory(tmp_inventory):
    im, fm, agg = tmp_inventory
    inv = im.get_inventory()
    assert inv == []


def test_update_inventory(tmp_inventory):
    im, fm, agg = tmp_inventory
    project = Project(name="Test", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="M1", manufacturer_name="Yageo", qty=5),
    ])
    result = im.update_inventory([project])
    assert len(result) == 1
    assert result[0].value == "10k"
    assert result[0].total_required == 5


def test_find_item(tmp_inventory):
    im, fm, agg = tmp_inventory
    project = Project(name="Test", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="M1", manufacturer_name="Yageo", qty=5),
    ])
    im.update_inventory([project])
    item = im.find_item("SA-ELE-00001")
    assert item is not None
    assert item.value == "10k"


def test_find_item_not_found(tmp_inventory):
    im, fm, agg = tmp_inventory
    assert im.find_item("NONEXISTENT-000") is None


def test_update_stock(tmp_inventory):
    im, fm, agg = tmp_inventory
    project = Project(name="Test", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="M1", manufacturer_name="Yageo", qty=5),
    ])
    im.update_inventory([project])
    result = im.update_stock("SA-ELE-00001", 20)
    assert result is not None
    assert result.current_stock == 20


def test_get_items_to_order(tmp_inventory):
    im, fm, agg = tmp_inventory
    project = Project(name="Test", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="M1", manufacturer_name="Yageo", qty=5),
    ])
    im.update_inventory([project])
    # total_required=5, stock=0 → to_order=5
    items = im.get_items_to_order()
    assert len(items) == 1
    assert items[0].to_order == 5
