"""Service service — use-case orchestration for services."""

import logging

from app.domain.exceptions import ResourceNotFoundError
from app.repositories.service_repository import ServiceRepository

logger = logging.getLogger(__name__)


class ServiceService:
    """Manages service CRUD operations."""

    def __init__(self):
        self._repo = ServiceRepository()

    def create_service(self, name: str, description: str = "", is_active: bool = True) -> dict:
        """Create a new service."""
        service = self._repo.create(name=name, description=description, is_active=is_active)
        self._repo.commit()
        logger.info("Created service id=%s name='%s'", service.id, name)
        return service.to_dict()

    def update_service(self, service_id: int, **kwargs) -> dict:
        """Update an existing service."""
        service = self._repo.get_by_id(service_id)
        if not service:
            raise ResourceNotFoundError("Service", service_id)

        service = self._repo.update(service, **kwargs)
        self._repo.commit()
        logger.info("Updated service id=%s", service_id)
        return service.to_dict()

    def get_all_services(self) -> list[dict]:
        """Return all services."""
        return [s.to_dict() for s in self._repo.get_all()]

    def get_active_services(self) -> list[dict]:
        """Return only active services."""
        return [s.to_dict() for s in self._repo.get_active()]
