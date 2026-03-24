"""
Fabric User Data Function: Reorder Inventory
Called from Power BI Translytical Task Flow when an operations manager triggers a reorder.
FabCon 2026 feature.
"""
import json
import logging
from datetime import datetime, timedelta, timezone


def main(request: dict) -> dict:
    """
    Process an inventory reorder request from Power BI.

    Args:
        request: Dict containing:
            - product_id: str
            - store_id: str
            - reorder_quantity: int
            - priority: str (Normal/Urgent/Critical)
            - requested_by: str

    Returns:
        Dict with reorder confirmation and estimated delivery
    """
    product_id = request.get("product_id")
    store_id = request.get("store_id")
    reorder_quantity = request.get("reorder_quantity", 0)
    priority = request.get("priority", "Normal")
    requested_by = request.get("requested_by", "unknown")

    # Business rules for delivery estimates
    delivery_days = {
        "Normal": 7,
        "Urgent": 3,
        "Critical": 1,
    }

    est_delivery = datetime.now(timezone.utc) + timedelta(
        days=delivery_days.get(priority, 7)
    )

    # Validate
    if reorder_quantity <= 0:
        return {
            "status": "rejected",
            "message": "Reorder quantity must be positive.",
        }

    if reorder_quantity > 10000:
        return {
            "status": "pending_approval",
            "message": f"Large order ({reorder_quantity} units) requires supply chain manager approval.",
            "requires_escalation": True,
        }

    # Create reorder record
    reorder_record = {
        "reorder_id": f"RO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{store_id}",
        "product_id": product_id,
        "store_id": store_id,
        "quantity": reorder_quantity,
        "priority": priority,
        "requested_by": requested_by,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "estimated_delivery": est_delivery.isoformat(),
        "status": "submitted",
    }

    logging.info(f"Reorder submitted: {json.dumps(reorder_record)}")

    return {
        "status": "submitted",
        "reorder_id": reorder_record["reorder_id"],
        "estimated_delivery": est_delivery.strftime("%Y-%m-%d"),
        "message": (
            f"Reorder {reorder_record['reorder_id']}: {reorder_quantity} units of "
            f"{product_id} for {store_id}. Est. delivery: {est_delivery.strftime('%Y-%m-%d')}"
        ),
    }
