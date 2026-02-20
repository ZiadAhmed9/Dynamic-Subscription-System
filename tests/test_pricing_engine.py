"""Unit tests for the Pricing Engine.

Tests all three strategies, inspection fee, proration, and edge cases.
These tests are pure business logic — no Flask dependency.
"""

from decimal import Decimal

import pytest

from app.domain.pricing_engine import (
    CostBreakdown,
    FixedPricingStrategy,
    PerAssetPricingStrategy,
    PerAreaPricingStrategy,
    PricingEngine,
)
from app.domain.exceptions import PricingError


# ---------------------------------------------------------------------------
# Strategy unit tests
# ---------------------------------------------------------------------------
class TestFixedPricingStrategy:
    """Tests for the FixedPricingStrategy."""

    def test_basic_calculation(self):
        strategy = FixedPricingStrategy()
        result = strategy.calculate(
            price=Decimal("100"), duration_months=3, assets=[], rules={},
        )
        assert result.base_cost == Decimal("300")
        assert result.total == Decimal("300")

    def test_single_month(self):
        strategy = FixedPricingStrategy()
        result = strategy.calculate(
            price=Decimal("50"), duration_months=1, assets=[], rules={},
        )
        assert result.base_cost == Decimal("50")


class TestPerAssetPricingStrategy:
    """Tests for the PerAssetPricingStrategy."""

    def test_multiple_assets(self):
        strategy = PerAssetPricingStrategy()
        assets = [
            {"id": 1, "label": "Car A", "asset_type": "car"},
            {"id": 2, "label": "Car B", "asset_type": "car"},
        ]
        result = strategy.calculate(
            price=Decimal("50"), duration_months=3, assets=assets, rules={},
        )
        # 50 * 3 * 2 assets = 300
        assert result.base_cost == Decimal("300")
        assert len(result.per_item_costs) == 2

    def test_zero_assets(self):
        strategy = PerAssetPricingStrategy()
        result = strategy.calculate(
            price=Decimal("100"), duration_months=6, assets=[], rules={},
        )
        assert result.base_cost == Decimal("0")
        assert result.per_item_costs == []


class TestPerAreaPricingStrategy:
    """Tests for the PerAreaPricingStrategy."""

    def test_area_based_pricing(self):
        strategy = PerAreaPricingStrategy()
        assets = [
            {"id": 1, "label": "Garden", "metadata": {"area": 120}},
        ]
        result = strategy.calculate(
            price=Decimal("2"), duration_months=6, assets=assets, rules={},
        )
        # 2 * 120 * 6 = 1440
        assert result.base_cost == Decimal("1440")

    def test_missing_area_defaults_to_zero(self):
        strategy = PerAreaPricingStrategy()
        assets = [{"id": 1, "label": "Unknown", "metadata": {}}]
        result = strategy.calculate(
            price=Decimal("5"), duration_months=3, assets=assets, rules={},
        )
        assert result.base_cost == Decimal("0")


# ---------------------------------------------------------------------------
# PricingEngine integration tests
# ---------------------------------------------------------------------------
class TestPricingEngine:
    """Tests for the PricingEngine facade."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_fixed_plan(self):
        rules = {"pricing_type": "fixed", "price": 150}
        result = self.engine.calculate(rules, duration_months=2, assets=[])
        assert float(result.total) == 300.0

    def test_with_inspection_fee(self):
        rules = {
            "pricing_type": "fixed",
            "price": 100,
            "requires_inspection": True,
            "inspection_fee": 25,
        }
        result = self.engine.calculate(rules, 1, [])
        assert result.inspection_fee == Decimal("25")
        assert float(result.total) == 125.0

    def test_with_proration(self):
        rules = {
            "pricing_type": "fixed",
            "price": 100,
            "billing_cycle_months": 1,
            "proration": {"enabled": True, "days_remaining": 15},
        }
        result = self.engine.calculate(rules, 1, [])
        # base=100, proration = 100 * (15/30) - 100 = -50
        assert result.proration_adjustment == Decimal("-50.00")
        assert float(result.total) == 50.0

    def test_unknown_pricing_type_raises(self):
        rules = {"pricing_type": "unknown", "price": 100}
        with pytest.raises(PricingError, match="Unknown pricing type"):
            self.engine.calculate(rules, 1, [])

    def test_custom_pricing_type_uses_pricing_config(self):
        rules = {
            "pricing_type": "seasonal_bundle",
            "price": 20,
            "pricing_config": {"basis": "per_asset", "duration_multiplier": True},
        }
        assets = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = self.engine.calculate(rules, 2, assets)
        assert float(result.total) == 120.0

    def test_custom_pricing_with_fixed_basis(self):
        rules = {
            "pricing_type": "custom_fixed",
            "price": 25,
            "pricing_config": {"basis": "fixed", "duration_multiplier": False},
        }
        result = self.engine.calculate(rules, 3, [])
        assert float(result.total) == 25.0

    def test_custom_pricing_with_unknown_basis_raises(self):
        rules = {
            "pricing_type": "custom",
            "price": 10,
            "pricing_config": {"basis": "mystery"},
        }
        with pytest.raises(PricingError, match="Unknown pricing basis"):
            self.engine.calculate(rules, 1, [])

    def test_custom_pricing_with_per_area_basis(self):
        rules = {
            "pricing_type": "area_bundle",
            "price": 2,
            "pricing_config": {"basis": "per_area", "duration_multiplier": True},
        }
        assets = [
            {"metadata": {"area": 10}},
            {"metadata": {"area": 15}},
        ]
        result = self.engine.calculate(rules, 2, assets)
        assert float(result.total) == 100.0

    def test_custom_pricing_with_field_sum_basis(self):
        rules = {
            "pricing_type": "water_usage",
            "price": 5,
            "pricing_config": {"basis": "field_sum", "field_name": "units"},
        }
        assets = [
            {"metadata": {"units": 3}},
            {"metadata": {"units": 2}},
        ]
        result = self.engine.calculate(rules, 1, assets)
        assert float(result.total) == 25.0

    def test_custom_pricing_field_sum_missing_field_name_raises(self):
        rules = {
            "pricing_type": "water_usage",
            "price": 5,
            "pricing_config": {"basis": "field_sum"},
        }
        with pytest.raises(PricingError, match="field_name"):
            self.engine.calculate(rules, 1, [])

    def test_proration_percentage_method(self):
        rules = {
            "pricing_type": "fixed",
            "price": 100,
            "proration": {"enabled": True, "method": "percentage", "adjustment_percent": -25},
        }
        result = self.engine.calculate(rules, 2, [])
        assert result.proration_adjustment == Decimal("-50.00")
        assert float(result.total) == 150.0

    def test_unknown_proration_method_raises(self):
        rules = {
            "pricing_type": "fixed",
            "price": 100,
            "proration": {"enabled": True, "method": "mystery"},
        }
        with pytest.raises(PricingError, match="Unknown proration method"):
            self.engine.calculate(rules, 1, [])

    def test_per_asset_with_inspection(self):
        rules = {
            "pricing_type": "per_asset",
            "price": 40,
            "requires_inspection": True,
            "inspection_fee": 10,
        }
        assets = [
            {"id": 1, "label": "Car A"},
            {"id": 2, "label": "Car B"},
        ]
        result = self.engine.calculate(rules, 3, assets)
        # base = 40*3*2 = 240, inspection = 10, total = 250
        assert float(result.total) == 250.0

    def test_defaults_to_fixed_strategy_when_pricing_type_missing(self):
        rules = {"price": 80}
        result = self.engine.calculate(rules, duration_months=2, assets=[])
        assert float(result.total) == 160.0

    def test_proration_enabled_without_days_remaining_keeps_total_unchanged(self):
        rules = {
            "pricing_type": "fixed",
            "price": 100,
            "proration": {"enabled": True},
        }
        result = self.engine.calculate(rules, duration_months=1, assets=[])
        assert result.proration_adjustment == Decimal("0")
        assert float(result.total) == 100.0

    def test_proration_with_non_positive_total_days_is_ignored(self):
        rules = {
            "pricing_type": "fixed",
            "price": 100,
            "billing_cycle_months": 0,
            "proration": {"enabled": True, "days_remaining": 10},
        }
        result = self.engine.calculate(rules, duration_months=1, assets=[])
        assert result.proration_adjustment == Decimal("0")
        assert float(result.total) == 100.0

    def test_per_area_multiple_assets_with_decimal_area(self):
        rules = {
            "pricing_type": "per_area",
            "price": 1.5,
        }
        assets = [
            {"id": 1, "label": "Front Yard", "metadata": {"area": 100}},
            {"id": 2, "label": "Back Yard", "metadata": {"area": 12.5}},
        ]
        result = self.engine.calculate(rules, duration_months=2, assets=assets)
        # (100 + 12.5) * 1.5 * 2 = 337.5
        assert float(result.total) == 337.5

    def test_to_dict_contains_all_breakdown_fields(self):
        breakdown = CostBreakdown(
            base_cost=Decimal("10"),
            inspection_fee=Decimal("2"),
            proration_adjustment=Decimal("-1"),
            per_item_costs=[{"asset_id": 1, "cost": 10.0}],
        )
        payload = breakdown.to_dict()
        assert payload == {
            "base_cost": 10.0,
            "inspection_fee": 2.0,
            "proration_adjustment": -1.0,
            "per_item_costs": [{"asset_id": 1, "cost": 10.0}],
            "total": 11.0,
        }
