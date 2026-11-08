from api.sales.database import DuckDbSalesDatabase
from api.sales.guard import check_sql
from api.sales.schema import TABLES


def test_lists_every_table_with_columns_counts_and_preview(client):
    response = client.get("/sales/tables")
    assert response.status_code == 200
    body = response.json()

    assert body["company"].startswith("Sejuk Beverages")
    assert [t["name"] for t in body["tables"]] == [t.name for t in TABLES]

    orders = next(t for t in body["tables"] if t["name"] == "orders")
    assert orders["rowCount"] > 1000
    assert [c["name"] for c in orders["columns"]] == [
        "id",
        "customer_id",
        "warehouse_id",
        "order_date",
        "status",
    ]
    assert len(orders["previewRows"]) == 20
    assert all(len(row) == 5 for row in orders["previewRows"])

    warehouses = next(t for t in body["tables"] if t["name"] == "warehouses")
    assert warehouses["rowCount"] == len(warehouses["previewRows"]) == 4


def test_described_columns_match_the_real_tables():
    # Keeps the description the model and users see in step with the schema.
    db = DuckDbSalesDatabase()
    for table in TABLES:
        result = db.run(check_sql(f"select * from {table.name}", max_rows=1))
        assert result.columns == [column.name for column in table.columns], table.name


def test_result_is_cached(client):
    first = client.get("/sales/tables").json()
    services = client.app.state.services
    assert services.sales_catalog.describe() is services.sales_catalog.describe()
    assert client.get("/sales/tables").json() == first
