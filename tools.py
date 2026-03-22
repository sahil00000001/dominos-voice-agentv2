"""
tools.py — Domino's Pizza Voice Agent Tool Definitions
=======================================================
Five tool handlers: confirm_order, add_upsell_item, finalise_order,
log_complaint, and initiate_refund.  Each receives a FunctionCallParams
object from Pipecat, executes business logic, and returns a result string
back to the LLM via params.result_callback().

Order events are pushed to the UI via web_ui module functions.
"""

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams

from web_ui import add_log, add_complaint, update_order, set_scenario


# ── Tool Handlers ──────────────────────────────────────────────────────────

async def confirm_order(params: FunctionCallParams) -> None:
    args             = params.arguments
    customer_name    = args.get("customer_name", "Customer")
    order_items      = args.get("order_items", [])
    delivery_address = args.get("delivery_address", "")
    order_total_inr  = args.get("order_total_inr", 0.0)

    add_log(f"[bold green]✔ ORDER CONFIRMED[/bold green]  {customer_name}  ·  "
            f"₹{order_total_inr:.0f}  ·  {', '.join(order_items)}")
    add_log(f"  [dim]📍 Delivering to:[/dim] {delivery_address}")

    update_order(
        customer_name=customer_name,
        order_items=order_items,
        delivery_address=delivery_address,
        order_total_inr=order_total_inr,
        status="confirmed",
        upsell_items=[],
        estimated_delivery_minutes=35,
    )
    set_scenario("Order")

    await params.result_callback(
        f"Order logged. Total: ₹{order_total_inr:.2f}. "
        "DO NOT repeat or summarise the order. "
        "Ask ONE upsell question now (single short sentence)."
    )


async def add_upsell_item(params: FunctionCallParams) -> None:
    args           = params.arguments
    item_name      = args.get("item_name", "item")
    item_price_inr = args.get("item_price_inr", 0.0)

    add_log(f"[bold yellow]➕ UPSELL ADDED[/bold yellow]  {item_name}  ·  ₹{item_price_inr:.0f}")

    update_order(upsell_items=[{"name": item_name, "price": item_price_inr}])

    await params.result_callback(
        f"{item_name} added. Updated total includes ₹{item_price_inr:.0f}. "
        "DO NOT repeat or summarise the order. "
        "Say ONLY the closing line: delivery in 30-45 minutes, thank by name, goodbye. "
        "Then call finalise_order immediately."
    )


async def finalise_order(params: FunctionCallParams) -> None:
    args                       = params.arguments
    customer_name              = args.get("customer_name", "Customer")
    final_order_summary        = args.get("final_order_summary", "")
    estimated_delivery_minutes = args.get("estimated_delivery_minutes", 35)

    add_log(f"[bold cyan]🏁 ORDER FINALISED[/bold cyan]  {customer_name}  "
            f"·  ETA {estimated_delivery_minutes} min")
    add_log(f"  [dim]{final_order_summary}[/dim]")

    update_order(status="finalised", estimated_delivery_minutes=estimated_delivery_minutes)

    await params.result_callback("Order finalised. Call complete. Say nothing more.")


async def log_complaint(params: FunctionCallParams) -> None:
    """
    Call when the customer reports a problem: food poisoning, wrong order,
    cold food, missing delivery, bad quality, etc.

    Expected arguments:
        customer_name   (str) — Customer's first name
        complaint_type  (str) — One of: food_poisoning / wrong_order /
                                late_delivery / cold_food / missing_order / general
        complaint_text  (str) — Full complaint as stated by the customer
    """
    args           = params.arguments
    customer_name  = args.get("customer_name", "Customer")
    complaint_type = args.get("complaint_type", "general")
    complaint_text = args.get("complaint_text", "")

    add_log(
        f"[bold red]⚠ COMPLAINT LOGGED[/bold red]  {customer_name}  ·  "
        f"{complaint_type.replace('_', ' ').upper()}"
    )
    add_log(f"  [dim]{complaint_text}[/dim]")

    add_complaint(customer_name, complaint_type, complaint_text)
    set_scenario(complaint_type.replace("_", " ").title())

    await params.result_callback(
        f"Complaint logged: {complaint_type}. Quality team notified. "
        "Acknowledge the complaint with genuine empathy — one sentence only."
    )


async def initiate_refund(params: FunctionCallParams) -> None:
    """
    Call when the customer is granted a monetary refund.

    Expected arguments:
        customer_name  (str)   — Customer's first name
        refund_amount  (float) — Amount in INR (0.0 if unknown)
        reason         (str)   — Short reason for the refund
    """
    args          = params.arguments
    customer_name = args.get("customer_name", "Customer")
    refund_amount = args.get("refund_amount", 0.0)
    reason        = args.get("reason", "")

    add_log(
        f"[bold magenta]💜 REFUND INITIATED[/bold magenta]  {customer_name}  "
        f"·  ₹{refund_amount:.0f}  ·  {reason}"
    )

    add_complaint(customer_name, "refund", f"₹{refund_amount:.0f} — {reason}")
    set_scenario("Refund")

    await params.result_callback(
        f"Refund of ₹{refund_amount:.0f} initiated for {customer_name}. "
        "Tell the customer: 3 to 5 business days. One sentence only."
    )


# ── Tool Schema Definitions ────────────────────────────────────────────────

def get_tool_definitions() -> ToolsSchema:

    confirm_order_schema = FunctionSchema(
        name="confirm_order",
        description=(
            "Call once the customer has verbally confirmed their full order and address. "
            "Pass all order details and the calculated total."
        ),
        properties={
            "customer_name":    {"type": "string", "description": "Customer's first name."},
            "order_items":      {
                "type": "array", "items": {"type": "string"},
                "description": "List of ordered items e.g. ['1x Farmhouse Pizza (Medium)'].",
            },
            "delivery_address": {"type": "string", "description": "Full delivery address."},
            "order_total_inr":  {"type": "number", "description": "Order total in Indian Rupees."},
        },
        required=["customer_name", "order_items", "delivery_address", "order_total_inr"],
    )

    add_upsell_item_schema = FunctionSchema(
        name="add_upsell_item",
        description="Call when the customer agrees to an upsell offer.",
        properties={
            "item_name":      {"type": "string", "description": "Name of the upsell item."},
            "item_price_inr": {"type": "number", "description": "Price in Indian Rupees."},
        },
        required=["item_name", "item_price_inr"],
    )

    finalise_order_schema = FunctionSchema(
        name="finalise_order",
        description="Call at the very end of the call after thanking the customer.",
        properties={
            "customer_name":              {"type": "string", "description": "Customer's first name."},
            "final_order_summary":        {"type": "string", "description": "Complete human-readable summary."},
            "estimated_delivery_minutes": {"type": "integer", "description": "Delivery ETA in minutes (default 35)."},
        },
        required=["customer_name", "final_order_summary"],
    )

    log_complaint_schema = FunctionSchema(
        name="log_complaint",
        description=(
            "Call IMMEDIATELY when the customer reports any complaint: food poisoning, "
            "wrong order, cold food, missing delivery, or bad quality. "
            "Do NOT wait — log it as soon as the complaint is understood."
        ),
        properties={
            "customer_name":  {"type": "string", "description": "Customer's first name."},
            "complaint_type": {
                "type": "string",
                "description": (
                    "Category: 'food_poisoning', 'wrong_order', 'late_delivery', "
                    "'cold_food', 'missing_order', or 'general'."
                ),
            },
            "complaint_text": {"type": "string", "description": "Full complaint as stated."},
        },
        required=["customer_name", "complaint_type", "complaint_text"],
    )

    initiate_refund_schema = FunctionSchema(
        name="initiate_refund",
        description=(
            "Call when the customer is owed a monetary refund. "
            "Use after refund request or when replacement is not possible."
        ),
        properties={
            "customer_name":  {"type": "string", "description": "Customer's first name."},
            "refund_amount":  {"type": "number", "description": "Refund amount in INR (0 if unknown)."},
            "reason":         {"type": "string", "description": "Short reason for the refund."},
        },
        required=["customer_name", "reason"],
    )

    return ToolsSchema(
        standard_tools=[
            confirm_order_schema,
            add_upsell_item_schema,
            finalise_order_schema,
            log_complaint_schema,
            initiate_refund_schema,
        ]
    )
