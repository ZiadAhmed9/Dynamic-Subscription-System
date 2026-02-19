"""Base repository with generic CRUD operations.

Concrete repositories inherit from this and can add domain-specific queries.
"""

from typing import TypeVar, Generic, Type

from app.extensions import db

T = TypeVar("T", bound=db.Model)


class BaseRepository(Generic[T]):
    """Generic repository providing common database operations.

    Args:
        model_class: The SQLAlchemy model class to operate on.
    """

    def __init__(self, model_class: Type[T]):
        self._model = model_class

    def create(self, **kwargs) -> T:
        """Insert a new record and flush to obtain its id."""
        instance = self._model(**kwargs)
        db.session.add(instance)
        db.session.flush()
        return instance

    def get_by_id(self, record_id: int) -> T | None:
        """Fetch a single record by primary key."""
        return db.session.get(self._model, record_id)

    def get_all(self) -> list[T]:
        """Return every record of this model."""
        return self._model.query.all()

    def filter_by(self, **kwargs) -> list[T]:
        """Return records matching the given column filters."""
        return self._model.query.filter_by(**kwargs).all()

    def update(self, instance: T, **kwargs) -> T:
        """Update an existing instance with keyword arguments."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        db.session.flush()
        return instance

    def delete(self, instance: T) -> None:
        """Remove a record from the session."""
        db.session.delete(instance)
        db.session.flush()

    @staticmethod
    def commit() -> None:
        """Commit the current transaction."""
        db.session.commit()
