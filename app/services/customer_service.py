"""Customer service — use-case orchestration for customers and assets."""

import logging

from app.domain.exceptions import ResourceNotFoundError
from app.repositories.customer_repository import CustomerRepository
from app.repositories.asset_repository import AssetRepository

logger = logging.getLogger(__name__)


class CustomerService:
    """Manages customer and asset operations."""

    def __init__(self):
        self._customer_repo = CustomerRepository()
        self._asset_repo = AssetRepository()

    # ------------------------------------------------------------------
    # Customer operations
    # ------------------------------------------------------------------

    def create_customer(self, name: str, email: str, phone: str | None = None) -> dict:
        """Create a new customer and return their dict representation."""
        customer = self._customer_repo.create(name=name, email=email, phone=phone)
        self._customer_repo.commit()
        logger.info("Created customer id=%s", customer.id)
        return customer.to_dict()

    def get_customer(self, customer_id: int) -> dict:
        """Fetch a customer by ID or raise not-found."""
        customer = self._customer_repo.get_by_id(customer_id)
        if not customer:
            raise ResourceNotFoundError("Customer", customer_id)
        return customer.to_dict()

    # ------------------------------------------------------------------
    # Asset operations
    # ------------------------------------------------------------------

    def add_asset(
        self,
        customer_id: int,
        asset_type: str,
        label: str,
        metadata: dict | None = None,
    ) -> dict:
        """Add an asset to a customer."""
        customer = self._customer_repo.get_by_id(customer_id)
        if not customer:
            raise ResourceNotFoundError("Customer", customer_id)

        asset = self._asset_repo.create(
            customer_id=customer_id,
            asset_type=asset_type,
            label=label,
            metadata_json=metadata or {},
        )
        self._asset_repo.commit()
        logger.info("Added asset id=%s for customer id=%s", asset.id, customer_id)
        return asset.to_dict()

    def get_customer_assets(
        self, customer_id: int, asset_type: str | None = None,
    ) -> list[dict]:
        """Return assets for a customer, optionally filtered by type."""
        customer = self._customer_repo.get_by_id(customer_id)
        if not customer:
            raise ResourceNotFoundError("Customer", customer_id)

        assets = self._asset_repo.get_by_customer(customer_id, asset_type)
        return [a.to_dict() for a in assets]

    def get_customer_assets_by_types(
        self, customer_id: int, asset_types: set[str] | None,
    ) -> list[dict]:
        """Return customer assets matching any of the provided asset types.

        If ``asset_types`` is None or empty, returns all customer assets.
        """
        if not asset_types:
            return self.get_customer_assets(customer_id)

        collected: dict[int, dict] = {}
        for asset_type in sorted(asset_types):
            for asset in self.get_customer_assets(customer_id, asset_type):
                collected[asset["id"]] = asset

        return list(collected.values())
