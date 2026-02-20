"""Targeted tests to drive full branch/line coverage."""

from decimal import Decimal

import pytest

from app import CustomJSONProvider, create_app
from app.domain.exceptions import AppError, ResourceNotFoundError
from app.domain.models import SubscriptionRequest
from app.repositories.asset_repository import AssetRepository
from app.repositories.base import BaseRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.plan_schema import PlanRulesSchema
from app.services.customer_service import CustomerService
from app.services.plan_service import PlanService
from app.services.service_service import ServiceService
from app.services.subscription_service import SubscriptionService


def _create_minimal_subscription_data():
    service_repo = ServiceRepository()
    customer_repo = CustomerRepository()
    plan_repo = PlanRepository()
    asset_repo = AssetRepository()
    sub_repo = SubscriptionRepository()

    service = service_repo.create(name="S1", description="d", is_active=True)
    customer = customer_repo.create(name="U1", email="u1@example.com", phone=None)
    asset = asset_repo.create(
        customer_id=customer.id,
        asset_type="car",
        label="Car 1",
        metadata_json={},
    )
    plan = plan_repo.create(
        service_id=service.id,
        name="P1",
        rules={"pricing_type": "fixed", "price": 10},
        is_active=True,
    )
    request = sub_repo.create(
        customer_id=customer.id,
        plan_id=plan.id,
        duration_months=1,
        status="pending",
        total_cost=10,
        cost_breakdown={"total": 10},
    )
    service_repo.commit()
    return {
        "service": service,
        "customer": customer,
        "asset": asset,
        "plan": plan,
        "request": request,
    }


class TestAppCoverage:
    def test_custom_json_provider_decimal_and_fallback(self, app):
        provider = CustomJSONProvider(app)
        assert provider.default(Decimal("1.25")) == 1.25
        with pytest.raises(TypeError):
            provider.default(object())

    def test_global_error_handlers_404_app_error_500(self):
        test_app = create_app("testing")
        test_app.config["PROPAGATE_EXCEPTIONS"] = False

        @test_app.route("/raise-app-error")
        def raise_app_error():
            raise AppError("boom", "CUSTOM_ERROR", 418)

        @test_app.route("/raise-500")
        def raise_500():
            raise RuntimeError("boom")

        client = test_app.test_client()
        not_found = client.get("/does-not-exist")
        assert not_found.status_code == 404
        assert not_found.get_json()["error_code"] == "NOT_FOUND"

        app_error = client.get("/raise-app-error")
        assert app_error.status_code == 418
        assert app_error.get_json()["error_code"] == "CUSTOM_ERROR"

        internal = client.get("/raise-500")
        assert internal.status_code == 500
        assert internal.get_json()["error_code"] == "INTERNAL_ERROR"


class TestRepositoryCoverage:
    def test_base_repository_generic_methods(self, app):
        with app.app_context():
            repo = BaseRepository(SubscriptionRequest)
            data = _create_minimal_subscription_data()
            req = repo.get_by_id(data["request"].id)
            assert req is not None
            assert len(repo.get_all()) == 1
            assert len(repo.filter_by(status="pending")) == 1
            repo.delete(req)
            repo.commit()
            assert repo.get_by_id(data["request"].id) is None

    def test_customer_plan_subscription_repo_methods(self, app):
        with app.app_context():
            data = _create_minimal_subscription_data()
            customer_repo = CustomerRepository()
            plan_repo = PlanRepository()
            sub_repo = SubscriptionRepository()

            assert customer_repo.get_by_email("u1@example.com") is not None
            assert plan_repo.get_by_service(data["service"].id, active_only=True)
            assert sub_repo.get_by_customer(data["customer"].id)

            data["request"].status = "pending_inspection"
            sub_repo.commit()
            assert sub_repo.get_pending_inspection()
            assert sub_repo.filter_requests(status="pending_inspection")


class TestServiceCoverage:
    def test_service_service_remaining_paths(self, app):
        with app.app_context():
            svc = ServiceService()
            created = svc.create_service("Svc X")
            assert svc.get_all_services()[0]["id"] == created["id"]
            with pytest.raises(ResourceNotFoundError):
                svc.update_service(9999, name="missing")

    def test_plan_service_remaining_paths(self, app):
        with app.app_context():
            service = ServiceService().create_service("Plan Root")
            plan_svc = PlanService()

            with pytest.raises(ResourceNotFoundError):
                plan_svc.create_plan(9999, "Missing Svc Plan", {"pricing_type": "fixed", "price": 10})

            plan = plan_svc.create_plan(
                service_id=service["id"],
                name="Plan 1",
                rules={"pricing_type": "fixed", "price": 10},
            )
            updated = plan_svc.update_plan(plan["id"], name="Plan 1 Updated")
            assert updated["name"] == "Plan 1 Updated"
            assert plan_svc.get_all_plans()
            assert plan_svc.get_plan(plan["id"])["id"] == plan["id"]
            with pytest.raises(ResourceNotFoundError):
                plan_svc.update_plan(9999, name="missing")
            with pytest.raises(ResourceNotFoundError):
                plan_svc.get_plan(9999)

    def test_customer_service_remaining_paths(self, app):
        with app.app_context():
            customer_svc = CustomerService()
            created = customer_svc.create_customer("User C", "userc@example.com")
            assert customer_svc.get_customer(created["id"])["id"] == created["id"]
            assert customer_svc.get_customer_assets_by_types(created["id"], None) == []

            with pytest.raises(ResourceNotFoundError):
                customer_svc.get_customer(9999)
            with pytest.raises(ResourceNotFoundError):
                customer_svc.add_asset(9999, "car", "No Owner", {})
            with pytest.raises(ResourceNotFoundError):
                customer_svc.get_customer_assets(9999)

    def test_subscription_service_not_found_and_no_assets(self, app):
        with app.app_context():
            sub_svc = SubscriptionService()
            with pytest.raises(ResourceNotFoundError):
                sub_svc.create_subscription(customer_id=9999, plan_id=1, duration_months=1, asset_ids=[])
            with pytest.raises(ResourceNotFoundError):
                sub_svc.get_subscription(9999)
            assert sub_svc._resolve_assets(customer_id=1, asset_ids=[]) == []

            # Ensure plan-not-found path is exercised after customer exists.
            customer = CustomerService().create_customer("User Z", "userz@example.com")
            with pytest.raises(ResourceNotFoundError):
                sub_svc.create_subscription(
                    customer_id=customer["id"],
                    plan_id=9999,
                    duration_months=1,
                    asset_ids=[],
                )

    def test_plan_rules_validator_pass_branch(self):
        schema = PlanRulesSchema(
            pricing_type="fixed",
            price=10,
            requires_inspection=True,
            inspection_fee=0,
        )
        assert schema.requires_inspection is True
        assert schema.inspection_fee == 0

    def test_plan_rules_validator_requires_pricing_config_for_custom_type(self):
        with pytest.raises(ValueError, match="pricing_config is required"):
            PlanRulesSchema(
                pricing_type="seasonal_custom",
                price=10,
            )


class TestApiCoverage:
    def test_mobile_app_error_branches(self, client):
        missing_assets = client.get("/mobile/customers/9999/assets")
        assert missing_assets.status_code == 404

        missing_sub = client.get("/mobile/subscriptions/9999")
        assert missing_sub.status_code == 404

    def test_mobile_assets_by_service_no_active_plans_returns_empty(self, client):
        customer_resp = client.post(
            "/dashboard/customers",
            json={"name": "No Plans", "email": "noplan@example.com"},
        )
        customer_id = customer_resp.get_json()["data"]["id"]
        resp = client.get(f"/mobile/customers/{customer_id}/services/9999/assets")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []

    def test_mobile_assets_by_service_unrestricted_plan(self, client):
        svc = client.post("/dashboard/services", json={"name": "All Assets"}).get_json()["data"]
        plan_resp = client.post(
            "/dashboard/plans",
            json={
                "service_id": svc["id"],
                "name": "Unrestricted Plan",
                "rules": {"pricing_type": "fixed", "price": 10},
            },
        )
        assert plan_resp.status_code == 201

        customer = client.post(
            "/dashboard/customers",
            json={"name": "Assets User", "email": "assets-user@example.com"},
        ).get_json()["data"]
        cid = customer["id"]
        client.post(
            f"/dashboard/customers/{cid}/assets",
            json={"asset_type": "car", "label": "Car A", "metadata": {}},
        )
        client.post(
            f"/dashboard/customers/{cid}/assets",
            json={"asset_type": "garden", "label": "Garden A", "metadata": {"area": 20}},
        )

        resp = client.get(f"/mobile/customers/{cid}/services/{svc['id']}/assets")
        assert resp.status_code == 200
        assert len(resp.get_json()["data"]) == 2

    def test_mobile_assets_by_service_error_branch(self, client):
        svc = client.post("/dashboard/services", json={"name": "Err Svc"}).get_json()["data"]
        client.post(
            "/dashboard/plans",
            json={
                "service_id": svc["id"],
                "name": "Car Plan",
                "rules": {
                    "pricing_type": "fixed",
                    "price": 10,
                    "applicable_asset_types": ["car"],
                },
            },
        )
        resp = client.get(f"/mobile/customers/9999/services/{svc['id']}/assets")
        assert resp.status_code == 404

    def test_dashboard_success_list_and_filter_endpoints(self, client):
        assert client.get("/dashboard/services").status_code == 200
        assert client.get("/dashboard/plans").status_code == 200
        assert client.get("/dashboard/subscriptions?status=pending").status_code == 200

    def test_dashboard_update_plan_success_path(self, client):
        svc_resp = client.post("/dashboard/services", json={"name": "Svc"})
        service_id = svc_resp.get_json()["data"]["id"]
        plan_resp = client.post(
            "/dashboard/plans",
            json={
                "service_id": service_id,
                "name": "Plan A",
                "rules": {"pricing_type": "fixed", "price": 10},
            },
        )
        plan_id = plan_resp.get_json()["data"]["id"]
        update_resp = client.put(
            f"/dashboard/plans/{plan_id}",
            json={
                "service_id": service_id,
                "name": "Plan A Updated",
                "rules": {"pricing_type": "fixed", "price": 11},
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.get_json()["data"]["name"] == "Plan A Updated"

    def test_dashboard_validation_error_branches(self, client):
        bad_service = client.post("/dashboard/services", json={})
        assert bad_service.status_code == 400

        bad_update_service = client.put("/dashboard/services/1", json={})
        assert bad_update_service.status_code == 400

        bad_plan = client.post("/dashboard/plans", json={})
        assert bad_plan.status_code == 400

        bad_update_plan = client.put("/dashboard/plans/1", json={})
        assert bad_update_plan.status_code == 400

        bad_status = client.patch("/dashboard/subscriptions/1/status", json={"status": "bad"})
        assert bad_status.status_code == 400

        bad_customer = client.post("/dashboard/customers", json={})
        assert bad_customer.status_code == 400

        bad_asset = client.post("/dashboard/customers/1/assets", json={})
        assert bad_asset.status_code == 400

    def test_dashboard_app_error_branches(self, client, monkeypatch):
        from app.api import dashboard as dashboard_api

        class BrokenServiceSvc:
            @staticmethod
            def create_service(**_kwargs):
                raise AppError("x", "ERR", 409)

            @staticmethod
            def update_service(*_args, **_kwargs):
                raise AppError("x", "ERR", 409)

        class BrokenPlanSvc:
            @staticmethod
            def create_plan(**_kwargs):
                raise AppError("x", "ERR", 409)

            @staticmethod
            def update_plan(*_args, **_kwargs):
                raise AppError("x", "ERR", 409)

        class BrokenSubSvc:
            @staticmethod
            def update_status(*_args, **_kwargs):
                raise AppError("x", "ERR", 409)

        class BrokenCustomerSvc:
            @staticmethod
            def create_customer(**_kwargs):
                raise AppError("x", "ERR", 409)

            @staticmethod
            def add_asset(**_kwargs):
                raise AppError("x", "ERR", 409)

        monkeypatch.setattr(dashboard_api, "_service_svc", BrokenServiceSvc())
        monkeypatch.setattr(dashboard_api, "_plan_svc", BrokenPlanSvc())
        monkeypatch.setattr(dashboard_api, "_subscription_svc", BrokenSubSvc())
        monkeypatch.setattr(dashboard_api, "_customer_svc", BrokenCustomerSvc())

        resp1 = client.post("/dashboard/services", json={"name": "N"})
        resp2 = client.put("/dashboard/services/1", json={"name": "N"})
        resp3 = client.post(
            "/dashboard/plans",
            json={
                "service_id": 1,
                "name": "P",
                "rules": {"pricing_type": "fixed", "price": 1},
            },
        )
        resp4 = client.put(
            "/dashboard/plans/1",
            json={
                "service_id": 1,
                "name": "P",
                "rules": {"pricing_type": "fixed", "price": 1},
            },
        )
        resp5 = client.patch("/dashboard/subscriptions/1/status", json={"status": "active"})
        resp6 = client.post("/dashboard/customers", json={"name": "A", "email": "a@a.com"})
        resp7 = client.post(
            "/dashboard/customers/1/assets",
            json={"asset_type": "car", "label": "c"},
        )

        for resp in (resp1, resp2, resp3, resp4, resp5, resp6, resp7):
            assert resp.status_code == 409
            assert resp.get_json()["error_code"] == "ERR"
