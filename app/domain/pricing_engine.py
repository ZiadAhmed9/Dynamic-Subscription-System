"""Pricing Engine — Strategy Pattern for dynamic cost calculation.

Strategies are selected at runtime from the plan's ``pricing_type`` rule.
New pricing types can be added by implementing ``PricingStrategy`` and
registering in the ``STRATEGY_MAP`` — no modification of existing code.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.exceptions import PricingError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost breakdown data object
# ---------------------------------------------------------------------------
@dataclass
class CostBreakdown:
    """Itemised cost breakdown returned by the pricing engine."""

    base_cost: Decimal = Decimal("0")
    inspection_fee: Decimal = Decimal("0")
    proration_adjustment: Decimal = Decimal("0")
    per_item_costs: list[dict] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return self.base_cost + self.inspection_fee + self.proration_adjustment

    def to_dict(self) -> dict:
        return {
            "base_cost": float(self.base_cost),
            "inspection_fee": float(self.inspection_fee),
            "proration_adjustment": float(self.proration_adjustment),
            "per_item_costs": self.per_item_costs,
            "total": float(self.total),
        }


# ---------------------------------------------------------------------------
# Abstract strategy
# ---------------------------------------------------------------------------
class PricingStrategy(ABC):
    """Interface that all pricing strategies must implement."""

    @abstractmethod
    def calculate(
        self,
        price: Decimal,
        duration_months: int,
        assets: list[dict],
        rules: dict,
    ) -> CostBreakdown:
        """Calculate the cost breakdown for a subscription.

        Args:
            price: Unit price from the plan rules.
            duration_months: Requested subscription length.
            assets: List of asset dicts.
            rules: Full plan rules dict.

        Returns:
            A ``CostBreakdown`` with itemised costs.
        """


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------
class FixedPricingStrategy(PricingStrategy):
    """Flat price multiplied by duration, regardless of assets."""

    def calculate(
        self,
        price: Decimal,
        duration_months: int,
        assets: list[dict],
        rules: dict,
    ) -> CostBreakdown:
        base = price * duration_months
        return CostBreakdown(base_cost=base)


class PerAssetPricingStrategy(PricingStrategy):
    """Price × number of assets × duration."""

    def calculate(
        self,
        price: Decimal,
        duration_months: int,
        assets: list[dict],
        rules: dict,
    ) -> CostBreakdown:
        per_item = []
        total = Decimal("0")

        for asset in assets:
            asset_cost = price * duration_months
            total += asset_cost
            per_item.append({
                "asset_id": asset.get("id"),
                "label": asset.get("label", ""),
                "cost": float(asset_cost),
            })

        return CostBreakdown(base_cost=total, per_item_costs=per_item)


class PerAreaPricingStrategy(PricingStrategy):
    """Price × total area (from asset metadata) × duration."""

    def calculate(
        self,
        price: Decimal,
        duration_months: int,
        assets: list[dict],
        rules: dict,
    ) -> CostBreakdown:
        per_item = []
        total = Decimal("0")

        for asset in assets:
            area = Decimal(str(asset.get("metadata", {}).get("area", 0)))
            asset_cost = price * area * duration_months
            total += asset_cost
            per_item.append({
                "asset_id": asset.get("id"),
                "label": asset.get("label", ""),
                "area": float(area),
                "cost": float(asset_cost),
            })

        return CostBreakdown(base_cost=total, per_item_costs=per_item)


class ConfigurablePricingStrategy(PricingStrategy):
    """Generic strategy driven by rules['pricing_config'].

    This enables new pricing_type values without backend code changes.
    """

    def calculate(
        self,
        price: Decimal,
        duration_months: int,
        assets: list[dict],
        rules: dict,
    ) -> CostBreakdown:
        config = rules.get("pricing_config", {}) or {}
        basis = config.get("basis", "fixed")
        duration_multiplier = duration_months if config.get("duration_multiplier", True) else 1

        if basis == "fixed":
            units = Decimal("1")
            per_item = []
        elif basis == "per_asset":
            units = Decimal(str(len(assets)))
            per_item = []
        elif basis == "per_area":
            total_area = sum(
                Decimal(str(asset.get("metadata", {}).get("area", 0)))
                for asset in assets
            )
            units = total_area
            per_item = []
        elif basis == "field_sum":
            field_name = config.get("field_name")
            if not field_name:
                raise PricingError("pricing_config.field_name is required for basis='field_sum'")
            units = sum(
                Decimal(str(asset.get("metadata", {}).get(field_name, 0)))
                for asset in assets
            )
            per_item = []
        else:
            raise PricingError(f"Unknown pricing basis: '{basis}'")

        base = price * units * Decimal(str(duration_multiplier))
        return CostBreakdown(base_cost=base, per_item_costs=per_item)


# ---------------------------------------------------------------------------
# Strategy registry — extend here for new pricing types
# ---------------------------------------------------------------------------
STRATEGY_MAP: dict[str, PricingStrategy] = {
    "fixed": FixedPricingStrategy(),
    "per_asset": PerAssetPricingStrategy(),
    "per_area": PerAreaPricingStrategy(),
}


# ---------------------------------------------------------------------------
# Pricing Engine (facade)
# ---------------------------------------------------------------------------
class PricingEngine:
    """Selects a pricing strategy and applies cross-cutting cost modifiers.

    Modifiers:
      - Inspection fee (if required)
      - Proration adjustment (daily method)
    """

    def calculate(self, rules: dict, duration_months: int, assets: list[dict]) -> CostBreakdown:
        """Calculate the full cost for a subscription request.

        Args:
            rules: Plan rules JSON dict.
            duration_months: Requested subscription length.
            assets: List of asset dicts.

        Returns:
            A ``CostBreakdown`` with all modifiers applied.
        """
        pricing_type = rules.get("pricing_type", "fixed")
        strategy = STRATEGY_MAP.get(pricing_type)

        if strategy is None:
            if isinstance(rules.get("pricing_config"), dict):
                strategy = ConfigurablePricingStrategy()
            else:
                raise PricingError(f"Unknown pricing type: '{pricing_type}'")

        price = Decimal(str(rules.get("price", 0)))
        breakdown = strategy.calculate(price, duration_months, assets, rules)

        self._apply_inspection_fee(rules, breakdown)
        self._apply_proration(rules, breakdown)

        logger.info(
            "Pricing calculated — type=%s, total=%s", pricing_type, breakdown.total,
        )
        return breakdown

    # ------------------------------------------------------------------
    # Cross-cutting modifiers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_inspection_fee(rules: dict, breakdown: CostBreakdown) -> None:
        """Add inspection fee if plan requires paid inspection."""
        if rules.get("requires_inspection") and rules.get("inspection_fee"):
            breakdown.inspection_fee = Decimal(str(rules["inspection_fee"]))

    @staticmethod
    def _apply_proration(rules: dict, breakdown: CostBreakdown) -> None:
        """Apply daily proration adjustment if enabled.

        Formula: adjustment = base_cost × (remaining_days / total_cycle_days) - base_cost
        For a full cycle this is zero; for partial cycles it reduces the cost.
        """
        proration = rules.get("proration", {})
        if not proration.get("enabled"):
            return

        method = proration.get("method", "daily")
        if method == "daily":
            PricingEngine._apply_daily_proration(rules, proration, breakdown)
            return
        if method == "percentage":
            percentage = Decimal(str(proration.get("adjustment_percent", 0)))
            adjustment = (breakdown.base_cost * percentage / Decimal("100")).quantize(Decimal("0.01"))
            breakdown.proration_adjustment = adjustment
            return

        raise PricingError(f"Unknown proration method: '{method}'")

    @staticmethod
    def _apply_daily_proration(rules: dict, proration: dict, breakdown: CostBreakdown) -> None:
        """Apply daily proration adjustment based on remaining days."""
        days_remaining = proration.get("days_remaining")
        if days_remaining is None:
            return

        total_days = proration.get("total_cycle_days")
        if total_days is None:
            billing_cycle_months = rules.get("billing_cycle_months", 1)
            total_days = billing_cycle_months * 30  # simplified month = 30 days

        if total_days <= 0:
            return

        ratio = Decimal(str(days_remaining)) / Decimal(str(total_days))
        # Negative adjustment = discount for partial period
        adjustment = breakdown.base_cost * ratio - breakdown.base_cost
        breakdown.proration_adjustment = adjustment.quantize(Decimal("0.01"))
