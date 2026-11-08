import pytest

from api.sales.data import generate
from api.sales.database import DuckDbSalesDatabase, QueryFailed
from api.sales.guard import check_sql
from api.sales.schema import ALLOWED_TABLES


@pytest.fixture(scope="module")
def db():
    return DuckDbSalesDatabase()


def run(db, sql):
    return db.run(check_sql(sql, max_rows=200))


def test_data_is_deterministic():
    assert generate() == generate()
    assert set(generate()) == ALLOWED_TABLES


def test_every_order_has_one_delivery(db):
    [(orders, deliveries)] = run(
        db, "select (select count(*) from orders), (select count(*) from deliveries)"
    ).rows
    assert orders == deliveries > 1000


def test_cancelled_orders_have_no_delivery_time(db):
    [(count,)] = run(
        db,
        "select count(*) from orders o join deliveries d on d.order_id = o.id "
        "where o.status = 'cancelled' and d.delivered_at is not null",
    ).rows
    assert count == 0


def test_built_in_patterns(db):
    # Kuantan (Pahang) is late most often in Q1 because of the monsoon.
    late = run(
        db,
        "select w.state from deliveries d join orders o on o.id = d.order_id "
        "join warehouses w on w.id = o.warehouse_id "
        "where o.status <> 'cancelled' and extract(quarter from o.order_date) = 1 "
        "and d.delivered_at::date > d.promised_date group by 1 order by count(*) desc limit 1",
    )
    assert late.rows == [("Pahang",)]

    # Penang has the most temperature excursions in August.
    excursions = run(
        db,
        "select o.warehouse_id from deliveries d join orders o on o.id = d.order_id "
        "where d.temperature_excursion and extract(month from o.order_date) = 8 "
        "group by 1 order by count(*) desc limit 1",
    )
    assert excursions.rows == [("WH-PG",)]


def test_values_are_json_friendly(db):
    [row] = run(db, "select unit_price_myr, is_chilled from products where sku = 'JCE-ORG-1L'").rows
    assert row == (8.9, True)


def test_database_itself_is_read_only(db):
    # Even SQL that skipped the guard can't change anything.
    with pytest.raises(QueryFailed, match="read-only"):
        db.run("delete from distribution.orders")
