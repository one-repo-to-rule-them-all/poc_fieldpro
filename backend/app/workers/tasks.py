"""
ARQ background task definitions.

Each function receives ``ctx`` as its first argument (the ARQ job context),
which provides access to shared resources like the DB session (``ctx["db"]``)
and the ARQ Redis pool (``ctx["redis"]``).

Start the worker with::

    python -m app.workers.main
"""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from typing import Any
import uuid

from arq import create_pool
from arq.connections import RedisSettings
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# SMTP helpers
# --------------------------------------------------------------------------- #

def _build_smtp() -> smtplib.SMTP | smtplib.SMTP_SSL:
    if settings.SMTP_PORT == 465:
        conn: smtplib.SMTP | smtplib.SMTP_SSL = smtplib.SMTP_SSL(
            settings.SMTP_HOST, settings.SMTP_PORT
        )
    else:
        conn = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
        conn.ehlo()
        if settings.SMTP_TLS:
            conn.starttls()
    if settings.SMTP_USER:
        conn.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    return conn


def _send_email(to: str, subject: str, html_body: str, text_body: str = "") -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    try:
        with _build_smtp() as conn:
            conn.send_message(msg)
    except Exception as exc:
        logger.error("smtp_send_failed", recipient=to, error=str(exc))
        raise


# --------------------------------------------------------------------------- #
# Task: send_password_reset_email
# --------------------------------------------------------------------------- #

async def send_password_reset_email(
    ctx: dict[str, Any],
    *,
    user_id: str,
    reset_token: str,
) -> None:
    """Send a password-reset email to the given user."""
    log = logger.bind(task="send_password_reset_email", user_id=user_id)

    db = ctx.get("db")
    close_db = False
    if db is None:
        from app.core.database import AsyncSessionLocal
        db = AsyncSessionLocal()
        close_db = True

    try:
        from sqlalchemy import select

        from app.models.user import User

        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            log.warning("user_not_found")
            return

        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        html_body = (
            f"<p>Hi {user.first_name},</p>"
            f"<p>Someone requested a password reset for your FieldPro account.</p>"
            f"<p><a href='{reset_url}' style='background:#2563eb;color:white;padding:10px 20px;"
            f"border-radius:4px;text-decoration:none;display:inline-block;'>Reset Password</a></p>"
            f"<p>Or copy this link: {reset_url}</p>"
            "<p>This link expires in 1 hour. If you did not request this, ignore this email.</p>"
            "<p>— FieldPro</p>"
        )
        text_body = (
            f"Hi {user.first_name},\n\n"
            f"Reset your FieldPro password: {reset_url}\n\n"
            "This link expires in 1 hour.\n"
            "If you did not request this, ignore this email."
        )

        if settings.SMTP_HOST:
            _send_email(user.email, "Reset your FieldPro password", html_body, text_body)
            log.info("password_reset_email_sent", email=user.email)
        else:
            log.info("smtp_not_configured_skipping", email=user.email, reset_url=reset_url)
    finally:
        if close_db:
            await db.close()


# --------------------------------------------------------------------------- #
# Task: send_work_order_notification
# --------------------------------------------------------------------------- #

async def send_work_order_notification(
    ctx: dict[str, Any],
    *,
    work_order_id: str,
    event: str,
) -> None:
    """Notify relevant parties when a work order state changes."""
    logger.info(
        "work_order_notification",
        task="send_work_order_notification",
        work_order_id=work_order_id,
        event=event,
    )
    # Phase 2: load work order + crew + client contacts,
    # dispatch email/SMS based on event type and tenant notification prefs.


# --------------------------------------------------------------------------- #
# Task: expand_recurring_work_orders
# --------------------------------------------------------------------------- #

async def expand_recurring_work_orders(ctx: dict[str, Any]) -> None:
    """
    Cron — nightly.
    Finds recurring work order templates and generates instances
    for the next 30 days that do not already exist.
    """
    log = logger.bind(task="expand_recurring_work_orders")
    log.info("starting")

    db = ctx.get("db")
    close_db = False
    if db is None:
        from app.core.database import AsyncSessionLocal
        db = AsyncSessionLocal()
        close_db = True

    try:
        from sqlalchemy import select

        from app.models.work_order import WorkOrder, WorkType

        result = await db.execute(
            select(WorkOrder).where(
                WorkOrder.work_type == WorkType.recurring,
                WorkOrder.recurrence_rule.isnot(None),
                WorkOrder.deleted_at.is_(None),
            )
        )
        templates = result.scalars().all()
        log.info("found_templates", count=len(templates))
        # Phase 2: parse RRULE with dateutil.rrule, generate + deduplicate instances.
    finally:
        if close_db:
            await db.close()


# --------------------------------------------------------------------------- #
# Task: generate_invoice_pdf
# --------------------------------------------------------------------------- #

async def generate_invoice_pdf(
    ctx: dict[str, Any],
    *,
    invoice_id: str,
) -> None:
    """Generate a PDF for the invoice and upload to object storage."""
    log = logger.bind(task="generate_invoice_pdf", invoice_id=invoice_id)
    log.info("starting")
    # Phase 2: render Jinja2 HTML template -> WeasyPrint PDF -> upload to R2/S3
    # -> update invoice.pdf_url + invoice.pdf_generated_at.


# --------------------------------------------------------------------------- #
# Task: send_invoice_email
# --------------------------------------------------------------------------- #

async def send_invoice_email(
    ctx: dict[str, Any],
    *,
    invoice_id: str,
) -> None:
    """Email the invoice to the client contact."""
    log = logger.bind(task="send_invoice_email", invoice_id=invoice_id)
    log.info("starting")

    db = ctx.get("db")
    close_db = False
    if db is None:
        from app.core.database import AsyncSessionLocal
        db = AsyncSessionLocal()
        close_db = True

    try:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.invoice import Invoice

        result = await db.execute(
            select(Invoice)
            .where(Invoice.id == uuid.UUID(invoice_id))
            .options(selectinload(Invoice.client))
        )
        invoice = result.scalar_one_or_none()
        if not invoice:
            log.warning("invoice_not_found")
            return

        client_email = getattr(invoice.client, "billing_email", None) if invoice.client else None
        if not client_email:
            log.warning("no_client_email", client_id=str(invoice.client_id))
            return

        html_body = (
            f"<p>Dear {invoice.client.name},</p>"
            f"<p>Invoice <strong>#{invoice.invoice_number}</strong> for "
            f"<strong>${invoice.total:.2f}</strong> is due on "
            f"{invoice.due_date.strftime('%B %d, %Y') if invoice.due_date else 'N/A'}.</p>"
            "<p>Thank you for your business.</p>"
            "<p>— FieldPro</p>"
        )
        if settings.SMTP_HOST:
            _send_email(
                client_email,
                f"Invoice #{invoice.invoice_number} from FieldPro",
                html_body,
            )
            log.info("invoice_email_sent", email=client_email)
        else:
            log.info("smtp_not_configured_skipping", invoice_id=invoice_id)
    finally:
        if close_db:
            await db.close()


# --------------------------------------------------------------------------- #
# Task: take_kpi_snapshot
# --------------------------------------------------------------------------- #

async def take_kpi_snapshot(ctx: dict[str, Any]) -> None:
    """
    Cron — hourly.
    Pre-aggregates KPI metrics per tenant into kpi_snapshots so the
    dashboard API returns in milliseconds from cached data.
    Phase 2: create kpi_snapshots table and populate here.
    """
    logger.info("kpi_snapshot", task="take_kpi_snapshot", status="phase2_stub")


# --------------------------------------------------------------------------- #
# Enqueue helper — used by API layer to dispatch jobs
# --------------------------------------------------------------------------- #

async def enqueue_task(task_name: str, **kwargs: Any) -> None:
    """
    Enqueue a named ARQ task.

    Usage::
        await enqueue_task("send_password_reset_email", user_id="...", reset_token="...")
    """
    redis_settings = RedisSettings.from_dsn(settings.ARQ_REDIS_URL)
    pool = await create_pool(redis_settings)
    try:
        await pool.enqueue_job(task_name, **kwargs)
        logger.debug("task_enqueued", task=task_name, kwargs=list(kwargs.keys()))
    finally:
        await pool.aclose()
