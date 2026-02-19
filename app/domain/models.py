"""SQLAlchemy ORM models.

Six generic tables — no service-specific tables.
All business rules are stored as JSON in SubscriptionPlan.rules.
"""

from datetime import datetime, timezone

from app.extensions import db


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class Customer(db.Model):
    """A resident who can own assets and subscribe to services."""

    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    assets = db.relationship("Asset", back_populates="customer", lazy="dynamic")
    subscription_requests = db.relationship(
        "SubscriptionRequest", back_populates="customer", lazy="dynamic",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------
class Asset(db.Model):
    """A customer-owned item (car, garden, pool, etc.) linked to subscriptions."""

    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True,
    )
    asset_type = db.Column(db.String(50), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    metadata_json = db.Column(db.JSON, default=dict)

    customer = db.relationship("Customer", back_populates="assets")
    subscription_items = db.relationship(
        "SubscriptionItem", back_populates="asset", lazy="dynamic",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "asset_type": self.asset_type,
            "label": self.label,
            "metadata": self.metadata_json,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class Service(db.Model):
    """A top-level service offering (car washing, gardening, etc.)."""

    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    plans = db.relationship("SubscriptionPlan", back_populates="service", lazy="dynamic")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Subscription Plan
# ---------------------------------------------------------------------------
class SubscriptionPlan(db.Model):
    """A plan under a service, with all business rules stored as JSON."""

    __tablename__ = "subscription_plans"

    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(
        db.Integer, db.ForeignKey("services.id"), nullable=False, index=True,
    )
    name = db.Column(db.String(120), nullable=False)
    rules = db.Column(db.JSON, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    service = db.relationship("Service", back_populates="plans")
    subscription_requests = db.relationship(
        "SubscriptionRequest", back_populates="plan", lazy="dynamic",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "service_id": self.service_id,
            "name": self.name,
            "rules": self.rules,
            "is_active": self.is_active,
        }


# ---------------------------------------------------------------------------
# Subscription Request
# ---------------------------------------------------------------------------
class SubscriptionRequest(db.Model):
    """A resident's request to subscribe to a plan, with calculated cost."""

    __tablename__ = "subscription_requests"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True,
    )
    plan_id = db.Column(
        db.Integer, db.ForeignKey("subscription_plans.id"), nullable=False, index=True,
    )
    duration_months = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default="pending", nullable=False)
    total_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cost_breakdown = db.Column(db.JSON, default=dict)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    customer = db.relationship("Customer", back_populates="subscription_requests")
    plan = db.relationship("SubscriptionPlan", back_populates="subscription_requests")
    items = db.relationship(
        "SubscriptionItem", back_populates="request", lazy="joined", cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "plan_id": self.plan_id,
            "duration_months": self.duration_months,
            "status": self.status,
            "total_cost": float(self.total_cost),
            "cost_breakdown": self.cost_breakdown,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Subscription Item
# ---------------------------------------------------------------------------
class SubscriptionItem(db.Model):
    """Links an asset to a subscription request with its individual cost."""

    __tablename__ = "subscription_items"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("subscription_requests.id"), nullable=False, index=True,
    )
    asset_id = db.Column(
        db.Integer, db.ForeignKey("assets.id"), nullable=False, index=True,
    )
    item_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    request = db.relationship("SubscriptionRequest", back_populates="items")
    asset = db.relationship("Asset", back_populates="subscription_items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "asset_id": self.asset_id,
            "item_cost": float(self.item_cost),
        }
