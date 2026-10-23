"""Tests for the BOM Parser."""
import sys
sys.path.insert(0, '.')
import pytest
import tempfile
import os
from src.bom_parser import BOMParser


def test_parse_csv():
    csv_content = """si.no,reference,value,footprint,mpn,manufacturer,qty,dnp
1,R1,10k,0603,CRCW060310K0,Vishay,5,
2,C1,100nF,0603,CL10B104KA8,Sam,3,x"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        tmp_path = f.name
    try:
        rows = BOMParser.parse_file(tmp_path, bom_type="electrical")
        assert len(rows) == 2
        assert rows[0].value == "10k"
        assert rows[0].qty == 5
        assert rows[0].dnp is False
        assert rows[1].value == "100nF"
        assert rows[1].dnp is True
    finally:
        os.unlink(tmp_path)


def test_parse_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        BOMParser.parse_file("/nonexistent/file.csv")


# ── DNP conventions (Bug 2) ────────────────────────────────────

def _parse_csv(csv_content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        tmp_path = f.name
    try:
        return BOMParser.parse_file(tmp_path, bom_type="electrical")
    finally:
        os.unlink(tmp_path)


def test_dnp_column_markers_mean_do_not_populate():
    rows = _parse_csv(
        "si.no,reference,value,footprint,mpn,manufacturer,qty,dnp\n"
        "1,R1,10k,0603,M1,Yageo,5,\n"
        "2,R2,10k,0603,M1,Yageo,5,DNF\n"
        "3,R3,10k,0603,M1,Yageo,5,no pop\n"
        "4,R4,10k,0603,M1,Yageo,5,0\n"
    )
    assert rows[0].dnp is False   # empty = populated
    assert rows[1].dnp is True    # DNF = do not populate
    assert rows[2].dnp is True    # "no pop" = do not populate
    assert rows[3].dnp is False   # 0 = populated


def test_populate_column_is_inverted():
    """In a 'Populate' column, YES/1 means the part IS fitted."""
    rows = _parse_csv(
        "si.no,reference,value,footprint,mpn,manufacturer,qty,populate\n"
        "1,R1,10k,0603,M1,Yageo,5,YES\n"
        "2,R2,10k,0603,M1,Yageo,5,1\n"
        "3,R3,10k,0603,M1,Yageo,5,NO\n"
        "4,R4,10k,0603,M1,Yageo,5,0\n"
    )
    assert rows[0].dnp is False   # YES = populated
    assert rows[1].dnp is False   # 1 = populated
    assert rows[2].dnp is True    # NO = not populated
    assert rows[3].dnp is True    # 0 = not populated


def test_fitted_column_is_inverted():
    rows = _parse_csv(
        "si.no,reference,value,footprint,mpn,manufacturer,qty,fitted\n"
        "1,R1,10k,0603,M1,Yageo,5,FITTED\n"
        "2,R2,10k,0603,M1,Yageo,5,\n"
    )
    assert rows[0].dnp is False   # FITTED = populated
    assert rows[1].dnp is False   # empty = populated (safer default)


def test_dnp_column_wins_when_both_present():
    rows = _parse_csv(
        "si.no,reference,value,footprint,mpn,manufacturer,qty,dnp,populate\n"
        "1,R1,10k,0603,M1,Yageo,5,X,YES\n"
    )
    # explicit DNP column says DNP → skip, even though populate says YES
    assert rows[0].dnp is True


def test_placeholder_dnp_value_is_ignored():
    """'—' / 'N/A' style placeholders must not mark the row as DNP."""
    rows = _parse_csv(
        "si.no,reference,value,footprint,mpn,manufacturer,qty,dnp\n"
        "1,R1,10k,0603,M1,Yageo,5,NA\n"
        "2,R2,10k,0603,M1,Yageo,5,-\n"
    )
    assert rows[0].dnp is False
    assert rows[1].dnp is False
