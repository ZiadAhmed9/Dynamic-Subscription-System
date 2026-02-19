"""Service repository."""

from app.domain.models import Service
from app.repositories.base import BaseRepository


class ServiceRepository(BaseRepository[Service]):
    """Data access for Service records."""

    def __init__(self):
        super().__init__(Service)

    def get_active(self) -> list[Service]:
        """Return only active services."""
        return Service.query.filter_by(is_active=True).all()
