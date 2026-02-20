"""Seed script — populates the database with demo data for testing.

Usage:
    flask shell
    >>> exec(open('seed.py').read())

Or run directly:
    python seed.py
"""

from app import create_app
from app.extensions import db
from app.domain.models import Customer, Asset, Service, SubscriptionPlan


def seed():
    """Insert demo services, plans, customers, and assets."""
    app = create_app("development")

    with app.app_context():
        db.create_all()

        # Check if already seeded
        if Service.query.first():
            print("⚠ Seed data already exists — skipping.")
            return

        # -- Services --
        car_wash = Service(name="Car Washing", description="Professional car wash service")
        gardening = Service(name="Gardening", description="Lawn and garden maintenance")
        pool = Service(name="Pool Cleaning", description="Residential pool maintenance")
        db.session.add_all([car_wash, gardening, pool])
        db.session.flush()

        # -- Plans --
        car_basic = SubscriptionPlan(
            service_id=car_wash.id,
            name="Car Wash Basic",
            rules={
                "pricing_type": "per_asset",
                "price": 50.0,
                "billing_cycle_months": 1,
                "min_duration_months": 3,
                "payment_type": "prepaid",
                "requires_inspection": False,
                "inspection_fee": 0,
                "proration": {"enabled": False},
                "applicable_asset_types": ["car"],
            },
        )
        garden_premium = SubscriptionPlan(
            service_id=gardening.id,
            name="Garden Premium",
            rules={
                "pricing_type": "per_area",
                "price": 2.0,
                "billing_cycle_months": 1,
                "min_duration_months": 6,
                "payment_type": "postpaid",
                "requires_inspection": True,
                "inspection_fee": 25.0,
                "proration": {"enabled": True, "method": "daily"},
                "applicable_asset_types": ["garden"],
            },
        )
        pool_fixed = SubscriptionPlan(
            service_id=pool.id,
            name="Pool Fixed Monthly",
            rules={
                "pricing_type": "fixed",
                "price": 150.0,
                "billing_cycle_months": 1,
                "min_duration_months": 1,
                "payment_type": "prepaid",
                "requires_inspection": True,
                "inspection_fee": 30.0,
                "proration": {"enabled": False},
                "applicable_asset_types": ["pool"],
            },
        )
        db.session.add_all([car_basic, garden_premium, pool_fixed])
        db.session.flush()

        # -- Customers --
        alice = Customer(name="Alice Johnson", email="alice@example.com", phone="+1234567890")
        bob = Customer(name="Bob Smith", email="bob@example.com", phone="+0987654321")
        db.session.add_all([alice, bob])
        db.session.flush()

        # -- Assets --
        db.session.add_all([
            Asset(customer_id=alice.id, asset_type="car", label="Alice's Sedan",
                  metadata_json={"make": "Toyota", "model": "Camry"}),
            Asset(customer_id=alice.id, asset_type="car", label="Alice's SUV",
                  metadata_json={"make": "Honda", "model": "CR-V"}),
            Asset(customer_id=alice.id, asset_type="garden", label="Front Yard",
                  metadata_json={"area": 120}),
            Asset(customer_id=bob.id, asset_type="car", label="Bob's Truck",
                  metadata_json={"make": "Ford", "model": "F-150"}),
            Asset(customer_id=bob.id, asset_type="pool", label="Backyard Pool",
                  metadata_json={"area": 50}),
            Asset(customer_id=bob.id, asset_type="garden", label="Back Garden",
                  metadata_json={"area": 200}),
        ])

        db.session.commit()
        print("✓ Seed data inserted successfully.")


if __name__ == "__main__":
    seed()
