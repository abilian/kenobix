"""
Tests for ODM lookup operators.

Tests cover:
- __in: Membership in a list
- __gt, __gte, __lt, __lte: Comparison operators
- __ne: Not equal
- __like: SQL LIKE pattern matching
- __isnull: NULL checking
- Combined lookups
- Edge cases
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from kenobix import KenobiX
from kenobix.odm import Document, _build_filter_condition, _parse_filter_key


@pytest.fixture
def db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test_lookups.db"
    db = KenobiX(str(db_path), indexed_fields=["name", "status"])
    yield db
    db.close()


@pytest.fixture
def setup_models(db):
    """Set up ODM models for testing."""
    Document.set_database(db)

    @dataclass
    class Product(Document):
        class Meta:
            collection_name = "products"
            indexed_fields = ["name", "category"]

        name: str
        price: float
        quantity: int
        category: str
        active: bool = True
        description: str | None = None

    # Create test data
    Product(name="Apple", price=1.50, quantity=100, category="fruit").save()
    Product(name="Banana", price=0.75, quantity=50, category="fruit").save()
    Product(name="Carrot", price=0.50, quantity=200, category="vegetable").save()
    Product(name="Milk", price=3.00, quantity=30, category="dairy").save()
    Product(
        name="Cheese", price=5.00, quantity=20, category="dairy", active=False
    ).save()
    Product(
        name="Orange",
        price=1.25,
        quantity=0,
        category="fruit",
        description="Citrus fruit",
    ).save()

    return Product


class TestParseFilterKey:
    """Tests for _parse_filter_key function."""

    def test_simple_field(self):
        """Simple field name without lookup."""
        assert _parse_filter_key("name") == ("name", "exact")

    def test_field_with_underscore(self):
        """Field name containing underscores."""
        assert _parse_filter_key("first_name") == ("first_name", "exact")

    def test_gt_lookup(self):
        """Greater than lookup."""
        assert _parse_filter_key("age__gt") == ("age", "gt")

    def test_gte_lookup(self):
        """Greater than or equal lookup."""
        assert _parse_filter_key("age__gte") == ("age", "gte")

    def test_lt_lookup(self):
        """Less than lookup."""
        assert _parse_filter_key("age__lt") == ("age", "lt")

    def test_lte_lookup(self):
        """Less than or equal lookup."""
        assert _parse_filter_key("age__lte") == ("age", "lte")

    def test_in_lookup(self):
        """Membership lookup."""
        assert _parse_filter_key("status__in") == ("status", "in")

    def test_ne_lookup(self):
        """Not equal lookup."""
        assert _parse_filter_key("status__ne") == ("status", "ne")

    def test_like_lookup(self):
        """LIKE pattern lookup."""
        assert _parse_filter_key("name__like") == ("name", "like")

    def test_isnull_lookup(self):
        """IS NULL lookup."""
        assert _parse_filter_key("description__isnull") == ("description", "isnull")

    def test_unknown_suffix_treated_as_field(self):
        """Unknown suffix should be treated as part of field name."""
        assert _parse_filter_key("user__status") == ("user__status", "exact")

    def test_field_with_underscore_and_lookup(self):
        """Field with underscores and a lookup."""
        assert _parse_filter_key("first_name__like") == ("first_name", "like")


class TestBuildFilterCondition:
    """Tests for _build_filter_condition function."""

    def test_exact_indexed(self):
        """Exact match on indexed field."""
        condition, params = _build_filter_condition(
            "name", "exact", "Alice", {"name"}, lambda x: x
        )
        assert condition == "name = ?"
        assert params == ["Alice"]

    def test_exact_non_indexed(self):
        """Exact match on non-indexed field."""
        condition, params = _build_filter_condition(
            "age", "exact", 30, set(), lambda x: x
        )
        assert condition == "json_extract(data, '$.age') = ?"
        assert params == [30]

    def test_in_lookup(self):
        """IN lookup with list."""
        condition, params = _build_filter_condition(
            "status", "in", ["active", "pending"], {"status"}, lambda x: x
        )
        assert condition == "status IN (?, ?)"
        assert params == ["active", "pending"]

    def test_in_empty_list(self):
        """IN lookup with empty list returns false condition."""
        condition, params = _build_filter_condition(
            "status", "in", [], {"status"}, lambda x: x
        )
        assert condition == "1 = 0"
        assert params == []

    def test_in_invalid_type_raises(self):
        """IN lookup with non-iterable raises ValueError."""
        with pytest.raises(ValueError, match="__in lookup requires"):
            _build_filter_condition("status", "in", "active", {"status"}, lambda x: x)

    def test_gt_lookup(self):
        """Greater than lookup."""
        condition, params = _build_filter_condition("age", "gt", 18, set(), lambda x: x)
        assert condition == "json_extract(data, '$.age') > ?"
        assert params == [18]

    def test_isnull_true(self):
        """IS NULL lookup."""
        condition, params = _build_filter_condition(
            "description", "isnull", True, set(), lambda x: x
        )
        assert condition == "json_extract(data, '$.description') IS NULL"
        assert params == []

    def test_isnull_false(self):
        """IS NOT NULL lookup."""
        condition, params = _build_filter_condition(
            "description", "isnull", False, set(), lambda x: x
        )
        assert condition == "json_extract(data, '$.description') IS NOT NULL"
        assert params == []


class TestInLookup:
    """Tests for __in lookup operator."""

    def test_in_with_list(self, setup_models):
        """Filter with __in using a list."""
        Product = setup_models
        results = Product.filter(category__in=["fruit", "dairy"])
        assert len(results) == 5  # Apple, Banana, Orange, Milk, Cheese

    def test_in_with_tuple(self, setup_models):
        """Filter with __in using a tuple."""
        Product = setup_models
        results = Product.filter(category__in=("fruit", "vegetable"))
        assert len(results) == 4  # Apple, Banana, Orange, Carrot

    def test_in_with_set(self, setup_models):
        """Filter with __in using a set."""
        Product = setup_models
        results = Product.filter(category__in={"dairy"})
        assert len(results) == 2  # Milk, Cheese

    def test_in_with_single_value(self, setup_models):
        """Filter with __in containing single value."""
        Product = setup_models
        results = Product.filter(name__in=["Apple"])
        assert len(results) == 1
        assert results[0].name == "Apple"

    def test_in_with_empty_list(self, setup_models):
        """Filter with __in and empty list returns no results."""
        Product = setup_models
        results = Product.filter(category__in=[])
        assert len(results) == 0

    def test_in_no_matches(self, setup_models):
        """Filter with __in where no values match."""
        Product = setup_models
        results = Product.filter(category__in=["electronics", "clothing"])
        assert len(results) == 0

    def test_in_on_indexed_field(self, setup_models):
        """Filter with __in on indexed field."""
        Product = setup_models
        results = Product.filter(category__in=["fruit"])
        assert len(results) == 3


class TestComparisonLookups:
    """Tests for comparison lookup operators."""

    def test_gt(self, setup_models):
        """Filter with __gt (greater than)."""
        Product = setup_models
        results = Product.filter(price__gt=2.00)
        assert len(results) == 2  # Milk (3.00), Cheese (5.00)

    def test_gte(self, setup_models):
        """Filter with __gte (greater than or equal)."""
        Product = setup_models
        results = Product.filter(price__gte=3.00)
        assert len(results) == 2  # Milk, Cheese

    def test_lt(self, setup_models):
        """Filter with __lt (less than)."""
        Product = setup_models
        results = Product.filter(price__lt=1.00)
        assert len(results) == 2  # Banana (0.75), Carrot (0.50)

    def test_lte(self, setup_models):
        """Filter with __lte (less than or equal)."""
        Product = setup_models
        results = Product.filter(price__lte=0.75)
        assert len(results) == 2  # Banana, Carrot

    def test_ne(self, setup_models):
        """Filter with __ne (not equal)."""
        Product = setup_models
        results = Product.filter(category__ne="fruit")
        assert len(results) == 3  # Carrot, Milk, Cheese

    def test_gt_with_zero(self, setup_models):
        """Filter with __gt and zero value."""
        Product = setup_models
        results = Product.filter(quantity__gt=0)
        assert len(results) == 5  # All except Orange (quantity=0)

    def test_lte_with_zero(self, setup_models):
        """Filter with __lte and zero value."""
        Product = setup_models
        results = Product.filter(quantity__lte=0)
        assert len(results) == 1  # Orange


class TestLikeLookup:
    """Tests for __like lookup operator."""

    def test_like_starts_with(self, setup_models):
        """Filter with LIKE pattern starting with."""
        Product = setup_models
        results = Product.filter(name__like="C%")
        assert len(results) == 2  # Carrot, Cheese

    def test_like_ends_with(self, setup_models):
        """Filter with LIKE pattern ending with."""
        Product = setup_models
        results = Product.filter(name__like="%e")
        # Apple, Orange, Cheese all end with 'e'
        assert len(results) == 3

    def test_like_contains(self, setup_models):
        """Filter with LIKE pattern containing."""
        Product = setup_models
        results = Product.filter(name__like="%an%")
        assert len(results) == 2  # Banana, Orange

    def test_like_exact_match(self, setup_models):
        """Filter with LIKE exact match (no wildcards)."""
        Product = setup_models
        results = Product.filter(name__like="Apple")
        assert len(results) == 1
        assert results[0].name == "Apple"

    def test_like_single_char_wildcard(self, setup_models):
        """Filter with LIKE single character wildcard."""
        Product = setup_models
        results = Product.filter(name__like="_ilk")
        assert len(results) == 1
        assert results[0].name == "Milk"


class TestIsnullLookup:
    """Tests for __isnull lookup operator."""

    def test_isnull_true(self, setup_models):
        """Filter for NULL values."""
        Product = setup_models
        results = Product.filter(description__isnull=True)
        assert len(results) == 5  # All except Orange

    def test_isnull_false(self, setup_models):
        """Filter for NOT NULL values."""
        Product = setup_models
        results = Product.filter(description__isnull=False)
        assert len(results) == 1
        assert results[0].name == "Orange"


class TestCombinedLookups:
    """Tests for combining multiple lookup operators."""

    def test_combine_exact_and_gt(self, setup_models):
        """Combine exact match with greater than."""
        Product = setup_models
        results = Product.filter(category="fruit", price__gt=1.00)
        assert len(results) == 2  # Apple (1.50), Orange (1.25)

    def test_combine_in_and_lt(self, setup_models):
        """Combine __in with __lt."""
        Product = setup_models
        results = Product.filter(category__in=["fruit", "vegetable"], price__lt=1.00)
        assert len(results) == 2  # Banana, Carrot

    def test_combine_multiple_comparisons(self, setup_models):
        """Combine multiple comparison operators."""
        Product = setup_models
        results = Product.filter(price__gte=0.50, price__lte=1.50)
        assert len(results) == 4  # Carrot, Banana, Orange, Apple

    def test_combine_ne_and_isnull(self, setup_models):
        """Combine __ne with __isnull."""
        Product = setup_models
        results = Product.filter(category__ne="fruit", description__isnull=True)
        assert len(results) == 3  # Carrot, Milk, Cheese

    def test_combine_like_and_in(self, setup_models):
        """Combine __like with __in."""
        Product = setup_models
        results = Product.filter(name__like="C%", category__in=["vegetable", "dairy"])
        assert len(results) == 2  # Carrot, Cheese


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_filter_on_boolean(self, setup_models):
        """Filter on boolean field."""
        Product = setup_models
        results = Product.filter(active=True)
        assert len(results) == 5

        results = Product.filter(active=False)
        assert len(results) == 1
        assert results[0].name == "Cheese"

    def test_filter_with_none_value(self, setup_models):
        """Filter with None value uses __isnull for correct behavior."""
        Product = setup_models
        # Note: Filtering with field=None doesn't work reliably with JSON
        # because missing fields and null values are different.
        # Use __isnull=True instead for NULL checking.
        results = Product.filter(description__isnull=True)
        assert len(results) == 5

    def test_in_with_numbers(self, setup_models):
        """__in with numeric values."""
        Product = setup_models
        results = Product.filter(quantity__in=[50, 100, 200])
        assert len(results) == 3  # Apple, Banana, Carrot

    def test_gt_with_float(self, setup_models):
        """__gt with float value."""
        Product = setup_models
        results = Product.filter(price__gt=1.25)
        assert len(results) == 3  # Apple, Milk, Cheese

    def test_empty_filter_returns_all(self, setup_models):
        """Empty filter should return all records."""
        Product = setup_models
        results = Product.filter()
        assert len(results) == 6

    def test_get_with_lookup(self, setup_models):
        """get() method should work with lookups."""
        Product = setup_models
        result = Product.get(price__gt=4.00)
        assert result is not None
        assert result.name == "Cheese"

    def test_get_with_in_lookup(self, setup_models):
        """get() with __in returns first match."""
        Product = setup_models
        result = Product.get(category__in=["dairy"])
        assert result is not None
        assert result.category == "dairy"

    def test_filter_with_limit_and_lookup(self, setup_models):
        """Filter with lookup and limit."""
        Product = setup_models
        results = Product.filter(category="fruit", limit=2)
        assert len(results) == 2

    def test_filter_with_offset_and_lookup(self, setup_models):
        """Filter with lookup, limit, and offset."""
        Product = setup_models
        # Get all fruit products
        all_fruit = Product.filter(category="fruit")
        assert len(all_fruit) == 3

        # Get fruit with limit and offset
        first_two = Product.filter(category="fruit", limit=2)
        assert len(first_two) == 2

        # Offset requires limit to work
        second_batch = Product.filter(category="fruit", limit=10, offset=1)
        assert len(second_batch) == 2  # Skip first, get remaining 2
