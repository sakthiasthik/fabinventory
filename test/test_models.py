"""Tests for model helpers."""
import sys
sys.path.insert(0, '.')
from src.models import derive_company_prefix, Order


def test_derive_prefix_simple_name():
    assert derive_company_prefix("Sakthi") == "SA"


def test_derive_prefix_multi_word_name():
    assert derive_company_prefix("Sakthi Electronics") == "SA"


def test_derive_prefix_initials_for_short_first_word():
    assert derive_company_prefix("A B Solutions") == "AB"


def test_derive_prefix_single_letter():
    assert derive_company_prefix("X") == "XX"


def test_derive_prefix_empty_and_garbage():
    assert derive_company_prefix("") == "FI"
    assert derive_company_prefix("   ") == "FI"
    assert derive_company_prefix("!!!") == "FI"


def test_derive_prefix_ignores_punctuation():
    assert derive_company_prefix("(Sakthi) Labs") == "SA"


def test_order_roundtrip_with_consolidation_fields():
    order = Order(order_id="PO-202610-001", supplier="Mouser",
                  consolidation_id="CON-202610-001",
                  vendor_link="https://www.mouser.com")
    loaded = Order.from_dict(order.to_dict())
    assert loaded.consolidation_id == "CON-202610-001"
    assert loaded.vendor_link == "https://www.mouser.com"


def test_order_loads_old_data_without_new_fields():
    loaded = Order.from_dict({"order_id": "PO-1", "supplier": "X"})
    assert loaded.consolidation_id is None
    assert loaded.vendor_link is None
