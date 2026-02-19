"""Customer repository."""

from app.domain.models import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Data access for Customer records."""

    def __init__(self):
        super().__init__(Customer)

    def get_by_email(self, email: str) -> Customer | None:
        """Find a customer by their email address."""
        return Customer.query.filter_by(email=email).first()
