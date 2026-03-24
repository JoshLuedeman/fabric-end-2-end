"""
Fabric User Data Function: Approve Discount
Called from Power BI Translytical Task Flow when a sales manager approves a discount request.
FabCon 2026 feature.
"""
import json
import logging
from datetime import datetime, timezone


def main(request: dict) -> dict:
    """
    Process a discount approval request from Power BI.

    Args:
        request: Dict containing:
            - customer_id: str
            - product_id: str
            - original_price: float
            - discount_pct: float
            - approved_by: str
            - reason: str

    Returns:
        Dict with approval result and new price
    """
    customer_id = request.get("customer_id")
    product_id = request.get("product_id")
    original_price = request.get("original_price", 0)
    discount_pct = request.get("discount_pct", 0)
    approved_by = request.get("approved_by", "unknown")
    reason = request.get("reason", "")

    # Business rules
    if discount_pct > 30:
        return {
            "status": "rejected",
            "message": "Discount exceeds maximum allowed (30%). Requires VP approval.",
            "requires_escalation": True,
        }

    new_price = round(original_price * (1 - discount_pct / 100), 2)

    # Write approval record to Fabric Warehouse
    approval_record = {
        "approval_id": f"DA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "customer_id": customer_id,
        "product_id": product_id,
        "original_price": original_price,
        "discount_pct": discount_pct,
        "new_price": new_price,
        "approved_by": approved_by,
        "reason": reason,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "status": "approved",
    }

    logging.info(f"Discount approved: {json.dumps(approval_record)}")

    return {
        "status": "approved",
        "approval_id": approval_record["approval_id"],
        "new_price": new_price,
        "message": f"Discount of {discount_pct}% approved for customer {customer_id}. New price: ${new_price}",
    }
