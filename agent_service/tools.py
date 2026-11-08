"""
Didactic Tools and Simulated Backend Services for Microsoft Agent Service.
Includes:
- Billing Tools (Invoice lookup, refund processing)
- Technical Support Tools (Service health check, container restart)
- In-memory mock database that updates state dynamically.
"""

import json
from typing import Any, Dict
from .models import ToolDefinition

# Simulated In-Memory Databases
INVOICES_DB: Dict[str, Dict[str, Any]] = {
    "INV-8821": {
        "invoice_id": "INV-8821",
        "customer": "Acme Corp (Cust #891)",
        "amount": 120.00,
        "currency": "USD",
        "status": "Paid (Duplicate charge reported)",
        "date": "2026-11-05",
        "items": ["Enterprise Seat Add-on (Duplicate item)"],
    },
    "INV-4010": {
        "invoice_id": "INV-4010",
        "customer": "Globex Retail",
        "amount": 340.00,
        "currency": "USD",
        "status": "Unpaid / Pending",
        "date": "2026-11-01",
        "items": ["Cloud Storage Addon 10TB"],
    },
    "INV-1002": {
        "invoice_id": "INV-1002",
        "customer": "Wayne Enterprises",
        "amount": 59.99,
        "currency": "USD",
        "status": "Paid",
        "date": "2026-10-28",
        "items": ["Standard API Developer Tier"],
    },
    "001Z": {
        "invoice_id": "001Z",
        "customer": "Apex Innovations (Cust #001)",
        "amount": 250.00,
        "currency": "USD",
        "status": "Paid",
        "date": "2026-11-06",
        "items": ["Custom AI Consulting & Deployment Setup"],
    },
}

SERVICES_DB: Dict[str, Dict[str, Any]] = {
    "payment-gateway": {
        "service_name": "payment-gateway",
        "cluster": "prod-us-east-1",
        "status": "DEGRADED",
        "http_500_rate": "42%",
        "latency_ms": 1450,
        "active_replicas": "1/3",
        "last_incident": "OOMKilled pod in region us-east-1",
    },
    "auth-service": {
        "service_name": "auth-service",
        "cluster": "prod-us-west-2",
        "status": "HEALTHY",
        "http_500_rate": "0.01%",
        "latency_ms": 42,
        "active_replicas": "3/3",
        "last_incident": "None (all checks green)",
    },
    "inventory-api": {
        "service_name": "inventory-api",
        "cluster": "prod-eu-central-1",
        "status": "HEALTHY",
        "http_500_rate": "0.00%",
        "latency_ms": 35,
        "active_replicas": "2/2",
        "last_incident": "None",
    },
}

# ==========================================
# Billing Tool Handlers
# ==========================================

def handle_lookup_invoice(invoice_id: str) -> str:
    """Finds details for a given invoice number."""
    clean_id = invoice_id.strip().upper()
    inv = INVOICES_DB.get(clean_id) or INVOICES_DB.get(f"INV-{clean_id}")
    if not inv:
        return json.dumps({
            "success": False,
            "error": f"Invoice '{invoice_id}' not found in the billing database. Available invoices: {', '.join(INVOICES_DB.keys())}."
        })
    return json.dumps({"success": True, "invoice": inv})


def handle_process_refund(invoice_id: str, amount: float, reason: str) -> str:
    """Processes a refund or credit for an invoice."""
    inv_key = invoice_id.strip().upper()
    if inv_key not in INVOICES_DB:
        return json.dumps({
            "success": False,
            "error": f"Invoice '{invoice_id}' does not exist. Cannot refund."
        })
    
    invoice = INVOICES_DB[inv_key]
    invoice["status"] = f"Refunded (${amount:.2f} credited)"
    invoice["refund_notes"] = reason

    return json.dumps({
        "success": True,
        "transaction_id": f"TX-REF-{abs(hash(inv_key)) % 100000}",
        "message": f"Successfully processed refund of ${amount:.2f} for invoice {inv_key}.",
        "reason": reason,
        "updated_status": invoice["status"]
    })


# ==========================================
# Tech Support Tool Handlers
# ==========================================

def handle_check_service_health(service_name: str) -> str:
    """Checks the operational health and metrics of a backend microservice."""
    key = service_name.strip().lower()
    svc = SERVICES_DB.get(key)
    if not svc:
        return json.dumps({
            "success": False,
            "error": f"Service '{service_name}' was not recognized. Available: {list(SERVICES_DB.keys())}"
        })
    return json.dumps({"success": True, "health": svc})


def handle_restart_service(service_name: str, region: str = "auto") -> str:
    """Restarts a microservice deployment and verifies recovery."""
    key = service_name.strip().lower()
    if key not in SERVICES_DB:
        return json.dumps({
            "success": False,
            "error": f"Cannot restart unknown service '{service_name}'."
        })
    
    svc = SERVICES_DB[key]
    # Update state to healthy
    svc["status"] = "HEALTHY (Recovered)"
    svc["http_500_rate"] = "0.00%"
    svc["latency_ms"] = 38
    svc["active_replicas"] = "3/3"
    svc["last_incident"] = f"Restarted by Technical Support Agent in {region}"

    return json.dumps({
        "success": True,
        "service_name": key,
        "cluster": svc["cluster"],
        "action": "Rolling container restart initiated and completed",
        "new_status": svc["status"],
        "message": f"Service '{key}' successfully restarted and responding with HTTP 200 OK."
    })


# ==========================================
# Tool Definitions (Schemas)
# ==========================================

TOOL_LOOKUP_INVOICE = ToolDefinition(
    name="lookup_invoice",
    description="Look up detailed billing information for a customer invoice by invoice ID (e.g. INV-8821).",
    parameters={
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": "string",
                "description": "The unique invoice identifier (e.g., 'INV-8821')."
            }
        },
        "required": ["invoice_id"]
    },
    handler=handle_lookup_invoice
)

TOOL_PROCESS_REFUND = ToolDefinition(
    name="process_refund",
    description="Process a monetary refund or credit for an invoice with a specified reason.",
    parameters={
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": "string",
                "description": "The unique invoice identifier (e.g., 'INV-8821')."
            },
            "amount": {
                "type": "number",
                "description": "The dollar amount to refund (e.g., 120.00)."
            },
            "reason": {
                "type": "string",
                "description": "The business justification or explanation for the refund."
            }
        },
        "required": ["invoice_id", "amount", "reason"]
    },
    handler=handle_process_refund
)

TOOL_CHECK_SERVICE_HEALTH = ToolDefinition(
    name="check_service_health",
    description="Inspect uptime, latency, error rates, and cluster health for a microservice.",
    parameters={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "The name of the service (e.g., 'payment-gateway', 'auth-service', 'inventory-api')."
            }
        },
        "required": ["service_name"]
    },
    handler=handle_check_service_health
)

TOOL_RESTART_SERVICE = ToolDefinition(
    name="restart_service",
    description="Execute a rolling restart of the specified microservice container deployment.",
    parameters={
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "The service to restart (e.g., 'payment-gateway')."
            },
            "region": {
                "type": "string",
                "description": "Target cloud region or 'auto'."
            }
        },
        "required": ["service_name"]
    },
    handler=handle_restart_service
)
