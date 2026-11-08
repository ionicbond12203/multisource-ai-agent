"""
Generates the sample sales data. Deterministic: the same seed always gives the
same rows, so tests and the live demo agree on the numbers.

A few patterns are built in so questions have interesting answers:
- Sales rise in February and March (Ramadan and Hari Raya Aidilfitri).
- Kuantan (east coast) delivers late more often in January to March (monsoon).
- Penang has more temperature excursions in August (a faulty reefer truck).
"""

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

Row = tuple[object, ...]

WAREHOUSES: list[Row] = [
    ("WH-SA", "Shah Alam DC", "Selangor"),
    ("WH-PG", "Penang DC", "Pulau Pinang"),
    ("WH-JB", "Johor Bahru DC", "Johor"),
    ("WH-KT", "Kuantan DC", "Pahang"),
]

# (state, city, serving warehouse)
LOCATIONS = [
    ("Selangor", "Shah Alam", "WH-SA"),
    ("Selangor", "Petaling Jaya", "WH-SA"),
    ("Selangor", "Klang", "WH-SA"),
    ("Kuala Lumpur", "Kuala Lumpur", "WH-SA"),
    ("Negeri Sembilan", "Seremban", "WH-SA"),
    ("Perak", "Ipoh", "WH-PG"),
    ("Pulau Pinang", "George Town", "WH-PG"),
    ("Pulau Pinang", "Bukit Mertajam", "WH-PG"),
    ("Kedah", "Alor Setar", "WH-PG"),
    ("Johor", "Johor Bahru", "WH-JB"),
    ("Johor", "Batu Pahat", "WH-JB"),
    ("Melaka", "Melaka", "WH-JB"),
    ("Pahang", "Kuantan", "WH-KT"),
    ("Terengganu", "Kuala Terengganu", "WH-KT"),
    ("Kelantan", "Kota Bharu", "WH-KT"),
]

CHANNEL_NAMES = {
    "supermarket": ["SegarMart", "Pasaraya Harmoni", "FamilyFresh"],
    "convenience": ["QuickStop", "Kedai 24", "MiniMart Ceria"],
    "horeca": ["Kafe Sentosa", "Hotel Seri Bayu", "Restoran Selera"],
    "wholesaler": ["Borong Jaya", "Grosir Mutiara"],
}

PRODUCTS: list[Row] = [
    ("TEA-GRN-500", "Teh Hijau RTD 500ml", "rtd_tea", True, Decimal("3.20")),
    ("TEA-TRK-300", "Teh Tarik RTD 300ml", "rtd_tea", True, Decimal("2.80")),
    ("TEA-LMN-500", "Lemon Tea 500ml", "rtd_tea", False, Decimal("2.60")),
    ("JCE-ORG-1L", "Orange Juice 1L", "juice", True, Decimal("8.90")),
    ("JCE-APL-1L", "Apple Juice 1L", "juice", True, Decimal("8.50")),
    ("JCE-MGO-330", "Mango Juice 330ml", "juice", True, Decimal("3.50")),
    ("SOY-1L", "Soya Bean Drink 1L", "dairy_alt", True, Decimal("5.40")),
    ("COC-330", "Coconut Water 330ml", "juice", True, Decimal("4.20")),
    ("WTR-1500", "Mineral Water 1.5L", "water", False, Decimal("1.90")),
    ("SPK-LIM-330", "Sparkling Lime 330ml", "carbonated", False, Decimal("2.40")),
    ("ISO-500", "Isotonic Drink 500ml", "isotonic", False, Decimal("3.00")),
    ("BAR-300", "Barley Drink 300ml", "rtd_tea", False, Decimal("2.20")),
]
CHILLED_SKUS = {sku for sku, _, _, chilled, _ in PRODUCTS if chilled}
PRICES = {sku: price for sku, _, _, _, price in PRODUCTS}

START, END = date(2026, 1, 1), date(2026, 9, 30)
# Relative order volume per month (Ramadan Feb-Mar 2026, Hari Raya around 20 March).
MONTH_WEIGHT = {1: 1.0, 2: 1.25, 3: 1.45, 4: 1.0, 5: 0.95, 6: 1.0, 7: 1.05, 8: 1.1, 9: 1.0}


def generate(seed: int = 2026) -> dict[str, list[Row]]:
    rng = random.Random(seed)
    customers = _customers(rng)
    orders: list[Row] = []
    items: list[Row] = []
    deliveries: list[Row] = []

    order_id = 1000
    day = START
    while day <= END:
        weekday_factor = 0.4 if day.weekday() == 6 else 1.0  # few Sunday orders
        expected = 6.0 * MONTH_WEIGHT[day.month] * weekday_factor
        for _ in range(_poisson(rng, expected)):
            order_id += 1
            customer_id, _, channel, _, _, warehouse_id = rng.choice(customers)
            status = rng.choices(["delivered", "cancelled", "returned"], [94, 4, 2])[0]
            orders.append((order_id, customer_id, warehouse_id, day, status))
            skus = _order_items(rng, order_id, channel, items)
            deliveries.append(_delivery(rng, order_id, day, warehouse_id, status, skus))
        day += timedelta(days=1)

    return {
        "warehouses": WAREHOUSES,
        "customers": [customer[:5] for customer in customers],
        "products": PRODUCTS,
        "orders": orders,
        "order_items": items,
        "deliveries": deliveries,
    }


# ---------- helpers ----------


def _customers(rng: random.Random) -> list[tuple[str, str, str, str, str, str]]:
    """Returns (id, name, channel, state, city, serving warehouse) for every outlet."""
    result = []
    for state, city, warehouse in LOCATIONS:
        for channel, names in CHANNEL_NAMES.items():
            if channel == "wholesaler" and rng.random() < 0.5:
                continue
            customer_id = f"C{len(result) + 1:03d}"
            result.append((customer_id, f"{rng.choice(names)} {city}", channel, state, city, warehouse))
    return result


def _order_items(rng: random.Random, order_id: int, channel: str, items: list[Row]) -> list[str]:
    scale = {"wholesaler": 8, "supermarket": 4, "horeca": 2, "convenience": 1}[channel]
    skus = rng.sample([p[0] for p in PRODUCTS], k=rng.randint(2, 5))
    for sku in skus:
        quantity = rng.randint(1, 6) * 12 * scale  # cartons of 12
        items.append((order_id, sku, quantity, PRICES[sku]))
    return skus


def _delivery(
    rng: random.Random, order_id: int, day: date, warehouse: str, status: str, skus: list[str]
) -> Row:
    promised = day + timedelta(days=2 if warehouse != "WH-KT" else 3)
    has_chilled = any(sku in CHILLED_SKUS for sku in skus)

    if status == "cancelled":
        return (order_id, promised, None, None, False)

    late_chance = 0.06
    if warehouse == "WH-KT" and day.month in (1, 2, 3):
        late_chance = 0.30  # north-east monsoon
    delay_days = rng.choice([1, 1, 2, 3]) if rng.random() < late_chance else -rng.choice([0, 0, 1])
    delivered_day = promised + timedelta(days=delay_days)
    delivered_at = datetime.combine(delivered_day, time(rng.randint(8, 18), rng.choice([0, 15, 30, 45])))

    if not has_chilled:
        return (order_id, promised, delivered_at, None, False)

    excursion_chance = 0.03
    if warehouse == "WH-PG" and day.month == 8:
        excursion_chance = 0.25  # faulty reefer truck
    excursion = rng.random() < excursion_chance
    max_temp = round(rng.uniform(8.6, 12.5) if excursion else rng.uniform(3.0, 7.8), 1)
    return (order_id, promised, delivered_at, Decimal(str(max_temp)), excursion)


def _poisson(rng: random.Random, mean: float) -> int:
    # Knuth's method; fine for small means.
    limit, count, product = pow(2.718281828, -mean), 0, rng.random()
    while product > limit:
        count += 1
        product *= rng.random()
    return count
