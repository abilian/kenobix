"""
.. moduleauthor:: Harrison Erd <harrisonerd@gmail.com>

Tests for KenobiX (fast version with indexed fields)

Run tests:

.. code-block:: shell

   pytest -vv --showlocals -k "test_kenobix" tests

Run with coverage:

.. code-block:: shell

   python -m coverage run --source='kenobi.kenobix' -m pytest \
   --showlocals tests/test_kenobix.py && coverage report \
   --data-file=.coverage --include="**/kenobix.py"

"""

import time
from contextlib import nullcontext as does_not_raise
from functools import partial

import pytest

# Import the fast version
from kenobi import KenobiX


# Reuse the same test data as the original tests
testdata_insert_single_document = (
    (
        "insert",
        {"key": "value"},
        does_not_raise(),
        1,
        {"key": "value"},
    ),
    (
        "insert_many",
        [{"key": "value1"}, {"key": "value2"}],
        does_not_raise(),
        2,
        [{"key": "value1"}, {"key": "value2"}],
    ),
    (
        "insert",
        0.1234,
        pytest.raises(TypeError),
        0,
        {},
    ),
    (
        "insert",
        None,
        pytest.raises(TypeError),
        0,
        {},
    ),
    (
        "insert_many",
        [0.1234, 0.1234],
        pytest.raises(TypeError),
        0,
        [],
    ),
)

ids_insert_single_document = (
    "Single document",
    "Multiple documents",
    "document invalid unsupported type",
    "document invalid None",
    "Multiple documents unsupported types",
)


@pytest.fixture()
def db_path_fast(tmp_path):
    """Path to fast DB in temp folder."""
    return tmp_path.joinpath("test_kenobix.db")


@pytest.fixture()
def create_db_fast(db_path_fast, request):
    """Create KenobiX instance with indexed fields for testing.

    Usage:
        def test_something(create_db_fast):
            db = create_db_fast()  # Default indexed fields
            # or
            db = create_db_fast(['name', 'age', 'custom_field'])
    """

    def _fcn(indexed_fields=None):
        """Initialize database with optional indexed fields."""
        if indexed_fields is None:
            # Default indexed fields for tests
            indexed_fields = ['key', 'id', 'name', 'age', 'color', 'city']

        db = KenobiX(db_path_fast, indexed_fields=indexed_fields)

        def cleanup():
            """Close database after test."""
            db.close()

        request.addfinalizer(cleanup)
        return db

    return _fcn


@pytest.mark.parametrize(
    "meth, document, expectation, result_count_expected, document_expected",
    testdata_insert_single_document,
    ids=ids_insert_single_document,
)
def test_insert_single_document_fast(
    meth,
    document,
    expectation,
    result_count_expected,
    document_expected,
    create_db_fast,
):
    """Test inserting a single document with fast version."""
    db = create_db_fast()
    if hasattr(db, meth):
        fcn = getattr(db, meth)
        with expectation:
            fcn(document)

    results = db.all()
    result_count_actual = len(results)
    assert result_count_actual == result_count_expected
    if isinstance(expectation, does_not_raise):
        if isinstance(document, dict):
            assert document_expected in results
        elif isinstance(document, list):
            for d_document in document:
                assert d_document in results


testdata_remove_document = (
    (
        {"key": "value"},
        "key",
        "value",
        does_not_raise(),
        0,
    ),
    (
        {"key": "value"},
        None,
        "value",
        pytest.raises(ValueError),
        1,
    ),
    (
        {"key": "value"},
        0.12345,
        "value",
        pytest.raises(ValueError),
        1,
    ),
    (
        {"key": "value"},
        "key",
        None,
        pytest.raises(ValueError),
        1,
    ),
)
ids_remove_document = (
    "remove one document",
    "key None",
    "key unsupported type",
    "value None",
)


@pytest.mark.parametrize(
    "document, query_key, query_val, expectation, results_count_expected",
    testdata_remove_document,
    ids=ids_remove_document,
)
def test_remove_document_fast(
    document, query_key, query_val, expectation, results_count_expected, create_db_fast
):
    """Test removing a document by key:value with fast version."""
    db = create_db_fast()
    db.insert(document)
    with expectation:
        db.remove(query_key, query_val)
    results = db.all()
    results_count_actual = len(results)
    assert results_count_actual == results_count_expected


testdata_update_document = (
    (
        {"id": 1, "key": "value"},
        {"key": "new_value"},
        "id",
        1,
        "key",
        "new_value",
        does_not_raise(),
        1,
        True,
    ),
    (
        {"id": 1, "key": "value"},
        {"key": "new_value"},
        None,
        1,
        "key",
        "value",
        pytest.raises(ValueError),
        1,
        False,
    ),
    (
        {"id": 1, "key": "value"},
        {"key": "new_value"},
        "id",
        None,
        "key",
        "value",
        pytest.raises(ValueError),
        1,
        False,
    ),
    (
        {"id": 1, "key": "value"},
        {"key": "new_value"},
        "id",
        2,
        "key",
        "value",
        does_not_raise(),
        1,
        False,
    ),
)
ids_update_document = (
    "Update a document",
    "id_field None ValueError",
    "id_val None ValueError",
    "could not update nonexistent document",
)


@pytest.mark.parametrize(
    (
        "document, updated_fields, id_field, id_val, val_key, "
        "val_expected, expectation, results_count_expected, is_success_expected"
    ),
    testdata_update_document,
    ids=ids_update_document,
)
def test_update_document_fast(
    document,
    updated_fields,
    id_field,
    id_val,
    val_key,
    val_expected,
    expectation,
    results_count_expected,
    is_success_expected,
    create_db_fast,
):
    """Test updating a document by key:value with fast version."""
    db = create_db_fast()
    db.insert(document)
    with expectation:
        is_success_actual = db.update(id_field, id_val, updated_fields)
    if isinstance(expectation, does_not_raise):
        assert is_success_actual is is_success_expected
    results = db.all()
    results_count_actual = len(results)
    assert results_count_actual == results_count_expected
    val_actual = results[0][val_key]
    assert val_actual == val_expected


def test_purge_database_fast(create_db_fast):
    """Test purging all documents from the database."""
    documents = [{"key": "value1"}, {"key": "value2"}]
    results_count_expected = 0
    db = create_db_fast()
    db.insert_many(documents)
    db.purge()
    results = db.all()
    results_count_actual = len(results)
    assert results_count_actual == results_count_expected


testdata_search_by_key_value = (
    (
        [{"key": "value1"}, {"key": "value2"}],
        "key",
        "value1",
        does_not_raise(),
        1,
    ),
    (
        [{"key": "value1"}, {"key": "value2"}],
        None,
        "value1",
        pytest.raises(ValueError),
        1,
    ),
    (
        [{"key": "value1"}, {"key": "value2"}],
        0.2345,
        "value1",
        pytest.raises(ValueError),
        1,
    ),
)
ids_search_by_key_value = (
    "successful query",
    "query_key None",
    "query_key unsupported type",
)


@pytest.mark.parametrize(
    "documents, query_key, query_val, expectation, results_count_expected",
    testdata_search_by_key_value,
    ids=ids_search_by_key_value,
)
def test_search_by_key_value_fast(
    documents,
    query_key,
    query_val,
    expectation,
    results_count_expected,
    create_db_fast,
):
    """Test searching documents by key:value with fast version."""
    db = create_db_fast()
    db.insert_many(documents)
    with expectation:
        results = db.search(query_key, query_val)
    if isinstance(expectation, does_not_raise):
        results_count_actual = len(results)
        assert results_count_actual == results_count_expected
        actual_doc_0 = results[0]
        expected_doc_0 = documents[0]
        assert actual_doc_0 == expected_doc_0


def test_pagination_all_fast(create_db_fast):
    """Test paginated retrieval of all documents."""
    documents = [{"key": f"value{i}"} for i in range(10)]
    results_count_expected = 5
    db = create_db_fast()
    db.insert_many(documents)
    results = db.all(limit=5, offset=0)
    results_count_actual = len(results)
    assert results_count_actual == results_count_expected
    assert results == documents[:5]


def test_pagination_search_fast(create_db_fast):
    """Test paginated search by key:value."""
    documents = [{"key": f"value{i}"} for i in range(10)]
    results_count_expected = 1
    db = create_db_fast()
    db.insert_many(documents)
    results = db.search("key", "value1", limit=1, offset=0)
    results_count_actual = len(results)
    assert results_count_actual == results_count_expected
    assert results[0] == {"key": "value1"}


def db_task(fcn, doc):
    """Function usable by thread pool executor"""
    fcn(doc)


def test_concurrent_inserts_fast(create_db_fast):
    """Test concurrent inserts to ensure thread safety."""
    documents = [{"key": f"value{i}"} for i in range(50)]
    results_count_expected = 50
    db = create_db_fast()
    insert_task = partial(db_task, db.insert)

    with db.executor as executor:
        executor.map(insert_task, documents)

    results = db.all()
    results_count_actual = len(results)
    assert results_count_actual == results_count_expected


def test_performance_bulk_insert_fast(create_db_fast):
    """Test the performance of bulk inserting a large number of documents."""
    documents = [{"key": f"value{i}"} for i in range(1000)]
    duration_max_expected = 5
    db = create_db_fast()
    start_time = time.time()
    db.insert_many(documents)
    end_time = time.time()
    duration_actual = end_time - start_time
    assert duration_actual < duration_max_expected, "Bulk insert took too long"


def test_safe_query_handling_fast(create_db_fast):
    """Test safe handling of potentially harmful input to prevent SQL injection."""
    document = {"key": "value"}
    results_count_expected = 0
    db = create_db_fast()
    db.insert(document)
    results = db.search("key", "value OR 1=1")
    results_count_actual = len(results)
    assert (
        results_count_actual == results_count_expected
    ), "Unsafe query execution detected"


def test_indexed_search_performance(create_db_fast):
    """Test that indexed searches are actually using indexes."""
    # Insert many documents
    documents = [
        {"name": f"user_{i}", "age": 20 + (i % 50), "city": f"city_{i % 10}"}
        for i in range(1000)
    ]
    db = create_db_fast(indexed_fields=['name', 'age'])
    db.insert_many(documents)

    # Verify that indexed search uses index
    plan = db.explain('search', 'name', 'user_500')
    plan_str = str(plan[0])
    assert 'SEARCH' in plan_str or 'INDEX' in plan_str, "Should use index for 'name'"

    # Search should work and be fast
    result = db.search('name', 'user_500')
    assert len(result) == 1
    assert result[0]['name'] == 'user_500'


def test_search_optimized_multi_field(create_db_fast):
    """Test the new search_optimized method for multi-field queries."""
    documents = [
        {"name": "Alice", "age": 30, "city": "NYC"},
        {"name": "Bob", "age": 30, "city": "LA"},
        {"name": "Alice", "age": 25, "city": "NYC"},
    ]
    db = create_db_fast(indexed_fields=['name', 'age', 'city'])
    db.insert_many(documents)

    # Search with multiple fields
    results = db.search_optimized(name="Alice", age=30)
    assert len(results) == 1
    assert results[0] == {"name": "Alice", "age": 30, "city": "NYC"}

    # Search with all fields
    results = db.search_optimized(name="Alice", age=25, city="NYC")
    assert len(results) == 1
    assert results[0] == {"name": "Alice", "age": 25, "city": "NYC"}


def test_cursor_pagination(create_db_fast):
    """Test cursor-based pagination."""
    documents = [{"key": f"value{i}"} for i in range(100)]
    db = create_db_fast()
    db.insert_many(documents)

    # First page
    result = db.all_cursor(limit=10)
    assert len(result['documents']) == 10
    assert result['has_more'] is True
    assert result['next_cursor'] is not None

    # Second page
    result2 = db.all_cursor(after_id=result['next_cursor'], limit=10)
    assert len(result2['documents']) == 10
    assert result2['has_more'] is True

    # Verify no overlap
    first_ids = [doc['key'] for doc in result['documents']]
    second_ids = [doc['key'] for doc in result2['documents']]
    assert len(set(first_ids) & set(second_ids)) == 0, "No overlap between pages"


def test_get_indexed_fields(create_db_fast):
    """Test getting the list of indexed fields."""
    db = create_db_fast(indexed_fields=['name', 'age', 'email'])
    indexed = db.get_indexed_fields()
    assert 'name' in indexed
    assert 'age' in indexed
    assert 'email' in indexed


def test_stats(create_db_fast):
    """Test database statistics."""
    documents = [{"key": f"value{i}"} for i in range(100)]
    db = create_db_fast(indexed_fields=['key'])
    db.insert_many(documents)

    stats = db.stats()
    assert stats['document_count'] == 100
    assert stats['database_size_bytes'] > 0
    assert 'key' in stats['indexed_fields']
    assert stats['wal_mode'] is True


def test_find_any_indexed(create_db_fast):
    """Test find_any with indexed field (should be faster)."""
    documents = [
        {"key": "value1"},
        {"key": "value2"},
        {"key": "value3"},
        {"key": "value4"},
    ]
    db = create_db_fast(indexed_fields=['key'])
    db.insert_many(documents)

    # Find any with indexed field
    results = db.find_any('key', ['value1', 'value3', 'value5'])
    assert len(results) == 2
    keys = [doc['key'] for doc in results]
    assert 'value1' in keys
    assert 'value3' in keys
    assert 'value5' not in keys
