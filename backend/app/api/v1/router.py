"""
Central API v1 router — includes all sub-routers.

The router-level dependency ``bind_audit_context`` populates the
``_AUDIT_CONTEXT`` contextvar on every /api/v1/* request, after auth
deps resolve. See ``app.core.audit.context`` for details.
"""

from fastapi import APIRouter, Depends

from app.api.v1 import (
    analytics,
    audit_logs,
    auth,
    clients,
    crews,
    invoices,
    locations,
    users,
    work_orders,
)
from app.core.audit import bind_audit_context

api_router = APIRouter(dependencies=[Depends(bind_audit_context)])

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["Work Orders"])
api_router.include_router(clients.router, prefix="/clients", tags=["Clients"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])
api_router.include_router(crews.router, prefix="/crews", tags=["Crews"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["Invoices"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["Audit Logs"])
