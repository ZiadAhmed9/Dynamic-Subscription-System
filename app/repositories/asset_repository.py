"""Asset repository."""

from app.domain.models import Asset
from app.repositories.base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    """Data access for Asset records."""

    def __init__(self):
        super().__init__(Asset)

    def get_by_customer(
        self, customer_id: int, asset_type: str | None = None,
    ) -> list[Asset]:
        """Return assets for a customer, optionally filtered by type."""
        query = Asset.query.filter_by(customer_id=customer_id)
        if asset_type:
            query = query.filter_by(asset_type=asset_type)
        return query.all()

    def get_many_by_ids(self, asset_ids: list[int]) -> list[Asset]:
        """Fetch multiple assets by their IDs in a single query."""
        return Asset.query.filter(Asset.id.in_(asset_ids)).all()
