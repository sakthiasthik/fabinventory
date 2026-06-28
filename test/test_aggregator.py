"""Tests for the Aggregator — master inventory aggregation logic."""
import sys
sys.path.insert(0, '.')
import pytest
from src.models import Project, BomRow, MasterItem
from src.aggregator import Aggregator


def test_aggregate_empty_projects():
    agg = Aggregator("SA")
    result = agg.aggregate([])
    assert result == []


def test_aggregate_single_project():
    agg = Aggregator("SA")
    project = Project(name="TestProject", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="MPN123", manufacturer_name="Yageo", qty=5),
        BomRow(si_no=2, reference="C1", value="100nF", footprint="0603",
               manufacturer_part_number="MPN456", manufacturer_name="Samsung", qty=3),
    ])
    result = agg.aggregate([project])
    assert len(result) == 2
    # Results sorted by internal_id (generation order)
    values = {r.value: r.total_required for r in result}
    assert values == {"10k": 5, "100nF": 3}


def test_aggregate_merges_same_component():
    agg = Aggregator("SA")
    p1 = Project(name="P1", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="M1", manufacturer_name="Yageo", qty=5),
    ])
    p2 = Project(name="P2", bom=[
        BomRow(si_no=1, reference="R2", value="10k", footprint="0603",
               manufacturer_part_number="M2", manufacturer_name="Vishay", qty=3),
    ])
    result = agg.aggregate([p1, p2])
    assert len(result) == 1
    assert result[0].total_required == 8
    assert "P1" in result[0].used_in_projects
    assert "P2" in result[0].used_in_projects
    assert "M1" in result[0].associated_mpns
    assert "M2" in result[0].associated_mpns


def test_aggregate_skips_dnp():
    agg = Aggregator("SA")
    project = Project(name="Test", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="M1", manufacturer_name="Yageo", qty=5, dnp=True),
    ])
    result = agg.aggregate([project])
    assert len(result) == 0


def test_aggregate_id_generation():
    agg = Aggregator("SA")
    agg.set_next_id(1)
    project = Project(name="Test", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="M1", manufacturer_name="Yageo", qty=5),
    ])
    result = agg.aggregate([project])
    assert result[0].internal_id == "SA-ELE-00001"


def test_preserves_existing_stock():
    agg = Aggregator("SA")
    existing = MasterItem(
        internal_id="SA-ELE-00001", value="10k", footprint="0603",
        total_required=5, current_stock=10, used_in_projects=["Old"], associated_mpns=["M1"]
    )
    project = Project(name="New", bom=[
        BomRow(si_no=1, reference="R1", value="10k", footprint="0603",
               manufacturer_part_number="M1", manufacturer_name="Yageo", qty=2),
    ])
    result = agg.aggregate([project], existing_items=[existing])
    assert result[0].current_stock == 10  # preserved
    assert result[0].total_required == 2  # recalculated
