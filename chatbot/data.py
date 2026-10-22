"""Mock account data and plan catalog for ConnectX Telecom.

This module provides the single source of truth for the customer account details
and available broadband plans.
"""

from typing import Any, Dict, List

# Exactly as specified in requirements
ACCOUNT_DATA: Dict[str, Any] = {
    "customer_name": "Priya Sharma",
    "plan": "ConnectX Pro — 150 Mbps",
    "monthly_charge": "₹999",
    "billing_cycle": "1st of every month",
    "last_bill": "₹999 (paid)",
    "current_status": "Active",
    "known_outages": "None in your area",
    "contract_end": "March 2026",
}

# Clearly-labelled MOCK PLAN CATALOG
PLAN_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "ConnectX Basic",
        "speed": "50 Mbps",
        "monthly_price": 599,
        "price_display": "₹599",
        "is_current": False,
    },
    {
        "name": "ConnectX Pro",
        "speed": "150 Mbps",
        "monthly_price": 999,
        "price_display": "₹999",
        "is_current": True,
    },
    {
        "name": "ConnectX Max",
        "speed": "300 Mbps",
        "monthly_price": 1299,
        "price_display": "₹1,299",
        "is_current": False,
    },
    {
        "name": "ConnectX Ultra",
        "speed": "1 Gbps",
        "monthly_price": 1999,
        "price_display": "₹1,999",
        "is_current": False,
    },
]

# Business rules / reference notes
CONTRACT_NOTE = (
    "NOTE: contract_end 'March 2026' is already in the past (today is October 2026). "
    "If asked about the contract, state what the data says ('March 2026'), mention that it "
    "appears to have ended / may now be month-to-month, and suggest confirming with support."
)

DATA_CONSTRAINTS_NOTE = (
    "The model must ONLY quote plans/prices from this catalog and the account data. "
    "For anything not in the data (upgrade fees, install dates, technician visits, router costs, etc.) "
    "say it is not available in the records and offer a human agent. Never invent numbers."
)


def format_account_block() -> str:
    """Formats customer account data as a clean readable block for the LLM system prompt."""
    lines = ["CURRENT CUSTOMER ACCOUNT:"]
    for key, val in ACCOUNT_DATA.items():
        clean_key = key.replace("_", " ").title()
        lines.append(f"- {clean_key}: {val}")
    return "\n".join(lines)


def format_catalog_block() -> str:
    """Formats the broadband plan catalog for the LLM system prompt."""
    lines = ["OFFICIAL CONNECTX BROADBAND PLAN CATALOG:"]
    for plan in PLAN_CATALOG:
        curr_tag = " (current plan)" if plan["is_current"] else ""
        lines.append(
            f"- {plan['name']} — {plan['speed']} — {plan['price_display']}/month{curr_tag}"
        )
    return "\n".join(lines)
