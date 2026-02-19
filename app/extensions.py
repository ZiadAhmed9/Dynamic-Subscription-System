"""Flask extension singletons.

Instantiated here and initialized with the app in the factory
to avoid circular imports.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
