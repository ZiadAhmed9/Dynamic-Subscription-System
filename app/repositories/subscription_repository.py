"""Subscription request repository."""

from app.domain.models import SubscriptionRequest
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[SubscriptionRequest]):
    """Data access for SubscriptionRequest records."""

    def __init__(self):
        super().__init__(SubscriptionRequest)

    def get_by_customer(self, customer_id: int) -> list[SubscriptionRequest]:
        """Return all subscription requests for a customer."""
        return SubscriptionRequest.query.filter_by(customer_id=customer_id).all()

    def get_pending_inspection(self) -> list[SubscriptionRequest]:
        """Return pending requests whose plan requires inspection.

        Joins to SubscriptionPlan and filters on the JSON rules column.
        """
        from app.domain.models import SubscriptionPlan

        return (
            SubscriptionRequest.query
            .join(SubscriptionPlan)
            .filter(
                SubscriptionRequest.status == "pending_inspection",
            )
            .all()
        )

    def filter_requests(
        self,
        status: str | None = None,
        needs_inspection: bool | None = None,
    ) -> list[SubscriptionRequest]:
        """Flexible filtering for dashboard views."""
        from app.domain.models import SubscriptionPlan

        query = SubscriptionRequest.query.join(SubscriptionPlan)

        if status:
            query = query.filter(SubscriptionRequest.status == status)

        if needs_inspection is True:
            query = query.filter(
                SubscriptionRequest.status == "pending_inspection",
            )

        return query.all()
