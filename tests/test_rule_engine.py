"""Unit tests for the Rule Engine.

Tests all validation rules: duration, assets, billing cycle.
Pure business logic — no Flask dependency.
"""

import pytest

from app.domain.rule_engine import RuleEngine
from app.domain.exceptions import RuleViolationError


class TestRuleEngine:
    """Tests for the RuleEngine."""

    def setup_method(self):
        self.engine = RuleEngine()

    # ------------------------------------------------------------------
    # Duration validation
    # ------------------------------------------------------------------
    def test_valid_duration(self):
        rules = {"min_duration_months": 3}
        # Should not raise
        self.engine.validate(rules, duration_months=3, assets=[])

    def test_duration_below_minimum_raises(self):
        rules = {"min_duration_months": 3}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=2, assets=[])
        assert "Minimum subscription duration" in exc_info.value.violations[0]

    def test_default_minimum_duration_is_one(self):
        rules = {}
        # Duration of 1 should pass with default min of 1
        self.engine.validate(rules, duration_months=1, assets=[])

    # ------------------------------------------------------------------
    # Asset type validation
    # ------------------------------------------------------------------
    def test_valid_asset_types(self):
        rules = {"applicable_asset_types": ["car"]}
        assets = [{"asset_type": "car", "label": "My Car"}]
        self.engine.validate(rules, duration_months=1, assets=assets)

    def test_invalid_asset_type_raises(self):
        rules = {"applicable_asset_types": ["car"]}
        assets = [{"asset_type": "garden", "label": "My Garden"}]
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=assets)
        assert "not applicable" in exc_info.value.violations[0]

    def test_no_asset_type_restriction(self):
        rules = {}
        assets = [{"asset_type": "anything", "label": "Wild Card"}]
        self.engine.validate(rules, duration_months=1, assets=assets)

    # ------------------------------------------------------------------
    # Billing cycle validation
    # ------------------------------------------------------------------
    def test_valid_billing_cycle(self):
        rules = {"billing_cycle_months": 3}
        self.engine.validate(rules, duration_months=6, assets=[])

    def test_duration_not_multiple_of_cycle_raises(self):
        rules = {"billing_cycle_months": 3}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=5, assets=[])
        assert "billing cycle" in exc_info.value.violations[0]

    # ------------------------------------------------------------------
    # Multiple violations
    # ------------------------------------------------------------------
    def test_multiple_violations_collected(self):
        rules = {
            "min_duration_months": 6,
            "billing_cycle_months": 3,
            "applicable_asset_types": ["car"],
        }
        assets = [{"asset_type": "pool", "label": "Pool"}]
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=2, assets=assets)
        # Should have at least: duration + asset type + billing cycle
        assert len(exc_info.value.violations) >= 2

    def test_collects_multiple_asset_type_violations(self):
        rules = {"applicable_asset_types": ["car"]}
        assets = [
            {"asset_type": "garden", "label": "Front Yard"},
            {"asset_type": "pool", "label": "Pool"},
        ]
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=assets)
        assert len(exc_info.value.violations) == 2

    def test_zero_billing_cycle_is_ignored(self):
        rules = {"billing_cycle_months": 0}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=5, assets=[])
        assert "Billing cycle must be greater than 0" in exc_info.value.violations[0]

    def test_missing_asset_type_is_rejected_when_types_are_restricted(self):
        rules = {"applicable_asset_types": ["car"]}
        assets = [{"label": "Unknown Asset"}]
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=assets)
        assert "not applicable" in exc_info.value.violations[0]

    def test_invalid_payment_type_raises(self):
        rules = {"payment_type": "cash"}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=[])
        assert "Invalid payment type" in exc_info.value.violations[0]

    def test_proration_daily_missing_days_remaining_raises(self):
        rules = {"proration": {"enabled": True, "method": "daily"}}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=[])
        assert "days_remaining" in exc_info.value.violations[0]

    def test_proration_percentage_missing_adjustment_raises(self):
        rules = {"proration": {"enabled": True, "method": "percentage"}}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=[])
        assert "adjustment_percent" in exc_info.value.violations[0]

    def test_proration_must_be_object(self):
        rules = {"proration": "enabled"}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=[])
        assert "must be an object" in exc_info.value.violations[0]

    def test_invalid_proration_method_raises(self):
        rules = {"proration": {"enabled": True, "method": "weekly"}}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=[])
        assert "Invalid proration method" in exc_info.value.violations[0]

    def test_proration_negative_days_remaining_raises(self):
        rules = {"proration": {"enabled": True, "method": "daily", "days_remaining": -1}}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=[])
        assert "cannot be negative" in exc_info.value.violations[0]

    def test_proration_percentage_out_of_range_raises(self):
        rules = {"proration": {"enabled": True, "method": "percentage", "adjustment_percent": 150}}
        with pytest.raises(RuleViolationError) as exc_info:
            self.engine.validate(rules, duration_months=1, assets=[])
        assert "between -100 and 100" in exc_info.value.violations[0]
