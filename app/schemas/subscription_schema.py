"""Pydantic schemas for subscription request validation."""

from pydantic import BaseModel, Field


class SubscriptionCreateSchema(BaseModel):
    """Schema for creating a subscription request."""

    customer_id: int = Field(..., gt=0)
    plan_id: int = Field(..., gt=0)
    duration_months: int = Field(..., gt=0)
    asset_ids: list[int] = Field(default_factory=list)


class SubscriptionStatusUpdateSchema(BaseModel):
    """Schema for updating a subscription request's status."""

    status: str = Field(
        ...,
        pattern=r"^(pending|pending_inspection|active|cancelled|expired)$",
    )
