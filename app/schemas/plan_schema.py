"""Pydantic schemas for subscription plan validation."""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class PlanRulesSchema(BaseModel):
    """Validates the rules JSON structure for a subscription plan."""

    pricing_type: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    price: float = Field(..., gt=0)
    billing_cycle_months: int = Field(default=1, ge=1)
    min_duration_months: int = Field(default=1, ge=1)
    payment_type: str = Field(default="prepaid", pattern=r"^(prepaid|postpaid)$")
    requires_inspection: bool = Field(default=False)
    inspection_fee: float = Field(default=0, ge=0)
    proration: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    pricing_config: dict[str, Any] | None = Field(default=None)
    applicable_asset_types: list[str] | None = Field(default=None)

    @model_validator(mode="after")
    def validate_rules(self) -> "PlanRulesSchema":
        """Validate cross-field rule constraints."""
        if self.requires_inspection and self.inspection_fee <= 0:
            # Allow free inspections — fee is optional
            pass

        base_types = {"fixed", "per_asset", "per_area"}
        if self.pricing_type not in base_types and not self.pricing_config:
            msg = "pricing_config is required for custom pricing_type values."
            raise ValueError(msg)

        return self


class PlanCreateSchema(BaseModel):
    """Schema for creating or updating a subscription plan."""

    service_id: int = Field(..., gt=0)
    name: str = Field(..., min_length=1, max_length=120)
    rules: PlanRulesSchema
    is_active: bool = Field(default=True)
