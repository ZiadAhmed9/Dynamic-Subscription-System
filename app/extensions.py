"""Flask extension singletons.

Instantiated here and initialized with the app in the factory
to avoid circular imports.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
