"""Subscription service — core workflow orchestration.

Flow: validate input → RuleEngine.validate() → PricingEngine.calculate() → persist.
"""

import logging

from app.domain.exceptions import ResourceNotFoundError, ValidationError
from app.domain.rule_engine import RuleEngine
from app.domain.pricing_engine import PricingEngine
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.asset_repository import AssetRepository
from app.domain.models import SubscriptionItem

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Orchestrates subscription request creation with rule and pricing engines."""

    def __init__(self):
        self._sub_repo = SubscriptionRepository()
        self._plan_repo = PlanRepository()
        self._customer_repo = CustomerRepository()
        self._asset_repo = AssetRepository()
        self._rule_engine = RuleEngine()
        self._pricing_engine = PricingEngine()

    def create_subscription(
        self,
        customer_id: int,
        plan_id: int,
        duration_months: int,
        asset_ids: list[int],
    ) -> dict:
        """Create a subscription request.

        Steps:
          1. Validate customer and plan exist
          2. Validate selected assets belong to customer
          3. Run rule engine against plan rules
          4. Calculate cost via pricing engine
          5. Persist request and items
        """
        customer = self._customer_repo.get_by_id(customer_id)
        if not customer:
            raise ResourceNotFoundError("Customer", customer_id)

        plan = self._plan_repo.get_by_id(plan_id)
        if not plan:
            raise ResourceNotFoundError("SubscriptionPlan", plan_id)

        assets = self._resolve_assets(customer_id, asset_ids)
        asset_dicts = [a.to_dict() for a in assets]
        rules = plan.rules

        # --- Rule validation ---
        self._rule_engine.validate(rules, duration_months, asset_dicts)

        # --- Pricing ---
        breakdown = self._pricing_engine.calculate(rules, duration_months, asset_dicts)
        payment_type = rules.get("payment_type", "prepaid")
        payment_details = self._build_payment_details(payment_type, breakdown.total)
        cost_breakdown = breakdown.to_dict()
        cost_breakdown["payment"] = payment_details

        # --- Determine initial status ---
        initial_status = self._determine_status(rules)

        # --- Persist ---
        request = self._sub_repo.create(
            customer_id=customer_id,
            plan_id=plan_id,
            duration_months=duration_months,
            status=initial_status,
            total_cost=breakdown.total,
            cost_breakdown=cost_breakdown,
        )

        self._create_items(request.id, assets, breakdown)
        self._sub_repo.commit()

        logger.info(
            "Subscription created id=%s customer=%s plan=%s total=%s",
            request.id, customer_id, plan_id, breakdown.total,
        )
        return request.to_dict()

    def get_subscription(self, request_id: int) -> dict:
        """Fetch a subscription request by ID."""
        request = self._sub_repo.get_by_id(request_id)
        if not request:
            raise ResourceNotFoundError("SubscriptionRequest", request_id)
        return request.to_dict()

    def list_subscriptions(
        self,
        status: str | None = None,
        needs_inspection: bool | None = None,
    ) -> list[dict]:
        """List subscription requests with optional filters."""
        requests = self._sub_repo.filter_requests(status, needs_inspection)
        return [r.to_dict() for r in requests]

    def update_status(self, request_id: int, status: str) -> dict:
        """Update the status of a subscription request."""
        request = self._sub_repo.get_by_id(request_id)
        if not request:
            raise ResourceNotFoundError("SubscriptionRequest", request_id)

        request = self._sub_repo.update(request, status=status)
        self._sub_repo.commit()
        logger.info("Subscription id=%s status changed to '%s'", request_id, status)
        return request.to_dict()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_assets(self, customer_id: int, asset_ids: list[int]):
        """Fetch and verify that all assets belong to the customer."""
        if not asset_ids:
            return []

        assets = self._asset_repo.get_many_by_ids(asset_ids)
        found_ids = {a.id for a in assets}
        missing = set(asset_ids) - found_ids

        if missing:
            raise ValidationError(
                f"Assets not found: {sorted(missing)}",
                details={"missing_asset_ids": sorted(missing)},
            )

        wrong_owner = [a for a in assets if a.customer_id != customer_id]
        if wrong_owner:
            raise ValidationError(
                "Some assets do not belong to the specified customer",
                details={"invalid_asset_ids": [a.id for a in wrong_owner]},
            )

        return assets

    @staticmethod
    def _determine_status(rules: dict) -> str:
        """Choose initial status based on inspection requirements."""
        if rules.get("requires_inspection"):
            return "pending_inspection"
        return "pending"

    @staticmethod
    def _create_items(request_id: int, assets, breakdown):
        """Create SubscriptionItem records linking assets to the request."""
        from app.extensions import db

        cost_map = {
            item["asset_id"]: item["cost"]
            for item in breakdown.per_item_costs
        }

        for asset in assets:
            item = SubscriptionItem(
                request_id=request_id,
                asset_id=asset.id,
                item_cost=cost_map.get(asset.id, 0),
            )
            db.session.add(item)

    @staticmethod
    def _build_payment_details(payment_type: str, total_cost):
        """Build payment summary based on plan payment type."""
        if payment_type == "postpaid":
            return {
                "payment_type": "postpaid",
                "amount_due_now": 0.0,
                "deferred_amount": float(total_cost),
            }

        return {
            "payment_type": "prepaid",
            "amount_due_now": float(total_cost),
            "deferred_amount": 0.0,
        }
