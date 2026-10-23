"""Tests for model helpers."""
import sys
sys.path.insert(0, '.')
from src.models import derive_company_prefix


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
