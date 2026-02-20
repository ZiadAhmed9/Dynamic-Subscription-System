"""Dashboard API namespace — endpoints for administration.

All routes delegate to service-layer classes. Controllers are kept thin
(parse → validate → call service → respond).
"""

from flask import request
from flask_restx import Namespace, Resource, fields
from pydantic import ValidationError as PydanticValidationError

from app.schemas.service_schema import ServiceCreateSchema
from app.schemas.plan_schema import PlanCreateSchema
from app.schemas.customer_schema import CustomerCreateSchema, AssetCreateSchema
from app.schemas.subscription_schema import SubscriptionStatusUpdateSchema
from app.schemas.response import success_response, error_response
from app.services.service_service import ServiceService
from app.services.plan_service import PlanService
from app.services.customer_service import CustomerService
from app.services.subscription_service import SubscriptionService
from app.domain.exceptions import AppError

ns = Namespace("dashboard", description="Dashboard / Administration APIs")

# ---------------------------------------------------------------------------
# Swagger models
# ---------------------------------------------------------------------------
service_model = ns.model("ServiceInput", {
    "name": fields.String(required=True, description="Service name"),
    "description": fields.String(description="Service description"),
    "is_active": fields.Boolean(default=True),
})

plan_rules_model = ns.model("PlanRules", {
    "pricing_type": fields.String(required=True, description="Dynamic pricing type key"),
    "price": fields.Float(required=True),
    "billing_cycle_months": fields.Integer(default=1),
    "min_duration_months": fields.Integer(default=1),
    "payment_type": fields.String(default="prepaid", enum=["prepaid", "postpaid"]),
    "requires_inspection": fields.Boolean(default=False),
    "inspection_fee": fields.Float(default=0),
    "pricing_config": fields.Raw(description="Required for custom pricing_type values"),
    "proration": fields.Raw(description="Proration config object"),
    "applicable_asset_types": fields.List(fields.String, description="Allowed asset types"),
})

plan_model = ns.model("PlanInput", {
    "service_id": fields.Integer(required=True),
    "name": fields.String(required=True),
    "rules": fields.Nested(plan_rules_model, required=True),
    "is_active": fields.Boolean(default=True),
})

customer_model = ns.model("CustomerInput", {
    "name": fields.String(required=True),
    "email": fields.String(required=True),
    "phone": fields.String(),
})

asset_model = ns.model("AssetInput", {
    "asset_type": fields.String(required=True),
    "label": fields.String(required=True),
    "metadata": fields.Raw(description="Asset metadata (area, color, etc.)"),
})

status_model = ns.model("StatusUpdate", {
    "status": fields.String(
        required=True,
        enum=["pending", "pending_inspection", "active", "cancelled", "expired"],
    ),
})

# ---------------------------------------------------------------------------
# Service instances
# ---------------------------------------------------------------------------
_service_svc = ServiceService()
_plan_svc = PlanService()
_customer_svc = CustomerService()
_subscription_svc = SubscriptionService()


# ---------------------------------------------------------------------------
# Service routes
# ---------------------------------------------------------------------------
@ns.route("/services")
class ServiceList(Resource):
    """Create and list services."""

    @ns.doc("list_services")
    def get(self):
        """List all services."""
        return success_response(_service_svc.get_all_services())

    @ns.doc("create_service")
    @ns.expect(service_model)
    def post(self):
        """Create a new service."""
        try:
            data = ServiceCreateSchema(**request.get_json())
            result = _service_svc.create_service(**data.model_dump())
            return success_response(result, 201)
        except PydanticValidationError as err:
            return error_response("Invalid input", "VALIDATION_ERROR", 400, details=err.errors())
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)


@ns.route("/services/<int:service_id>")
@ns.param("service_id", "The service ID")
class ServiceDetail(Resource):
    """Update a service."""

    @ns.doc("update_service")
    @ns.expect(service_model)
    def put(self, service_id: int):
        """Update an existing service."""
        try:
            data = ServiceCreateSchema(**request.get_json())
            result = _service_svc.update_service(service_id, **data.model_dump())
            return success_response(result)
        except PydanticValidationError as err:
            return error_response("Invalid input", "VALIDATION_ERROR", 400, details=err.errors())
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)


# ---------------------------------------------------------------------------
# Plan routes
# ---------------------------------------------------------------------------
@ns.route("/plans")
class PlanList(Resource):
    """Create and list subscription plans."""

    @ns.doc("list_plans")
    def get(self):
        """List all plans (optional: ?service_id=)."""
        service_id = request.args.get("service_id", type=int)
        return success_response(_plan_svc.get_all_plans(service_id))

    @ns.doc("create_plan")
    @ns.expect(plan_model)
    def post(self):
        """Create a new subscription plan with rules."""
        try:
            data = PlanCreateSchema(**request.get_json())
            result = _plan_svc.create_plan(
                service_id=data.service_id,
                name=data.name,
                rules=data.rules.model_dump(),
                is_active=data.is_active,
            )
            return success_response(result, 201)
        except PydanticValidationError as err:
            return error_response("Invalid input", "VALIDATION_ERROR", 400, details=err.errors())
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)


@ns.route("/plans/<int:plan_id>")
@ns.param("plan_id", "The plan ID")
class PlanDetail(Resource):
    """Update a subscription plan."""

    @ns.doc("update_plan")
    @ns.expect(plan_model)
    def put(self, plan_id: int):
        """Update a plan and its rules."""
        try:
            data = PlanCreateSchema(**request.get_json())
            result = _plan_svc.update_plan(
                plan_id,
                name=data.name,
                rules=data.rules.model_dump(),
                is_active=data.is_active,
            )
            return success_response(result)
        except PydanticValidationError as err:
            return error_response("Invalid input", "VALIDATION_ERROR", 400, details=err.errors())
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)


# ---------------------------------------------------------------------------
# Subscription routes
# ---------------------------------------------------------------------------
@ns.route("/subscriptions")
class SubscriptionList(Resource):
    """List subscription requests with filters."""

    @ns.doc("list_subscriptions")
    def get(self):
        """List subscriptions (?status=, ?needs_inspection=true)."""
        status = request.args.get("status")
        needs_inspection = request.args.get("needs_inspection", "").lower() == "true" or None
        return success_response(
            _subscription_svc.list_subscriptions(status, needs_inspection),
        )


@ns.route("/subscriptions/<int:request_id>/status")
@ns.param("request_id", "The subscription request ID")
class SubscriptionStatusUpdate(Resource):
    """Update a subscription request's status."""

    @ns.doc("update_subscription_status")
    @ns.expect(status_model)
    def patch(self, request_id: int):
        """Change the status of a subscription request."""
        try:
            data = SubscriptionStatusUpdateSchema(**request.get_json())
            result = _subscription_svc.update_status(request_id, data.status)
            return success_response(result)
        except PydanticValidationError as err:
            return error_response("Invalid input", "VALIDATION_ERROR", 400, details=err.errors())
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)


# ---------------------------------------------------------------------------
# Customer / Asset routes (for testability via Postman)
# ---------------------------------------------------------------------------
@ns.route("/customers")
class CustomerCreate(Resource):
    """Create a customer."""

    @ns.doc("create_customer")
    @ns.expect(customer_model)
    def post(self):
        """Create a new customer."""
        try:
            data = CustomerCreateSchema(**request.get_json())
            result = _customer_svc.create_customer(**data.model_dump())
            return success_response(result, 201)
        except PydanticValidationError as err:
            return error_response("Invalid input", "VALIDATION_ERROR", 400, details=err.errors())
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)


@ns.route("/customers/<int:customer_id>/assets")
@ns.param("customer_id", "The customer ID")
class CustomerAssetCreate(Resource):
    """Add an asset to a customer."""

    @ns.doc("create_asset")
    @ns.expect(asset_model)
    def post(self, customer_id: int):
        """Add a new asset to a customer."""
        try:
            data = AssetCreateSchema(**request.get_json())
            result = _customer_svc.add_asset(
                customer_id=customer_id,
                asset_type=data.asset_type,
                label=data.label,
                metadata=data.metadata,
            )
            return success_response(result, 201)
        except PydanticValidationError as err:
            return error_response("Invalid input", "VALIDATION_ERROR", 400, details=err.errors())
        except AppError as err:
            return error_response(err.message, err.error_code, err.status_code)
