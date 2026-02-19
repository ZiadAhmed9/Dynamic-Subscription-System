"""Rule Engine — validates subscription requests against plan rules.

Pure business logic with no Flask or database dependency.
"""

import logging

from app.domain.exceptions import RuleViolationError

logger = logging.getLogger(__name__)


class RuleEngine:
    """Validates a subscription request against the plan's rule configuration.

    All rules are read from the plan's JSON ``rules`` column, making the
    engine fully data-driven.
    """

    def validate(
        self,
        rules: dict,
        duration_months: int,
        assets: list[dict],
    ) -> None:
        """Run all rule checks.  Raises ``RuleViolationError`` if any fail.

        Args:
            rules: The plan's ``rules`` JSON dict.
            duration_months: Requested subscription duration.
            assets: List of asset dicts (each must have ``asset_type``).
        """
        violations: list[str] = []

        self._validate_duration(rules, duration_months, violations)
        self._validate_assets(rules, assets, violations)
        self._validate_billing_cycle(rules, duration_months, violations)
        self._validate_payment_type(rules, violations)
        self._validate_proration(rules, violations)

        if violations:
            logger.warning("Rule violations: %s", violations)
            raise RuleViolationError(violations)

    # ------------------------------------------------------------------
    # Private validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_duration(
        rules: dict, duration_months: int, violations: list[str],
    ) -> None:
        """Check minimum duration requirement."""
        min_duration = rules.get("min_duration_months", 1)
        if duration_months < min_duration:
            violations.append(
                f"Minimum subscription duration is {min_duration} month(s). "
                f"Requested: {duration_months}.",
            )

    @staticmethod
    def _validate_assets(
        rules: dict, assets: list[dict], violations: list[str],
    ) -> None:
        """Ensure selected assets match the plan's applicable types."""
        applicable_types = rules.get("applicable_asset_types")
        if applicable_types is None:
            return  # no restriction

        for asset in assets:
            if asset.get("asset_type") not in applicable_types:
                violations.append(
                    f"Asset '{asset.get('label', 'unknown')}' of type "
                    f"'{asset.get('asset_type')}' is not applicable to this plan. "
                    f"Allowed types: {applicable_types}.",
                )

    @staticmethod
    def _validate_billing_cycle(
        rules: dict, duration_months: int, violations: list[str],
    ) -> None:
        """Duration must be a multiple of the billing cycle."""
        billing_cycle = rules.get("billing_cycle_months", 1)
        if billing_cycle <= 0:
            violations.append("Billing cycle must be greater than 0.")
            return

        if duration_months % billing_cycle != 0:
            violations.append(
                f"Duration must be a multiple of the billing cycle "
                f"({billing_cycle} month(s)). Requested: {duration_months}.",
            )

    @staticmethod
    def _validate_payment_type(rules: dict, violations: list[str]) -> None:
        """Validate payment type rule if provided."""
        payment_type = rules.get("payment_type", "prepaid")
        if payment_type not in {"prepaid", "postpaid"}:
            violations.append(
                f"Invalid payment type '{payment_type}'. Allowed values: ['prepaid', 'postpaid'].",
            )

    @staticmethod
    def _validate_proration(rules: dict, violations: list[str]) -> None:
        """Validate proration rule structure and method-specific fields."""
        proration = rules.get("proration", {})
        if not isinstance(proration, dict):
            violations.append("Proration config must be an object.")
            return

        if not proration.get("enabled"):
            return

        method = proration.get("method", "daily")
        if method not in {"daily", "percentage"}:
            violations.append(
                f"Invalid proration method '{method}'. Allowed values: ['daily', 'percentage'].",
            )
            return

        if method == "daily":
            days_remaining = proration.get("days_remaining")
            if days_remaining is None:
                violations.append("Proration 'daily' method requires 'days_remaining'.")
            elif days_remaining < 0:
                violations.append("Proration 'days_remaining' cannot be negative.")

        if method == "percentage":
            adjustment_percent = proration.get("adjustment_percent")
            if adjustment_percent is None:
                violations.append("Proration 'percentage' method requires 'adjustment_percent'.")
                return

            if adjustment_percent < -100 or adjustment_percent > 100:
                violations.append("Proration 'adjustment_percent' must be between -100 and 100.")
