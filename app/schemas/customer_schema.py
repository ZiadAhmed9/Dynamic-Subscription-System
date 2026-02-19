"""Pydantic schemas for customer and asset validation."""

from pydantic import BaseModel, EmailStr, Field


class CustomerCreateSchema(BaseModel):
    """Schema for creating a new customer."""

    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    phone: str | None = Field(None, max_length=30)


class AssetCreateSchema(BaseModel):
    """Schema for creating a new asset for a customer."""

    asset_type: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=120)
    metadata: dict = Field(default_factory=dict)
