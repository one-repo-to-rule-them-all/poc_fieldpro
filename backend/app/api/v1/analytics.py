"""Analytics API router — dashboard metrics, completion rates, and revenue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import (
    CurrentTenantId,
    CurrentUser,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _parse_date_param(
    value: str | None,
    param_name: str,
    end_of_day: bool = False,
) -> datetime | None:
    """Parse an ISO date string to a timezone-aware datetime, or None.

    When end_of_day=True and the input is a bare date (no time component),
    the time is set to 23:59:59 so the full day is included in range queries.
    """
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        if end_of_day and "T" not in value and "t" not in value:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{param_name}' must be a valid ISO date or datetime string",
        ) from err


# --------------------------------------------------------------------------- #
# GET /dashboard
# --------------------------------------------------------------------------- #

@router.get("/dashboard")
async def get_dashboard(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    date_from: Annotated[str | None, Query(description="ISO date/datetime, inclusive")] = None,
    date_to: Annotated[str | None, Query(description="ISO date/datetime, inclusive")] = None,
):
    """
    Return high-level KPI metrics for the tenant dashboard.

    Returned structure:
    {
        "work_orders": {
            "total": N,
            "scheduled": N,
            "in_progress": N,
            "completed_today": N,
            "overdue": N
        },
        "active_check_ins": N,
        "outstanding_balance": "1234.56",
        "completion_rate_30d": 94.5
    }
    """
    now = datetime.now(tz=UTC)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    dt_from = _parse_date_param(date_from, "date_from")
    dt_to = _parse_date_param(date_to, "date_to")

    tid = str(tenant_id)

    # --- Work order status counts -----------------------------------------
    wo_counts_sql = text("""
        SELECT
            COUNT(*)                                                         AS total,
            COUNT(*) FILTER (WHERE status = 'scheduled')                    AS scheduled,
            COUNT(*) FILTER (WHERE status = 'in_progress')                  AS in_progress,
            COUNT(*) FILTER (
                WHERE status = 'completed'
                  AND actual_end_time >= :start_of_today
                  AND actual_end_time <= :end_of_today
            )                                                                AS completed_today,
            COUNT(*) FILTER (
                WHERE sla_deadline < :now
                  AND status NOT IN ('completed', 'cancelled')
                  AND deleted_at IS NULL
            )                                                                AS overdue
        FROM work_orders
        WHERE tenant_id = :tenant_id
          AND deleted_at IS NULL
          AND (
              CAST(:dt_from AS timestamptz) IS NULL
              OR scheduled_date >= CAST(:dt_from AS timestamptz)
          )
          AND (
              CAST(:dt_to AS timestamptz) IS NULL
              OR scheduled_date <= CAST(:dt_to AS timestamptz)
          )
    """)

    wo_row = (
        await db.execute(
            wo_counts_sql,
            {
                "tenant_id": tid,
                "now": now,
                "start_of_today": start_of_today,
                "end_of_today": end_of_today,
                "dt_from": dt_from,
                "dt_to": dt_to,
            },
        )
    ).mappings().one()

    # --- Active check-ins (checked in, not yet checked out) ---------------
    active_checkins_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM work_order_check_ins ci
        JOIN work_orders wo ON wo.id = ci.work_order_id
        WHERE wo.tenant_id = :tenant_id
          AND wo.deleted_at IS NULL
          AND ci.check_out_time IS NULL
    """)
    active_checkins = (
        await db.execute(active_checkins_sql, {"tenant_id": tid})
    ).scalar_one()

    # --- Outstanding balance (invoiced but not fully paid) ----------------
    balance_sql = text("""
        SELECT COALESCE(SUM(inv.total - COALESCE(paid.amount_paid, 0)), 0) AS outstanding
        FROM invoices inv
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS amount_paid
            FROM payments
            GROUP BY invoice_id
        ) paid ON paid.invoice_id = inv.id
        WHERE inv.tenant_id = :tenant_id
          AND inv.deleted_at IS NULL
          AND inv.status NOT IN ('void', 'paid')
    """)
    outstanding = (
        await db.execute(balance_sql, {"tenant_id": tid})
    ).scalar_one()

    # --- Completion rate over last 30 days --------------------------------
    thirty_days_ago = now - timedelta(days=settings.ANALYTICS_DEFAULT_LOOKBACK_DAYS)
    completion_sql = text("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed') AS completed_count,
            COUNT(*) FILTER (WHERE status IN ('completed', 'cancelled')) AS closed_count
        FROM work_orders
        WHERE tenant_id = :tenant_id
          AND deleted_at IS NULL
          AND created_at >= :since
    """)
    comp_row = (
        await db.execute(completion_sql, {"tenant_id": tid, "since": thirty_days_ago})
    ).mappings().one()

    if comp_row["closed_count"] and comp_row["closed_count"] > 0:
        completion_rate_30d = round(
            (comp_row["completed_count"] / comp_row["closed_count"]) * 100, 2
        )
    else:
        completion_rate_30d = 0.0

    return {
        "data": {
            "work_orders": {
                "total": wo_row["total"],
                "scheduled": wo_row["scheduled"],
                "in_progress": wo_row["in_progress"],
                "completed_today": wo_row["completed_today"],
                "overdue": wo_row["overdue"],
            },
            "active_check_ins": active_checkins,
            "outstanding_balance": str(round(outstanding, 2)),
            "completion_rate_30d": completion_rate_30d,
        }
    }


# --------------------------------------------------------------------------- #
# GET /completion-rate
# --------------------------------------------------------------------------- #

@router.get("/completion-rate")
async def get_completion_rate(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    crew_id: Annotated[uuid.UUID | None, Query()] = None,
    location_id: Annotated[uuid.UUID | None, Query()] = None,
):
    """
    Return the completion rate for work orders in the given date range,
    optionally filtered by crew and/or location.

    Response:
    {
        "data": {
            "total_work_orders": N,
            "completed": N,
            "cancelled": N,
            "completion_rate": 94.5,
            "date_from": "...",
            "date_to": "..."
        }
    }
    """
    now = datetime.now(tz=UTC)
    dt_from = _parse_date_param(date_from, "date_from") or (
        now - timedelta(days=settings.ANALYTICS_DEFAULT_LOOKBACK_DAYS)
    )
    dt_to = _parse_date_param(date_to, "date_to") or now

    tid = str(tenant_id)
    crew_id_str = str(crew_id) if crew_id else None
    location_id_str = str(location_id) if location_id else None

    sql = text("""
        SELECT
            COUNT(*)                                                          AS total,
            COUNT(*) FILTER (WHERE status = 'completed')                     AS completed,
            COUNT(*) FILTER (WHERE status = 'cancelled')                     AS cancelled
        FROM work_orders
        WHERE tenant_id = :tenant_id
          AND deleted_at IS NULL
          AND created_at >= :dt_from
          AND created_at <= :dt_to
          AND (:crew_id IS NULL     OR crew_id::text     = :crew_id)
          AND (:location_id IS NULL OR location_id::text = :location_id)
    """)

    row = (
        await db.execute(
            sql,
            {
                "tenant_id": tid,
                "dt_from": dt_from,
                "dt_to": dt_to,
                "crew_id": crew_id_str,
                "location_id": location_id_str,
            },
        )
    ).mappings().one()

    closed = (row["completed"] or 0) + (row["cancelled"] or 0)
    completion_rate = round((row["completed"] / closed) * 100, 2) if closed > 0 else 0.0

    return {
        "data": {
            "total_work_orders": row["total"],
            "completed": row["completed"],
            "cancelled": row["cancelled"],
            "completion_rate": completion_rate,
            "date_from": dt_from.isoformat(),
            "date_to": dt_to.isoformat(),
        }
    }


# --------------------------------------------------------------------------- #
# GET /revenue
# --------------------------------------------------------------------------- #

@router.get("/revenue")
async def get_revenue(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    months: Annotated[
        int, Query(ge=1, le=24, description="Number of calendar months to include")
    ] = 12,
):
    """
    Return monthly revenue totals for the past N months (default 12).

    Revenue is computed from non-voided invoices' totals, grouped by
    calendar month of issue_date.

    Response:
    {
        "data": [
            {"month": "2025-05", "invoiced": "4500.00", "collected": "3200.00"},
            ...
        ]
    }
    """
    tid = str(tenant_id)

    sql = text("""
        SELECT
            TO_CHAR(inv.issue_date AT TIME ZONE 'UTC', 'YYYY-MM')         AS month,
            COALESCE(SUM(inv.total), 0)                                    AS invoiced,
            COALESCE(SUM(COALESCE(paid.amount_paid, 0)), 0)               AS collected
        FROM invoices inv
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS amount_paid
            FROM payments
            GROUP BY invoice_id
        ) paid ON paid.invoice_id = inv.id
        WHERE inv.tenant_id = :tenant_id
          AND inv.deleted_at IS NULL
          AND inv.status != 'void'
          AND inv.issue_date >= (
              DATE_TRUNC('month', NOW() AT TIME ZONE 'UTC') - INTERVAL '1 month' * (:months - 1)
          )
        GROUP BY month
        ORDER BY month ASC
    """)

    rows = (
        await db.execute(sql, {"tenant_id": tid, "months": months})
    ).mappings().all()

    result = [
        {
            "month": row["month"],
            "invoiced": str(round(row["invoiced"], 2)),
            "collected": str(round(row["collected"], 2)),
        }
        for row in rows
    ]

    return {"data": result}


# --------------------------------------------------------------------------- #
# GET /kpis
# --------------------------------------------------------------------------- #

@router.get("/kpis")
async def get_kpis(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: Annotated[str | None, Query()] = None,
):
    """
    Return the 8 KPI fields consumed by the dashboard overview cards.

    Response matches the KPIData TypeScript interface:
    {
        "active_work_orders": N,
        "completed_today": N,
        "completion_rate": 0.94,       # fraction 0-1, selected range
        "sla_compliance": 0.97,        # fraction 0-1, selected range
        "outstanding_invoices": 1234.56,
        "total_revenue_mtd": 9800.00,
        "crew_utilization": 0.6,       # actual hours worked / scheduled hours, range-filtered
        "avg_time_on_site_minutes": 47
    }
    """
    now = datetime.now(tz=UTC)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    dt_from = _parse_date_param(from_, "from") or (
        now - timedelta(days=settings.ANALYTICS_DEFAULT_LOOKBACK_DAYS)
    )
    dt_to = _parse_date_param(to, "to", end_of_day=True) or now

    tid = str(tenant_id)

    # --- Active WOs and completed-today -------------------------------------
    wo_sql = text("""
        SELECT
            COUNT(*) FILTER (WHERE status IN ('scheduled', 'in_progress')) AS active_work_orders,
            COUNT(*) FILTER (
                WHERE status = 'completed'
                  AND actual_end_time >= :start_of_today
                  AND actual_end_time <= :end_of_today
            ) AS completed_today
        FROM work_orders
        WHERE tenant_id = :tenant_id
          AND deleted_at IS NULL
    """)
    wo_row = (
        await db.execute(wo_sql, {
            "tenant_id": tid,
            "start_of_today": start_of_today,
            "end_of_today": end_of_today,
        })
    ).mappings().one()

    # --- Completion rate and SLA compliance (selected range) ----------------
    rate_sql = text("""
        SELECT
            COUNT(*) FILTER (WHERE status IN ('completed', 'cancelled'))   AS closed_count,
            COUNT(*) FILTER (WHERE status = 'completed')                   AS completed_count,
            COUNT(*) FILTER (
                WHERE status = 'completed'
                  AND sla_deadline IS NOT NULL
            ) AS with_sla_closed,
            COUNT(*) FILTER (
                WHERE status = 'completed'
                  AND sla_deadline IS NOT NULL
                  AND actual_end_time <= sla_deadline
            ) AS with_sla_ontime
        FROM work_orders
        WHERE tenant_id = :tenant_id
          AND deleted_at IS NULL
          AND created_at >= :dt_from
          AND created_at <= :dt_to
    """)
    rate_row = (
        await db.execute(rate_sql, {"tenant_id": tid, "dt_from": dt_from, "dt_to": dt_to})
    ).mappings().one()

    closed = rate_row["closed_count"] or 0
    completed = rate_row["completed_count"] or 0
    completion_rate = round(completed / closed, 4) if closed > 0 else 0.0

    with_sla = rate_row["with_sla_closed"] or 0
    on_time = rate_row["with_sla_ontime"] or 0
    sla_compliance = round(on_time / with_sla, 4) if with_sla > 0 else 1.0

    # --- Outstanding invoices balance --------------------------------------
    balance_sql = text("""
        SELECT COALESCE(SUM(inv.total - COALESCE(paid.amount_paid, 0)), 0) AS outstanding
        FROM invoices inv
        LEFT JOIN (
            SELECT invoice_id, SUM(amount) AS amount_paid
            FROM payments
            GROUP BY invoice_id
        ) paid ON paid.invoice_id = inv.id
        WHERE inv.tenant_id = :tenant_id
          AND inv.deleted_at IS NULL
          AND inv.status NOT IN ('void', 'paid')
    """)
    outstanding = float(
        (await db.execute(balance_sql, {"tenant_id": tid})).scalar_one() or 0
    )

    # --- Revenue for selected range ----------------------------------------
    mtd_sql = text("""
        SELECT COALESCE(SUM(total), 0) AS revenue_mtd
        FROM invoices
        WHERE tenant_id = :tenant_id
          AND deleted_at IS NULL
          AND status != 'void'
          AND issue_date >= :dt_from
          AND issue_date <= :dt_to
    """)
    revenue_mtd = float(
        (
            await db.execute(
                mtd_sql, {"tenant_id": tid, "dt_from": dt_from, "dt_to": dt_to}
            )
        ).scalar_one()
        or 0
    )

    # --- Crew utilization: actual hours worked / scheduled hours, range-filtered -
    # Numerator: completed check-in durations on crew-assigned WOs in window.
    # Denominator: estimated_hours of crew-assigned WOs scheduled in window.
    # Not capped at 1.0 — overruns are operationally meaningful.
    util_sql = text("""
        WITH actual AS (
            SELECT COALESCE(SUM(
                EXTRACT(EPOCH FROM (ci.check_out_time - ci.check_in_time)) / 3600.0
            ), 0) AS hours_worked
            FROM work_order_check_ins ci
            JOIN work_orders wo ON wo.id = ci.work_order_id
            WHERE wo.tenant_id = :tenant_id
              AND wo.deleted_at IS NULL
              AND wo.crew_id IS NOT NULL
              AND ci.check_out_time IS NOT NULL
              AND ci.check_in_time >= :dt_from
              AND ci.check_in_time <= :dt_to
        ),
        scheduled AS (
            SELECT COALESCE(SUM(estimated_hours), 0) AS hours_scheduled
            FROM work_orders
            WHERE tenant_id = :tenant_id
              AND deleted_at IS NULL
              AND crew_id IS NOT NULL
              AND scheduled_date >= :dt_from
              AND scheduled_date <= :dt_to
        )
        SELECT actual.hours_worked, scheduled.hours_scheduled
        FROM actual, scheduled
    """)
    util_row = (
        await db.execute(util_sql, {"tenant_id": tid, "dt_from": dt_from, "dt_to": dt_to})
    ).mappings().one()

    hours_worked = float(util_row["hours_worked"] or 0)
    hours_scheduled = float(util_row["hours_scheduled"] or 0)
    crew_utilization = round(hours_worked / hours_scheduled, 4) if hours_scheduled > 0 else 0.0

    # --- Average time on-site (completed check-ins, selected range) --------
    avg_sql = text("""
        SELECT COALESCE(
            AVG(
                EXTRACT(EPOCH FROM (ci.check_out_time - ci.check_in_time)) / 60
            ), 0
        ) AS avg_minutes
        FROM work_order_check_ins ci
        JOIN work_orders wo ON wo.id = ci.work_order_id
        WHERE wo.tenant_id = :tenant_id
          AND wo.deleted_at IS NULL
          AND ci.check_out_time IS NOT NULL
          AND ci.check_in_time >= :dt_from
          AND ci.check_in_time <= :dt_to
    """)
    avg_minutes = float(
        (
            await db.execute(
                avg_sql, {"tenant_id": tid, "dt_from": dt_from, "dt_to": dt_to}
            )
        ).scalar_one()
        or 0
    )

    return {
        "active_work_orders": int(wo_row["active_work_orders"] or 0),
        "completed_today": int(wo_row["completed_today"] or 0),
        "completion_rate": completion_rate,
        "sla_compliance": sla_compliance,
        "outstanding_invoices": round(outstanding, 2),
        "total_revenue_mtd": round(revenue_mtd, 2),
        "crew_utilization": crew_utilization,
        "avg_time_on_site_minutes": round(avg_minutes),
    }


# --------------------------------------------------------------------------- #
# GET /work-order-trends
# --------------------------------------------------------------------------- #

@router.get("/work-order-trends")
async def get_work_order_trends(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: Annotated[str | None, Query()] = None,
):
    """
    Return daily created and completed work order counts for the given date range.

    Response: list of WorkOrderTrend objects:
    [{"date": "2025-05-01", "created": 3, "completed": 2}, ...]
    """
    now = datetime.now(tz=UTC)
    dt_from = _parse_date_param(from_, "from") or (now - timedelta(days=30))
    dt_to = _parse_date_param(to, "to", end_of_day=True) or now
    tid = str(tenant_id)

    sql = text("""
        WITH date_series AS (
            SELECT generate_series(
                DATE_TRUNC('day', CAST(:dt_from AS timestamptz)),
                DATE_TRUNC('day', CAST(:dt_to AS timestamptz)),
                INTERVAL '1 day'
            )::date AS day
        ),
        created AS (
            SELECT DATE(created_at AT TIME ZONE 'UTC') AS day, COUNT(*) AS cnt
            FROM work_orders
            WHERE tenant_id = :tenant_id
              AND deleted_at IS NULL
              AND created_at >= :dt_from
              AND created_at <= :dt_to
            GROUP BY 1
        ),
        completed AS (
            SELECT DATE(actual_end_time AT TIME ZONE 'UTC') AS day, COUNT(*) AS cnt
            FROM work_orders
            WHERE tenant_id = :tenant_id
              AND deleted_at IS NULL
              AND status = 'completed'
              AND actual_end_time IS NOT NULL
              AND actual_end_time >= :dt_from
              AND actual_end_time <= :dt_to
            GROUP BY 1
        )
        SELECT
            ds.day::text        AS date,
            COALESCE(c.cnt, 0)  AS created,
            COALESCE(cp.cnt, 0) AS completed
        FROM date_series ds
        LEFT JOIN created   c  ON c.day  = ds.day
        LEFT JOIN completed cp ON cp.day = ds.day
        ORDER BY ds.day ASC
    """)

    rows = (
        await db.execute(sql, {"tenant_id": tid, "dt_from": dt_from, "dt_to": dt_to})
    ).mappings().all()

    return [
        {
            "date": row["date"],
            "created": int(row["created"] or 0),
            "completed": int(row["completed"] or 0),
        }
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# GET /revenue-by-client
# --------------------------------------------------------------------------- #

@router.get("/revenue-by-client")
async def get_revenue_by_client(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: Annotated[str | None, Query()] = None,
):
    """
    Return total invoiced revenue grouped by client for the given date range.

    Response: list of RevenueByClient objects (sorted by revenue descending):
    [{"client_name": "Acme Corp", "revenue": 4500.00}, ...]
    """
    now = datetime.now(tz=UTC)
    dt_from = _parse_date_param(from_, "from") or (now - timedelta(days=30))
    dt_to = _parse_date_param(to, "to", end_of_day=True) or now
    tid = str(tenant_id)

    sql = text("""
        SELECT
            cl.name                         AS client_name,
            COALESCE(SUM(inv.total), 0)     AS revenue
        FROM clients cl
        JOIN invoices inv ON inv.client_id = cl.id
        WHERE inv.tenant_id = :tenant_id
          AND inv.deleted_at IS NULL
          AND cl.deleted_at IS NULL
          AND inv.status != 'void'
          AND inv.issue_date >= :dt_from
          AND inv.issue_date <= :dt_to
        GROUP BY cl.id, cl.name
        ORDER BY revenue DESC
        LIMIT 10
    """)

    rows = (
        await db.execute(sql, {"tenant_id": tid, "dt_from": dt_from, "dt_to": dt_to})
    ).mappings().all()

    return [
        {
            "client_name": row["client_name"],
            "revenue": round(float(row["revenue"] or 0), 2),
        }
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# GET /crew-productivity
# --------------------------------------------------------------------------- #

@router.get("/crew-productivity")
async def get_crew_productivity(
    tenant_id: CurrentTenantId,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: Annotated[str | None, Query()] = None,
):
    """
    Return per-crew productivity metrics for the given date range.

    Response: list of CrewProductivity objects:
    [
        {
            "crew_name": "Team A",
            "work_orders_completed": 12,
            "avg_hours": 3.5,
            "sla_compliance": 0.92
        },
        ...
    ]
    """
    now = datetime.now(tz=UTC)
    dt_from = _parse_date_param(from_, "from") or (
        now - timedelta(days=settings.CREW_PRODUCTIVITY_DEFAULT_LOOKBACK_DAYS)
    )
    dt_to = _parse_date_param(to, "to", end_of_day=True) or now

    tid = str(tenant_id)

    sql = text("""
        SELECT
            c.name                                                          AS crew_name,
            COUNT(*) FILTER (WHERE wo.status = 'completed')                AS work_orders_completed,
            COALESCE(
                AVG(
                    EXTRACT(EPOCH FROM (wo.actual_end_time - wo.actual_start_time)) / 3600
                ) FILTER (
                    WHERE wo.status = 'completed'
                      AND wo.actual_start_time IS NOT NULL
                      AND wo.actual_end_time IS NOT NULL
                ), 0
            )                                                              AS avg_hours,
            CASE
                WHEN COUNT(*) FILTER (
                    WHERE wo.status = 'completed' AND wo.sla_deadline IS NOT NULL
                ) = 0 THEN 1.0
                ELSE ROUND(
                    COUNT(*) FILTER (
                        WHERE wo.status = 'completed'
                          AND wo.sla_deadline IS NOT NULL
                          AND wo.actual_end_time <= wo.sla_deadline
                    )::numeric /
                    NULLIF(COUNT(*) FILTER (
                        WHERE wo.status = 'completed' AND wo.sla_deadline IS NOT NULL
                    ), 0),
                    4
                )
            END                                                            AS sla_compliance
        FROM crews c
        JOIN work_orders wo ON wo.crew_id = c.id
        WHERE c.tenant_id = :tenant_id
          AND c.deleted_at IS NULL
          AND wo.deleted_at IS NULL
          AND wo.scheduled_date >= :dt_from
          AND wo.scheduled_date <= :dt_to
        GROUP BY c.id, c.name
        ORDER BY work_orders_completed DESC
    """)

    rows = (
        await db.execute(sql, {"tenant_id": tid, "dt_from": dt_from, "dt_to": dt_to})
    ).mappings().all()

    return [
        {
            "crew_name": row["crew_name"],
            "work_orders_completed": int(row["work_orders_completed"] or 0),
            "avg_hours": round(float(row["avg_hours"] or 0), 2),
            "sla_compliance": float(row["sla_compliance"] or 1.0),
        }
        for row in rows
    ]
