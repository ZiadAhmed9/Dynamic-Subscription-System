"""Postman-style runtime tests against the live Flask server.

Tests every guide.md requirement via HTTP calls to localhost:5000.
Run with: python postman_test.py
"""

import json
import urllib.request
import sys
import time

BASE = "http://localhost:5000"
PASS = 0
FAIL = 0
TS = int(time.time())  # unique suffix to avoid duplicates


def req(method, path, data=None):
    """Make an HTTP request and return (status_code, json_body)."""
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


# =====================================================================
print("\n>>> 1. DASHBOARD: Create a new service dynamically")
# =====================================================================
status, body = req("POST", "/dashboard/services", {"name": f"Pest Control {TS}", "description": "Pest removal service"})
check("Create service returns 201", status == 201)
check("Response has service data", f"Pest Control {TS}" in str(body.get("data", {}).get("name", "")))
new_service_id = body.get("data", {}).get("id")

# =====================================================================
print("\n>>> 2. DASHBOARD: Update a service")
# =====================================================================
status, body = req("PUT", f"/dashboard/services/{new_service_id}", {"name": f"Pest Pro {TS}", "description": "Updated"})
check("Update service returns 200", status == 200)
check("Name updated correctly", f"Pest Pro {TS}" in str(body.get("data", {}).get("name", "")))

# =====================================================================
print("\n>>> 3. DASHBOARD: Create a plan with ALL rule types")
# =====================================================================
plan_rules = {
    "pricing_type": "per_asset",
    "price": 75.0,
    "billing_cycle_months": 3,
    "min_duration_months": 6,
    "payment_type": "postpaid",
    "requires_inspection": True,
    "inspection_fee": 30.0,
    "proration": {"enabled": True, "method": "daily"},
    "applicable_asset_types": ["house"],
}
status, body = req("POST", "/dashboard/plans", {
    "service_id": new_service_id,
    "name": "Pest Quarterly",
    "rules": plan_rules,
})
check("Create plan returns 201", status == 201)
plan_data = body.get("data", {})
check("Plan has rules stored", plan_data.get("rules", {}).get("pricing_type") == "per_asset")
check("Min duration in rules", plan_data.get("rules", {}).get("min_duration_months") == 6)
check("Billing cycle in rules", plan_data.get("rules", {}).get("billing_cycle_months") == 3)
check("Payment type in rules", plan_data.get("rules", {}).get("payment_type") == "postpaid")
check("Inspection required in rules", plan_data.get("rules", {}).get("requires_inspection") is True)
check("Inspection fee in rules", plan_data.get("rules", {}).get("inspection_fee") == 30.0)
check("Proration in rules", plan_data.get("rules", {}).get("proration", {}).get("enabled") is True)
check("Asset types in rules", plan_data.get("rules", {}).get("applicable_asset_types") == ["house"])
new_plan_id = plan_data.get("id")

# =====================================================================
print("\n>>> 4. DASHBOARD: Update a plan with new rules")
# =====================================================================
updated_rules = {**plan_rules, "price": 80.0, "min_duration_months": 3}
status, body = req("PUT", f"/dashboard/plans/{new_plan_id}", {
    "service_id": new_service_id,
    "name": "Pest Quarterly Updated",
    "rules": updated_rules,
})
check("Update plan returns 200", status == 200)
check("Plan name updated", body.get("data", {}).get("name") == "Pest Quarterly Updated")
check("Plan price updated", body.get("data", {}).get("rules", {}).get("price") == 80.0)

# =====================================================================
print("\n>>> 5. DASHBOARD: Create a customer")
# =====================================================================
status, body = req("POST", "/dashboard/customers", {"name": f"Test User {TS}", "email": f"test{TS}@example.com", "phone": f"+{TS}"})
check("Create customer returns 201", status == 201)
customer_id = body.get("data", {}).get("id")

# =====================================================================
print("\n>>> 6. DASHBOARD: Add assets to customer")
# =====================================================================
status, body = req("POST", f"/dashboard/customers/{customer_id}/assets", {
    "asset_type": "house", "label": "Main House", "metadata": {"area": 200},
})
check("Add asset returns 201", status == 201)
asset_id = body.get("data", {}).get("id")

status, body = req("POST", f"/dashboard/customers/{customer_id}/assets", {
    "asset_type": "house", "label": "Guest House", "metadata": {"area": 100},
})
check("Add second asset returns 201", status == 201)
asset_id_2 = body.get("data", {}).get("id")

# =====================================================================
print("\n>>> 7. MOBILE: Fetch available services and subscription plans")
# =====================================================================
status, body = req("GET", "/mobile/services")
check("GET /mobile/services returns 200", status == 200)
services = body.get("data", [])
check("Returns multiple services", len(services) >= 4, f"got {len(services)}")
pest_svc = [s for s in services if f"Pest Pro {TS}" in str(s.get("name", ""))]
check("Newly created service appears", len(pest_svc) == 1)
check("Service has plans attached", len(pest_svc[0].get("plans", [])) > 0 if pest_svc else False)

# =====================================================================
print("\n>>> 8. MOBILE: Fetch customer assets (by type)")
# =====================================================================
status, body = req("GET", f"/mobile/customers/{customer_id}/assets")
check("GET customer assets returns 200", status == 200)
check("Returns correct number of assets", len(body.get("data", [])) == 2)

status, body = req("GET", f"/mobile/customers/{customer_id}/assets?asset_type=house")
check("Filter by asset_type works", len(body.get("data", [])) == 2)

# =====================================================================
print("\n>>> 9. MOBILE: Fetch customer assets by service")
# =====================================================================
status, body = req("GET", f"/mobile/customers/{customer_id}/services/{new_service_id}/assets")
check("GET assets by service returns 200", status == 200)
check("Returns only applicable assets (house type)", len(body.get("data", [])) == 2)

# =====================================================================
print("\n>>> 10. MOBILE: Create a subscription request")
# =====================================================================
status, body = req("POST", "/mobile/subscriptions", {
    "customer_id": customer_id,
    "plan_id": new_plan_id,
    "duration_months": 6,
    "asset_ids": [asset_id, asset_id_2],
    "days_remaining": 15,
})
print(f"  DEBUG sub create: status={status} body={body}")
check("Create subscription returns 201", status == 201)
sub_data = body.get("data", {})
check("Subscription has total_cost", sub_data.get("total_cost") is not None)
check("Subscription has cost_breakdown", sub_data.get("cost_breakdown") is not None)
check("Cost breakdown has base_cost", "base_cost" in sub_data.get("cost_breakdown", {}))
check("Cost breakdown has inspection_fee", "inspection_fee" in sub_data.get("cost_breakdown", {}))
check("Total cost > 0", sub_data.get("total_cost", 0) > 0, f"got {sub_data.get('total_cost')}")
sub_id = sub_data.get("id")

# =====================================================================
print("\n>>> 11. MOBILE: View subscription request with cost breakdown")
# =====================================================================
status, body = req("GET", f"/mobile/subscriptions/{sub_id}")
check("GET subscription detail returns 200", status == 200)
check("Detail has cost_breakdown", body.get("data", {}).get("cost_breakdown") is not None)

# =====================================================================
print("\n>>> 12. DASHBOARD: View subscription requests")
# =====================================================================
status, body = req("GET", "/dashboard/subscriptions")
check("List subscriptions returns 200", status == 200)
check("Returns subscription list", len(body.get("data", [])) > 0)

# =====================================================================
print("\n>>> 13. DASHBOARD: Filter subscriptions requiring inspection")
# =====================================================================
status, body = req("GET", "/dashboard/subscriptions?needs_inspection=true")
check("Filter by needs_inspection returns 200", status == 200)
check("Returns inspection-requiring subscriptions", len(body.get("data", [])) > 0)

# =====================================================================
print("\n>>> 14. DASHBOARD: Update subscription status")
# =====================================================================
status, body = req("PATCH", f"/dashboard/subscriptions/{sub_id}/status", {"status": "active"})
check("Update status returns 200", status == 200)
check("Status updated to active", body.get("data", {}).get("status") == "active")

# =====================================================================
print("\n>>> 15. RULE VALIDATION: Duration too short (should reject)")
# =====================================================================
status, body = req("POST", "/mobile/subscriptions", {
    "customer_id": customer_id,
    "plan_id": new_plan_id,
    "duration_months": 1,
    "asset_ids": [asset_id],
})
check("Short duration rejected (not 201)", status != 201, f"got {status}")
check("Error mentions violation", "RULE" in body.get("error_code", "").upper() or "violation" in str(body).lower())

# =====================================================================
print("\n>>> 16. RULE VALIDATION: Billing cycle alignment (should reject)")
# =====================================================================
status, body = req("POST", "/mobile/subscriptions", {
    "customer_id": customer_id,
    "plan_id": new_plan_id,
    "duration_months": 4,
    "asset_ids": [asset_id],
})
check("Non-aligned billing cycle rejected", status != 201, f"got {status}")

# =====================================================================
print("\n>>> 17. DYNAMIC: New service works without code changes")
# =====================================================================
# Create a completely new service + plan + subscription in one flow
status, svc = req("POST", "/dashboard/services", {"name": f"Window Cleaning {TS}"})
check("Create new service", status == 201)
if status != 201:
    print("  [FAIL] Skipping rest of test 17 — service creation failed")
else:
    wc_id = svc["data"]["id"]

    status, plan = req("POST", "/dashboard/plans", {
        "service_id": wc_id,
        "name": f"Window Basic {TS}",
        "rules": {"pricing_type": "fixed", "price": 100, "billing_cycle_months": 1, "min_duration_months": 1},
    })
    check("Create plan for new service", status == 201)
    wc_plan_id = plan["data"]["id"]

    status, sub = req("POST", "/mobile/subscriptions", {
        "customer_id": customer_id,
        "plan_id": wc_plan_id,
        "duration_months": 1,
        "asset_ids": [],
    })
    check("Subscribe to brand new service (no code change)", status == 201)
    check("Cost calculated correctly for new service", sub.get("data", {}).get("total_cost") == 100)

# =====================================================================
# SUMMARY
# =====================================================================
print(f"\n{'='*50}")
print(f"  RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
print(f"{'='*50}")

if FAIL > 0:
    print("\nWARNING: Some tests failed! Review above.")
    sys.exit(1)
else:
    print("\nAll tests passed! Ready to submit.")
    sys.exit(0)
