"""Subscription plan repository."""

from app.domain.models import SubscriptionPlan
from app.repositories.base import BaseRepository


class PlanRepository(BaseRepository[SubscriptionPlan]):
    """Data access for SubscriptionPlan records."""

    def __init__(self):
        super().__init__(SubscriptionPlan)

    def get_by_service(
        self, service_id: int, active_only: bool = False,
    ) -> list[SubscriptionPlan]:
        """Return plans for a service, optionally only active ones."""
        query = SubscriptionPlan.query.filter_by(service_id=service_id)
        if active_only:
            query = query.filter_by(is_active=True)
        return query.all()
