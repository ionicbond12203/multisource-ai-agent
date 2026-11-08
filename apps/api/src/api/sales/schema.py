"""
The sample sales database of Sejuk Beverages Sdn Bhd, a fictional Malaysian
drinks distributor. The same tables exist in Postgres (with DATABASE_URL) and
in DuckDB (offline), both in a schema called `distribution`.
"""

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

# What the model is told about the data. Keep it in sync with CREATE_TABLES and data.py.
DESCRIPTION = """\
Postgres database of Sejuk Beverages Sdn Bhd, a Malaysian drinks distributor. Data covers 1 Jan to 30 Sep 2026.
All tables are in the search path; use unqualified names.

warehouses(id, name, state)
  4 rows. id: 'WH-SA' Shah Alam (Selangor), 'WH-PG' Penang (Pulau Pinang), 'WH-JB' Johor Bahru (Johor),
  'WH-KT' Kuantan (Pahang).

customers(id, name, channel, state, city)
  Retail outlets. channel: 'supermarket' | 'convenience' | 'horeca' (hotels, restaurants, cafes) | 'wholesaler'.
  state: Malaysian state, e.g. 'Selangor', 'Kuala Lumpur', 'Pulau Pinang', 'Johor', 'Pahang', 'Perak', 'Kedah',
  'Terengganu', 'Kelantan', 'Melaka', 'Negeri Sembilan'.

products(sku, name, category, is_chilled, unit_price_myr)
  category: 'rtd_tea' | 'juice' | 'dairy_alt' | 'water' | 'carbonated' | 'isotonic'.
  is_chilled: must be kept at 2 to 8 C during delivery.

orders(id, customer_id, warehouse_id, order_date, status)
  status: 'delivered' | 'cancelled' | 'returned'. warehouse_id is the warehouse that shipped the order.

order_items(order_id, sku, quantity, unit_price_myr)
  Sales value of a line = quantity * unit_price_myr (Malaysian ringgit).

deliveries(order_id, promised_date, delivered_at, max_temp_c, temperature_excursion)
  One row per order. delivered_at is local time (MYT) and NULL for cancelled orders.
  Late delivery: delivered_at::date > promised_date.
  max_temp_c: highest reefer temperature during the trip, NULL when the order has no chilled products.
  temperature_excursion: true when chilled stock stayed above 8 C for more than 30 minutes."""
