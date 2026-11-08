from dataclasses import replace

from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app
from api.sales.catalog import SalesCatalog
from api.sales.database import DuckDbSalesDatabase, QueryFailed
from api.sales.guard import check_sql
from api.sales.schema import TABLES


def rows(client, table, **params):
    response = client.get(f"/sales/tables/{table}/rows", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_lists_every_table_with_columns_and_counts(client):
    body = client.get("/sales/tables").json()
    assert body["company"].startswith("Sejuk Beverages")
    assert [t["name"] for t in body["tables"]] == [t.name for t in TABLES]

    orders = next(t for t in body["tables"] if t["name"] == "orders")
    assert orders["rowCount"] > 1000
    assert orders["primaryKey"] == ["id"]
    assert [c["name"] for c in orders["columns"]] == [
        "id",
        "customer_id",
        "warehouse_id",
        "order_date",
        "status",
    ]

    order_items = next(t for t in body["tables"] if t["name"] == "order_items")
    assert order_items["primaryKey"] == ["order_id", "sku"]


def test_pages_cover_every_row_exactly_once(client):
    total = rows(client, "customers", limit=1)["total"]
    seen = []
    for offset in range(0, total, 20):
        seen += [row[0] for row in rows(client, "customers", offset=offset, limit=20)["rows"]]
    assert len(seen) == total == len(set(seen))
    assert seen == sorted(seen)  # default order is the primary key


def test_page_shape(client):
    page = rows(client, "orders", offset=100, limit=25)
    assert page["columns"] == ["id", "customer_id", "warehouse_id", "order_date", "status"]
    assert len(page["rows"]) == 25
    assert page["offset"] == 100 and page["limit"] == 25 and page["order"] == "asc"
    assert page["total"] > 1000
    assert "sort" not in page  # null fields are left out


def test_sorting_by_a_column(client):
    by_price = rows(client, "products", sort="unit_price_myr", order="desc", limit=100)
    prices = [row[4] for row in by_price["rows"]]
    assert prices == sorted(prices, reverse=True)
    assert by_price["sort"] == "unit_price_myr"


def test_sorting_keeps_nulls_last_and_pages_stable(client):
    first = rows(client, "deliveries", sort="delivered_at", order="desc", limit=10)
    assert all(row[2] is not None for row in first["rows"])
    # A sort with many ties (true/false) still pages without repeats, thanks to the key tie-breaker.
    a = rows(client, "deliveries", sort="temperature_excursion", limit=50)["rows"]
    b = rows(client, "deliveries", sort="temperature_excursion", offset=50, limit=50)["rows"]
    assert not {row[0] for row in a} & {row[0] for row in b}


def test_unknown_table_or_column_is_rejected(client):
    assert client.get("/sales/tables/documents/rows").status_code == 404
    response = client.get("/sales/tables/orders/rows", params={"sort": "id; drop table orders"})
    assert response.status_code == 422
    assert "Unknown column" in response.json()["detail"]
    assert client.get("/sales/tables/orders/rows", params={"limit": 1000}).status_code == 422
    assert client.get("/sales/tables/orders/rows", params={"order": "sideways"}).status_code == 422


def test_paging_has_its_own_rate_limit():
    settings = Settings(
        chat_per_client_per_minute=0,
        chat_per_client_per_day=0,
        chat_per_minute=0,
        uploads_per_client_per_hour=0,
        browse_per_client_per_minute=2,
        _env_file=None,
    )
    client = TestClient(create_app(settings))
    assert [client.get("/sales/tables/orders/rows").status_code for _ in range(3)] == [200, 200, 429]


def test_described_columns_match_the_real_tables():
    # Keeps the description the model and users see in step with the schema.
    db = DuckDbSalesDatabase()
    for table in TABLES:
        result = db.run(check_sql(f"select * from {table.name}", max_rows=1))
        assert result.columns == table.column_names(), table.name


def test_table_list_is_cached(client):
    catalog = client.app.state.services.sales_catalog
    assert catalog.describe() is catalog.describe()


class BrokenDatabase:
    def run(self, sql):
        raise QueryFailed("consuming input failed: server closed the connection unexpectedly")


def test_database_failure_is_a_clear_503_not_a_crash(settings):
    app = create_app(settings)
    services = app.state.services
    app.state.services = replace(services, sales_catalog=SalesCatalog(BrokenDatabase()))
    client = TestClient(app)

    for url in ("/sales/tables", "/sales/tables/orders/rows"):
        response = client.get(url, headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 503
        assert response.json()["detail"] == "The database didn't answer. Try again in a moment."
        # Handled errors keep CORS headers, so the browser shows the message instead of a CORS error.
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
