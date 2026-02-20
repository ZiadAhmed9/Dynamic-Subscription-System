"""Mobile API namespace — endpoints for the resident mobile application.

All routes delegate to service-layer classes. Controllers are kept thin
(parse → validate → call service → respond).
"""

from flask import request
from flask_restx import Namespace, Resource, fields
from pydantic import ValidationError as PydanticValidationError

from app.schemas.subscription_schema import SubscriptionCreateSchema
from app.schemas.response import success_response, error_response
from app.services.service_service import ServiceService
from app.services.plan_service import PlanService
from app.services.customer_service import CustomerService
from app.services.subscription_service import SubscriptionService
from app.domain.exceptions import AppError

ns = Namespace("mobile", description="Mobile application APIs")

# ---------------------------------------------------------------------------
# Swagger models (for documentation only)
# ---------------------------------------------------------------------------
subscription_input_model = ns.model("SubscriptionInput", {
    "customer_id": fields.Integer(required=True, description="Customer ID"),
    "plan_id": fields.Integer(required=True, description="Subscription plan ID"),
    "duration_months": fields.Integer(required=True, description="Duration in months"),
    "asset_ids": fields.List(fields.Integer, description="List of asset IDs"),
})


# ---------------------------------------------------------------------------
# Service instances
# ---------------------------------------------------------------------------
_service_svc = ServiceService()
_plan_svc = PlanService()
_customer_svc = CustomerService()
_subscription_svc = SubscriptionService()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@ns.route("/services")
class ServiceList(Resource):
    """List active services with their plans."""

    @ns.doc("list_active_services")
    def get(self):
        """Fetch all active services with their subscription plans."""
        services = _service_svc.get_active_services()
        for svc in services:
            svc["plans"] = _plan_svc.get_all_plans(service_id=svc["id"])
        return success_response(services)


@ns.route("/customers/<int:customer_id>/assets")
@ns.param("customer_id", "The customer ID")
class CustomerAssets(Resource):
    """Fetch customer assets, optionally filtered by type."""

    @ns.doc("list_customer_assets")
    def get(self, customer_id: int):
        """Return assets for a customer."""
        try:
            asset_type = request.args.get("asset_type")
            assets = _customer_svc.get_customer_assets(customer_id, asset_type)
            return success_response(assets)
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)


@ns.route("/customers/<int:customer_id>/services/<int:service_id>/assets")
@ns.param("customer_id", "The customer ID")
@ns.param("service_id", "The service ID")
class CustomerAssetsByService(Resource):
    """Fetch customer assets that are applicable to a specific service."""

    @ns.doc("list_customer_assets_by_service")
    def get(self, customer_id: int, service_id: int):
        """Return customer assets filtered by service plan asset rules."""
        try:
            plans = _plan_svc.get_all_plans(service_id=service_id)
            active_plans = [p for p in plans if p.get("is_active")]

            if not active_plans:
                return success_response([])

            applicable_types: set[str] = set()
            unrestricted = False
            for plan in active_plans:
                plan_types = plan.get("rules", {}).get("applicable_asset_types")
                if not plan_types:
                    unrestricted = True
                    break
                applicable_types.update(plan_types)

            assets = _customer_svc.get_customer_assets_by_types(
                customer_id,
                None if unrestricted else applicable_types,
            )
            return success_response(assets)
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)


@ns.route("/subscriptions")
class SubscriptionCreate(Resource):
    """Create a subscription request."""

    @ns.doc("create_subscription")
    @ns.expect(subscription_input_model)
    def post(self):
        """Submit a new subscription request."""
        try:
            data = SubscriptionCreateSchema(**request.get_json())
            result = _subscription_svc.create_subscription(
                customer_id=data.customer_id,
                plan_id=data.plan_id,
                duration_months=data.duration_months,
                asset_ids=data.asset_ids,
                days_remaining=data.days_remaining,
            )
            return success_response(result, 201)
        except PydanticValidationError as err:
            return error_response(
                "Invalid input", "VALIDATION_ERROR", 400,
                details=err.errors(),
            )
        except AppError as err:
            return error_response(
                err.message, err.error_code, err.status_code,
                details=getattr(err, "violations", None) or getattr(err, "details", None),
            )


@ns.route("/subscriptions/<int:request_id>")
@ns.param("request_id", "The subscription request ID")
class SubscriptionDetail(Resource):
    """View subscription request details."""

    @ns.doc("get_subscription")
    def get(self, request_id: int):
        """Fetch a subscription request with cost breakdown."""
        try:
            result = _subscription_svc.get_subscription(request_id)
            return success_response(result)
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)
