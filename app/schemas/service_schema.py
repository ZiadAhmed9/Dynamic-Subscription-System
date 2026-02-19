"""Pydantic schemas for service validation."""

from pydantic import BaseModel, Field


class ServiceCreateSchema(BaseModel):
    """Schema for creating or updating a service."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="")
    is_active: bool = Field(default=True)
