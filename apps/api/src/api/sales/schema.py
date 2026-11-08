"""
The sample sales database of Sejuk Beverages Sdn Bhd, a fictional Malaysian
drinks distributor. The same tables exist in Postgres (with DATABASE_URL) and
in DuckDB (offline), both in a schema called `distribution`.
"""

from dataclasses import dataclass

SCHEMA = "distribution"

# Tables the SQL agent may read. Anything else is rejected before it runs.
ALLOWED_TABLES = frozenset({"warehouses", "customers", "products", "orders", "order_items", "deliveries"})

# Portable DDL: runs unchanged on Postgres and DuckDB.
CREATE_TABLES = f"""
create schema if not exists {SCHEMA};

create table if not exists {SCHEMA}.warehouses (
    id     text primary key,
    name   text not null,
    state  text not null
);

create table if not exists {SCHEMA}.customers (
    id       text primary key,
    name     text not null,
    channel  text not null,
    state    text not null,
    city     text not null
);

create table if not exists {SCHEMA}.products (
    sku             text primary key,
    name            text not null,
    category        text not null,
    is_chilled      boolean not null,
    unit_price_myr  numeric(10, 2) not null
);

create table if not exists {SCHEMA}.orders (
    id            integer primary key,
    customer_id   text not null references {SCHEMA}.customers (id),
    warehouse_id  text not null references {SCHEMA}.warehouses (id),
    order_date    date not null,
    status        text not null
);

create table if not exists {SCHEMA}.order_items (
    order_id        integer not null references {SCHEMA}.orders (id),
    sku             text not null references {SCHEMA}.products (sku),
    quantity        integer not null,
    unit_price_myr  numeric(10, 2) not null,
    primary key (order_id, sku)
);

create table if not exists {SCHEMA}.deliveries (
    order_id               integer primary key references {SCHEMA}.orders (id),
    promised_date          date not null,
    delivered_at           timestamp,
    max_temp_c             numeric(4, 1),
    temperature_excursion  boolean not null
);
"""

# Insert order matters because of the foreign keys.
TABLE_ORDER = ("warehouses", "customers", "products", "orders", "order_items", "deliveries")

COMPANY = "Sejuk Beverages Sdn Bhd, a fictional Malaysian drinks distributor"
PERIOD = "1 January to 30 September 2026"


@dataclass(frozen=True)
class Column:
    name: str
    type: str  # as in CREATE_TABLES
    description: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    description: str
    columns: tuple[Column, ...]
    # Primary key columns; the default row order. Empty means the first column.
    key: tuple[str, ...] = ()

    @property
    def primary_key(self) -> tuple[str, ...]:
        return self.key or (self.columns[0].name,)

    def column_names(self) -> list[str]:
        return [column.name for column in self.columns]


def find_table(name: str) -> Table | None:
    return next((table for table in TABLES if table.name == name), None)


# The single description of the data: the model reads it (as DESCRIPTION) to
# write SQL, and GET /sales/tables shows it to users. A test checks it matches
# the real columns, so keep it in step with CREATE_TABLES and data.py.
TABLES: tuple[Table, ...] = (
    Table(
        "warehouses",
        "Distribution centres that ship the orders.",
        (
            Column(
                "id",
                "text",
                "'WH-SA' Shah Alam (Selangor), 'WH-PG' Penang (Pulau Pinang), 'WH-JB' Johor Bahru (Johor), "
                "'WH-KT' Kuantan (Pahang)",
            ),
            Column("name", "text"),
            Column("state", "text", "Malaysian state the warehouse is in"),
        ),
    ),
    Table(
        "customers",
        "Retail outlets that order drinks.",
        (
            Column("id", "text"),
            Column("name", "text"),
            Column(
                "channel",
                "text",
                "'supermarket' | 'convenience' | 'horeca' (hotels, restaurants, cafes) | 'wholesaler'",
            ),
            Column(
                "state",
                "text",
                "Malaysian state, e.g. 'Selangor', 'Kuala Lumpur', 'Pulau Pinang', 'Johor', 'Pahang', 'Perak', "
                "'Kedah', 'Terengganu', 'Kelantan', 'Melaka', 'Negeri Sembilan'",
            ),
            Column("city", "text"),
        ),
    ),
    Table(
        "products",
        "Drinks on sale.",
        (
            Column("sku", "text"),
            Column("name", "text"),
            Column(
                "category", "text", "'rtd_tea' | 'juice' | 'dairy_alt' | 'water' | 'carbonated' | 'isotonic'"
            ),
            Column("is_chilled", "boolean", "must be kept at 2 to 8 C during delivery"),
            Column("unit_price_myr", "numeric(10, 2)", "list price in Malaysian ringgit"),
        ),
    ),
    Table(
        "orders",
        "One row per customer order.",
        (
            Column("id", "integer"),
            Column("customer_id", "text", "customers.id"),
            Column("warehouse_id", "text", "warehouses.id, the warehouse that shipped the order"),
            Column("order_date", "date"),
            Column("status", "text", "'delivered' | 'cancelled' | 'returned'"),
        ),
    ),
    Table(
        "order_items",
        "Products in each order. Sales value of a line = quantity * unit_price_myr (Malaysian ringgit).",
        (
            Column("order_id", "integer", "orders.id"),
            Column("sku", "text", "products.sku"),
            Column("quantity", "integer", "bottles"),
            Column("unit_price_myr", "numeric(10, 2)", "price charged per bottle"),
        ),
        key=("order_id", "sku"),
    ),
    Table(
        "deliveries",
        "One row per order. Late delivery: delivered_at::date > promised_date.",
        (
            Column("order_id", "integer", "orders.id"),
            Column("promised_date", "date"),
            Column("delivered_at", "timestamp", "local time (MYT); NULL for cancelled orders"),
            Column(
                "max_temp_c",
                "numeric(4, 1)",
                "highest reefer temperature during the trip; NULL when the order has no chilled products",
            ),
            Column(
                "temperature_excursion",
                "boolean",
                "true when chilled stock stayed above 8 C for more than 30 minutes",
            ),
        ),
    ),
)


def _describe_for_model() -> str:
    lines = [
        f"Postgres database of {COMPANY}. Data covers {PERIOD}.",
        "All tables are in the search path; use unqualified names.",
    ]
    for table in TABLES:
        lines.append("")
        lines.append(f"{table.name}({', '.join(column.name for column in table.columns)})")
        lines.append(f"  {table.description}")
        lines += [f"  {column.name}: {column.description}." for column in table.columns if column.description]
    return "\n".join(lines)


# What the model is told about the data when it writes SQL.
DESCRIPTION = _describe_for_model()
