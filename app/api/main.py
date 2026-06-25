import os
from contextlib import contextmanager

import psycopg2
from fastapi import FastAPI, HTTPException, Path, Query

DB_CONN = os.getenv(
    "POSTGRES_CONN",
    "postgresql://postgres:postgres@postgres:5432/warehouse",
)

app = FastAPI(
    title="Edikted Shipments API",
    description="Query shipment data from the Edikted data warehouse.",
    version="1.0.0",
)


@contextmanager
def get_db():
    conn = psycopg2.connect(DB_CONN)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Required endpoint
# ---------------------------------------------------------------------------

@app.get(
    "/total_weight",
    summary="Total billable weight and charge for a carrier on a given date",
    tags=["required"],
)
def total_weight(
    carrier: str = Query(..., description="Carrier name (case-sensitive)"),
    date: str = Query(..., description="Date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    SUM(weight_billable) AS total_billable_weight,
                    SUM(total_charge)    AS total_charge
                FROM fact.fact_shipments
                WHERE carrier = %s
                  AND "date" = %s::date
                """,
                (carrier, date),
            )
            row = cur.fetchone()

    return {
        "carrier": carrier,
        "date": date,
        "total_billable_weight": float(row[0]) if row[0] is not None else None,
        "total_charge": float(row[1]) if row[1] is not None else None,
    }


# ---------------------------------------------------------------------------
# Enriched endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/carriers", summary="All carriers with aggregate stats", tags=["enriched"])
def list_carriers():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    carrier,
                    COUNT(*)                                      AS shipments,
                    ROUND(SUM(total_charge)::numeric, 2)          AS total_charge,
                    ROUND(SUM(weight_billable)::numeric, 2)       AS total_weight_lbs
                FROM fact.fact_shipments
                WHERE carrier IS NOT NULL
                GROUP BY carrier
                ORDER BY total_charge DESC NULLS LAST
                """
            )
            rows = cur.fetchall()

    return [
        {
            "carrier": r[0],
            "shipments": r[1],
            "total_charge": float(r[2]) if r[2] is not None else None,
            "total_weight_lbs": float(r[3]) if r[3] is not None else None,
        }
        for r in rows
    ]


@app.get(
    "/carriers/{carrier}/summary",
    summary="Detailed stats for a single carrier",
    tags=["enriched"],
)
def carrier_summary(carrier: str = Path(...)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)                                                             AS shipments,
                    ROUND(SUM(total_charge)::numeric, 2)                                AS total_charge,
                    ROUND(SUM(weight_billable)::numeric, 2)                             AS total_weight_lbs,
                    ROUND(AVG(total_charge)::numeric, 4)                                AS avg_charge,
                    ROUND((SUM(total_charge) / NULLIF(SUM(weight_billable),0))::numeric, 4)
                                                                                        AS charge_per_lb,
                    MIN("date")::text                                                   AS first_date,
                    MAX("date")::text                                                   AS last_date,
                    COUNT(DISTINCT service)                                              AS services
                FROM fact.fact_shipments
                WHERE carrier = %s
                """,
                (carrier,),
            )
            row = cur.fetchone()

    if not row or row[0] == 0:
        raise HTTPException(status_code=404, detail=f"Carrier '{carrier}' not found")

    return {
        "carrier": carrier,
        "shipments": row[0],
        "total_charge": float(row[1]) if row[1] is not None else None,
        "total_weight_lbs": float(row[2]) if row[2] is not None else None,
        "avg_charge": float(row[3]) if row[3] is not None else None,
        "charge_per_lb": float(row[4]) if row[4] is not None else None,
        "first_date": row[5],
        "last_date": row[6],
        "services": row[7],
    }


@app.get(
    "/top-dates",
    summary="Top N dates by shipment count, total value, or total weight",
    tags=["enriched"],
)
def top_dates(
    metric: str = Query("shipments", enum=["shipments", "value", "weight"]),
    limit: int = Query(3, ge=1, le=50),
):
    queries = {
        "shipments": (
            'SELECT "date"::text, COUNT(*) FROM fact.fact_shipments WHERE "date" IS NOT NULL GROUP BY "date" ORDER BY 2 DESC LIMIT %s',
            "shipments",
        ),
        "value": (
            'SELECT "date"::text, ROUND(SUM(total_charge)::numeric,2) FROM fact.fact_shipments WHERE "date" IS NOT NULL AND total_charge IS NOT NULL GROUP BY "date" ORDER BY 2 DESC LIMIT %s',
            "total_charge",
        ),
        "weight": (
            'SELECT "date"::text, ROUND(SUM(weight_billable)::numeric,2) FROM fact.fact_shipments WHERE "date" IS NOT NULL AND weight_billable IS NOT NULL GROUP BY "date" ORDER BY 2 DESC LIMIT %s',
            "total_weight_lbs",
        ),
    }
    sql, label = queries[metric]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

    return {
        "metric": metric,
        "label": label,
        "results": [{"date": r[0], label: float(r[1])} for r in rows],
    }


@app.get("/cities", summary="Top cities by total charge", tags=["enriched"])
def top_cities(limit: int = Query(3, ge=1, le=100)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    receiver_city,
                    COUNT(*)                                AS shipments,
                    ROUND(SUM(total_charge)::numeric, 2)   AS total_charge,
                    ROUND(SUM(weight_billable)::numeric, 2) AS total_weight_lbs
                FROM fact.fact_shipments
                WHERE receiver_city IS NOT NULL AND total_charge IS NOT NULL
                GROUP BY receiver_city
                ORDER BY total_charge DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "city": r[0],
            "shipments": r[1],
            "total_charge": float(r[2]) if r[2] is not None else None,
            "total_weight_lbs": float(r[3]) if r[3] is not None else None,
        }
        for r in rows
    ]


@app.get(
    "/charge-weight-ratio",
    summary="Charge per lb by carrier and service, ranked",
    tags=["enriched"],
)
def charge_weight_ratio(limit: int = Query(10, ge=1, le=100)):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    carrier,
                    service,
                    ROUND((SUM(total_charge) / NULLIF(SUM(weight_billable),0))::numeric, 4) AS charge_per_lb,
                    ROUND(SUM(total_charge)::numeric, 2)                                    AS total_charge,
                    ROUND(SUM(weight_billable)::numeric, 2)                                 AS total_weight_lbs,
                    COUNT(*)                                                                 AS shipments
                FROM fact.fact_shipments
                WHERE carrier IS NOT NULL AND service IS NOT NULL
                  AND total_charge IS NOT NULL AND weight_billable IS NOT NULL
                GROUP BY carrier, service
                HAVING SUM(weight_billable) > 0
                ORDER BY charge_per_lb DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "carrier": r[0],
            "service": r[1],
            "charge_per_lb": float(r[2]) if r[2] is not None else None,
            "total_charge": float(r[3]) if r[3] is not None else None,
            "total_weight_lbs": float(r[4]) if r[4] is not None else None,
            "shipments": r[5],
        }
        for r in rows
    ]
