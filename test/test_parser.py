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
