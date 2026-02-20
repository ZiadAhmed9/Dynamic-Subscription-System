"""Integration tests for the subscription workflow via the API.

Uses the Flask test client with an in-memory SQLite database.
"""

import json


def _post_json(client, url, data):
    """Helper to POST JSON and return the parsed response."""
    resp = client.post(url, data=json.dumps(data), content_type="application/json")
    return resp.status_code, resp.get_json()


def _setup_service_and_plan(client):
    """Create a service and a per-asset plan via dashboard API."""
    # Create service
    _, svc = _post_json(client, "/dashboard/services", {
        "name": "Car Washing",
        "description": "Professional car wash",
    })
    service_id = svc["data"]["id"]

    # Create plan
    _, plan = _post_json(client, "/dashboard/plans", {
        "service_id": service_id,
        "name": "Car Wash Basic",
        "rules": {
            "pricing_type": "per_asset",
            "price": 50,
            "billing_cycle_months": 1,
            "min_duration_months": 3,
            "payment_type": "prepaid",
            "requires_inspection": False,
            "inspection_fee": 0,
            "proration": {"enabled": False},
            "applicable_asset_types": ["car"],
        },
    })
    plan_id = plan["data"]["id"]
    return service_id, plan_id


def _setup_customer_with_assets(client):
    """Create a customer with two car assets via dashboard API."""
    _, cust = _post_json(client, "/dashboard/customers", {
        "name": "Test User",
        "email": "test@example.com",
    })
    customer_id = cust["data"]["id"]

    _, asset1 = _post_json(client, f"/dashboard/customers/{customer_id}/assets", {
        "asset_type": "car",
        "label": "Sedan",
        "metadata": {"make": "Toyota"},
    })
    _, asset2 = _post_json(client, f"/dashboard/customers/{customer_id}/assets", {
        "asset_type": "car",
        "label": "SUV",
        "metadata": {"make": "Honda"},
    })
    return customer_id, [asset1["data"]["id"], asset2["data"]["id"]]


class TestSubscriptionWorkflow:
    """End-to-end subscription creation tests."""

    def test_full_subscription_flow(self, client):
        """Create service → plan → customer → assets → subscribe."""
        _, plan_id = _setup_service_and_plan(client)
        customer_id, asset_ids = _setup_customer_with_assets(client)

        # Create subscription
        status, body = _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration_months": 3,
            "asset_ids": asset_ids,
        })

        assert status == 201
        data = body["data"]
        assert data["status"] == "pending"
        # 50 * 3 * 2 assets = 300
        assert data["total_cost"] == 300.0
        assert len(data["items"]) == 2

    def test_duration_violation_returns_422(self, client):
        """Request with duration below minimum should be rejected."""
        _, plan_id = _setup_service_and_plan(client)
        customer_id, asset_ids = _setup_customer_with_assets(client)

        status, body = _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration_months": 1,  # min is 3
            "asset_ids": asset_ids,
        })
        assert status == 422
        assert body["error_code"] == "RULE_VIOLATION"

    def test_wrong_asset_type_returns_422(self, client):
        """Submitting a non-car asset to a car-only plan should fail."""
        _, plan_id = _setup_service_and_plan(client)

        _, cust = _post_json(client, "/dashboard/customers", {
            "name": "Garden User",
            "email": "garden@example.com",
        })
        cid = cust["data"]["id"]
        _, asset = _post_json(client, f"/dashboard/customers/{cid}/assets", {
            "asset_type": "garden",
            "label": "Front Yard",
            "metadata": {"area": 100},
        })

        status, body = _post_json(client, "/mobile/subscriptions", {
            "customer_id": cid,
            "plan_id": plan_id,
            "duration_months": 3,
            "asset_ids": [asset["data"]["id"]],
        })
        assert status == 422
        assert body["error_code"] == "RULE_VIOLATION"

    def test_missing_asset_id_returns_400(self, client):
        _, plan_id = _setup_service_and_plan(client)
        customer_id, _ = _setup_customer_with_assets(client)

        status, body = _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration_months": 3,
            "asset_ids": [99999],
        })
        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        assert "missing_asset_ids" in body["details"]

    def test_asset_belongs_to_another_customer_returns_400(self, client):
        _, plan_id = _setup_service_and_plan(client)
        customer_id_1, asset_ids_1 = _setup_customer_with_assets(client)

        _, cust_2 = _post_json(client, "/dashboard/customers", {
            "name": "Second User",
            "email": "second@example.com",
        })
        customer_id_2 = cust_2["data"]["id"]

        status, body = _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id_2,
            "plan_id": plan_id,
            "duration_months": 3,
            "asset_ids": asset_ids_1,
        })
        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"
        assert "invalid_asset_ids" in body["details"]
        assert customer_id_1 != customer_id_2

    def test_inspection_required_sets_pending_inspection_status(self, client):
        _, svc = _post_json(client, "/dashboard/services", {
            "name": "Garden Care",
            "description": "Garden subscriptions",
        })
        service_id = svc["data"]["id"]
        _, plan = _post_json(client, "/dashboard/plans", {
            "service_id": service_id,
            "name": "Garden Premium",
            "rules": {
                "pricing_type": "per_area",
                "price": 2,
                "billing_cycle_months": 1,
                "min_duration_months": 1,
                "payment_type": "postpaid",
                "requires_inspection": True,
                "inspection_fee": 25,
                "proration": {"enabled": False},
                "applicable_asset_types": ["garden"],
            },
        })
        plan_id = plan["data"]["id"]

        _, cust = _post_json(client, "/dashboard/customers", {
            "name": "Garden User",
            "email": "inspection@example.com",
        })
        customer_id = cust["data"]["id"]
        _, asset = _post_json(client, f"/dashboard/customers/{customer_id}/assets", {
            "asset_type": "garden",
            "label": "Large Yard",
            "metadata": {"area": 100},
        })

        status, body = _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration_months": 1,
            "asset_ids": [asset["data"]["id"]],
        })
        assert status == 201
        assert body["data"]["status"] == "pending_inspection"
        assert body["data"]["total_cost"] == 225.0
        assert body["data"]["cost_breakdown"]["payment"]["payment_type"] == "postpaid"
        assert body["data"]["cost_breakdown"]["payment"]["amount_due_now"] == 0.0
        assert body["data"]["cost_breakdown"]["payment"]["deferred_amount"] == 225.0


class TestMobileAPI:
    """Tests for mobile-facing read endpoints."""

    def test_list_services_returns_active(self, client):
        _setup_service_and_plan(client)
        resp = client.get("/mobile/services")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) >= 1
        assert "plans" in data[0]

    def test_get_subscription_detail(self, client):
        _, plan_id = _setup_service_and_plan(client)
        customer_id, asset_ids = _setup_customer_with_assets(client)

        _, sub = _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration_months": 3,
            "asset_ids": asset_ids,
        })
        sub_id = sub["data"]["id"]

        resp = client.get(f"/mobile/subscriptions/{sub_id}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["cost_breakdown"]["total"] == 300.0

    def test_get_assets_filtered_by_type(self, client):
        _, cust = _post_json(client, "/dashboard/customers", {
            "name": "Filter User",
            "email": "filter@example.com",
        })
        customer_id = cust["data"]["id"]
        _post_json(client, f"/dashboard/customers/{customer_id}/assets", {
            "asset_type": "car",
            "label": "Car A",
            "metadata": {},
        })
        _post_json(client, f"/dashboard/customers/{customer_id}/assets", {
            "asset_type": "garden",
            "label": "Garden A",
            "metadata": {"area": 50},
        })

        resp = client.get(f"/mobile/customers/{customer_id}/assets?asset_type=car")
        assert resp.status_code == 200
        assets = resp.get_json()["data"]
        assert len(assets) == 1
        assert assets[0]["asset_type"] == "car"

    def test_get_assets_by_service(self, client):
        service_id, _ = _setup_service_and_plan(client)
        _, cust = _post_json(client, "/dashboard/customers", {
            "name": "Svc Asset User",
            "email": "svc-asset@example.com",
        })
        customer_id = cust["data"]["id"]
        _post_json(client, f"/dashboard/customers/{customer_id}/assets", {
            "asset_type": "car",
            "label": "Car A",
            "metadata": {},
        })
        _post_json(client, f"/dashboard/customers/{customer_id}/assets", {
            "asset_type": "garden",
            "label": "Garden A",
            "metadata": {"area": 50},
        })

        resp = client.get(f"/mobile/customers/{customer_id}/services/{service_id}/assets")
        assert resp.status_code == 200
        assets = resp.get_json()["data"]
        assert len(assets) == 1
        assert assets[0]["asset_type"] == "car"

    def test_create_subscription_with_invalid_payload_returns_400(self, client):
        status, body = _post_json(client, "/mobile/subscriptions", {
            "customer_id": 0,
            "plan_id": -1,
            "duration_months": 0,
            "asset_ids": [],
        })
        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"


class TestDashboardAPI:
    """Tests for dashboard admin endpoints."""

    def test_update_service(self, client):
        _, svc = _post_json(client, "/dashboard/services", {
            "name": "Temp Service",
        })
        sid = svc["data"]["id"]

        resp = client.put(
            f"/dashboard/services/{sid}",
            data=json.dumps({"name": "Updated Service"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "Updated Service"

    def test_update_subscription_status(self, client):
        _, plan_id = _setup_service_and_plan(client)
        customer_id, asset_ids = _setup_customer_with_assets(client)

        _, sub = _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration_months": 3,
            "asset_ids": asset_ids,
        })
        sub_id = sub["data"]["id"]

        resp = client.patch(
            f"/dashboard/subscriptions/{sub_id}/status",
            data=json.dumps({"status": "active"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "active"

    def test_list_subscriptions_with_inspection_filter(self, client):
        _, plan_id = _setup_service_and_plan(client)
        customer_id, asset_ids = _setup_customer_with_assets(client)
        _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id,
            "plan_id": plan_id,
            "duration_months": 3,
            "asset_ids": asset_ids,
        })

        _, svc = _post_json(client, "/dashboard/services", {"name": "Inspection Service"})
        _, plan = _post_json(client, "/dashboard/plans", {
            "service_id": svc["data"]["id"],
            "name": "Inspection Plan",
            "rules": {
                "pricing_type": "fixed",
                "price": 100,
                "billing_cycle_months": 1,
                "min_duration_months": 1,
                "payment_type": "prepaid",
                "requires_inspection": True,
                "inspection_fee": 10,
                "proration": {"enabled": False},
                "applicable_asset_types": ["car"],
            },
        })
        _post_json(client, "/mobile/subscriptions", {
            "customer_id": customer_id,
            "plan_id": plan["data"]["id"],
            "duration_months": 1,
            "asset_ids": [asset_ids[0]],
        })

        resp = client.get("/dashboard/subscriptions?needs_inspection=true")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert len(data) == 1
        assert data[0]["status"] == "pending_inspection"

    def test_create_plan_with_invalid_pricing_type_format_returns_400(self, client):
        _, svc = _post_json(client, "/dashboard/services", {"name": "Bad Plan Service"})
        status, body = _post_json(client, "/dashboard/plans", {
            "service_id": svc["data"]["id"],
            "name": "Invalid Plan",
            "rules": {
                "pricing_type": "dynamic magic!",
                "price": 10,
                "billing_cycle_months": 1,
                "min_duration_months": 1,
                "payment_type": "prepaid",
                "requires_inspection": False,
                "inspection_fee": 0,
                "proration": {"enabled": False},
                "applicable_asset_types": ["car"],
            },
        })
        assert status == 400
        assert body["error_code"] == "VALIDATION_ERROR"

    def test_create_plan_with_custom_pricing_type_and_config(self, client):
        _, svc = _post_json(client, "/dashboard/services", {"name": "Custom Price Service"})
        status, body = _post_json(client, "/dashboard/plans", {
            "service_id": svc["data"]["id"],
            "name": "Custom Plan",
            "rules": {
                "pricing_type": "seasonal_bundle",
                "pricing_config": {"basis": "per_asset", "duration_multiplier": True},
                "price": 15,
                "billing_cycle_months": 1,
                "min_duration_months": 1,
                "payment_type": "prepaid",
                "requires_inspection": False,
                "inspection_fee": 0,
                "proration": {"enabled": False},
                "applicable_asset_types": ["car"],
            },
        })
        assert status == 201
        assert body["data"]["rules"]["pricing_type"] == "seasonal_bundle"

    def test_update_missing_subscription_returns_404(self, client):
        resp = client.patch(
            "/dashboard/subscriptions/99999/status",
            data=json.dumps({"status": "active"}),
            content_type="application/json",
        )
        assert resp.status_code == 404
        assert resp.get_json()["error_code"] == "RESOURCE_NOT_FOUND"
