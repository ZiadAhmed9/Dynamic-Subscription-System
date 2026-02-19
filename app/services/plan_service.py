"""Plan service — use-case orchestration for subscription plans."""

import logging

from app.domain.exceptions import ResourceNotFoundError
from app.repositories.plan_repository import PlanRepository
from app.repositories.service_repository import ServiceRepository

logger = logging.getLogger(__name__)


class PlanService:
    """Manages subscription plan CRUD operations."""

    def __init__(self):
        self._plan_repo = PlanRepository()
        self._service_repo = ServiceRepository()

    def create_plan(
        self,
        service_id: int,
        name: str,
        rules: dict,
        is_active: bool = True,
    ) -> dict:
        """Create a new subscription plan under a service."""
        service = self._service_repo.get_by_id(service_id)
        if not service:
            raise ResourceNotFoundError("Service", service_id)

        plan = self._plan_repo.create(
            service_id=service_id,
            name=name,
            rules=rules,
            is_active=is_active,
        )
        self._plan_repo.commit()
        logger.info("Created plan id=%s for service id=%s", plan.id, service_id)
        return plan.to_dict()

    def update_plan(self, plan_id: int, **kwargs) -> dict:
        """Update an existing subscription plan."""
        plan = self._plan_repo.get_by_id(plan_id)
        if not plan:
            raise ResourceNotFoundError("SubscriptionPlan", plan_id)

        plan = self._plan_repo.update(plan, **kwargs)
        self._plan_repo.commit()
        logger.info("Updated plan id=%s", plan_id)
        return plan.to_dict()

    def get_all_plans(self, service_id: int | None = None) -> list[dict]:
        """Return plans, optionally filtered by service."""
        if service_id:
            plans = self._plan_repo.get_by_service(service_id)
        else:
            plans = self._plan_repo.get_all()
        return [p.to_dict() for p in plans]

    def get_plan(self, plan_id: int) -> dict:
        """Fetch a single plan by ID."""
        plan = self._plan_repo.get_by_id(plan_id)
        if not plan:
            raise ResourceNotFoundError("SubscriptionPlan", plan_id)
        return plan.to_dict()
