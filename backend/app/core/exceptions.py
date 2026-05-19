"""
FieldPro custom exception hierarchy.

All domain exceptions derive from FieldProException so callers can catch
either the root or a specific subclass.
"""

from __future__ import annotations


class FieldProException(Exception):  # noqa: N818  — root class is "Exception"; subclasses end in "Error"
    """Base class for all FieldPro domain exceptions."""

    def __init__(self, message: str, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, detail={self.detail!r})"


class NotFoundError(FieldProException):
    """Raised when a requested resource does not exist."""


class PermissionDeniedError(FieldProException):
    """Raised when a user attempts an action outside their role permissions."""


class TenantAccessDeniedError(FieldProException):
    """
    Raised when a user attempts to access a resource belonging to a different
    tenant (cross-tenant data breach attempt).
    """


class PlanLimitExceededError(FieldProException):
    """
    Raised when an action would violate the tenant's subscription plan limits
    (e.g., creating more users than the plan allows).
    """


class DuplicateError(FieldProException):
    """
    Raised when a unique-constraint violation is detected at the service layer
    (e.g., duplicate email, duplicate work order number).
    """


class InvalidOperationError(FieldProException):
    """
    Raised when a business-rule violation occurs at the service layer.

    Examples:
    - Attempting to complete an already-completed work order.
    - Deleting an invoice that has been paid.
    - Re-activating an already-active subscription.
    """


class ExternalServiceError(FieldProException):
    """
    Raised when an external dependency fails (S3, SMTP, Twilio, Sentry, etc.).

    Callers may choose to retry or degrade gracefully.
    """
