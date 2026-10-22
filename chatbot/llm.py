"""LLM client wrapper using generic OpenAI-compatible SDK.

Provides robust retry logic with exponential backoff on 429/5xx,
graceful fallback on failure, and an offline MOCK_LLM mode.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Defaults to gemini-3.8-flash for Gemini API compatibility, or fallback to gemini-2.5-flash
DEFAULT_MODEL = "gemini-3.8-flash"
FRIENDLY_FALLBACK = (
    "I apologize, Priya, but I am having trouble connecting to our service right now. "
    "Please try again in a moment, or reach out to our 24/7 ConnectX support team at 1800-CONNECTX."
)


def _get_env_config() -> tuple[Optional[str], str, str]:
    """Retrieves API key, base URL, and model from environment variables."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL
    model = (
        os.getenv("LLM_MODEL")
        or os.getenv("GEMINI_MODEL")
        or DEFAULT_MODEL
    )
    return api_key, base_url, model


def _mock_chat(system: str, messages: List[Dict[str, str]]) -> str:
    """Deterministic stub for running offline without an API key (MOCK_LLM=1)."""
    last_msg = messages[-1]["content"] if messages else ""
    last_lower = last_msg.lower().strip()

    # Pre-classifier check
    if "classify" in system.lower() or "pre-classifier" in system.lower() or "json" in system.lower():
        # Obvious out-of-scope triggers
        if any(w in last_lower for w in ["airtel", "jio", "competitor"]):
            return json.dumps({"in_scope": False, "category": "competitor_pricing"})
        if any(w in last_lower for w in ["landlord", "write an email", "recipe", "essay"]):
            return json.dumps({"in_scope": False, "category": "personal_advice"})
        if any(w in last_lower for w in ["weather", "mumbai", "news", "president", "capital"]):
            return json.dumps({"in_scope": False, "category": "general_knowledge"})
        # In-scope
        return json.dumps({"in_scope": True, "category": "telecom_support"})

    # Conversation summarizer check
    if "summarize" in system.lower() or "summary" in system.lower():
        return (
            "Conversation summary: The customer (Priya Sharma) inquired about their current "
            "ConnectX Pro 150 Mbps plan, reviewed faster upgrade options (Max 300 Mbps at ₹1,299 and "
            "Ultra 1 Gbps at ₹1,999), and checked pricing differences."
        )

    # Core assistant queries
    if "current plan" in last_lower or "what plan" in last_lower:
        return (
            "Hi Priya! You are currently on the ConnectX Pro plan offering 150 Mbps speeds at ₹999 per month. "
            "Your account status is Active and your last bill of ₹999 is paid."
        )

    if "faster option" in last_lower or "upgrade" in last_lower:
        return (
            "Yes, Priya! We offer two faster broadband options: ConnectX Max offering 300 Mbps at ₹1,299 per month, "
            "and ConnectX Ultra offering 1 Gbps at ₹1,999 per month."
        )

    if "how much more" in last_lower or "cost" in last_lower:
        return (
            "Upgrading to ConnectX Max (300 Mbps) would cost ₹300 more each month than your current ₹999 plan. "
            "If you prefer ConnectX Ultra (1 Gbps), that would be ₹1,000 more per month."
        )

    if "next bill" in last_lower or "billing cycle" in last_lower:
        return (
            "Hi Priya! Your billing cycle is on the 1st of every month, so your next bill will be generated "
            "on the 1st of next month."
        )

    if "outage" in last_lower:
        return (
            "Good news, Priya! There are currently no known outages in your area, and your ConnectX broadband "
            "connection status is Active."
        )

    if "contract" in last_lower:
        return (
            "According to your account data, your contract end date was March 2026. Because that date has passed, "
            "your service appears to have ended or transitioned to a month-to-month basis; please confirm with support."
        )

    # Out-of-scope fallback declines
    if "airtel" in last_lower:
        return (
            "I don't have information on competitor pricing like Airtel, but I would be glad to help you "
            "with any details regarding your ConnectX broadband plan, billing, or speed upgrades."
        )
    if "landlord" in last_lower or "email" in last_lower:
        return (
            "I cannot assist with writing emails to your landlord, but I can help you with your ConnectX "
            "account details, payments, or connectivity issues."
        )
    if "weather" in last_lower:
        return (
            "I do not have access to local weather information, but I'm here to assist you with your "
            "ConnectX broadband connection, billing, or network status."
        )

    if last_lower in ["hi", "hello", "hey"]:
        return (
            "Hello Priya! Welcome to ConnectX Customer Support. How can I assist you with your broadband service today?"
        )

    return (
        "Hi Priya! I am here to help you with your ConnectX broadband account, billing, plan changes, or outages. "
        "What can I do for you today?"
    )


def chat(
    system: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.3,
    max_retries: int = 3,
) -> str:
    """Execute a chat completion request with exponential backoff on 429/5xx errors.

    Args:
        system: System instructions and persona for the assistant.
        messages: Conversation history as list of dicts with 'role' and 'content'.
        temperature: Sampling temperature (default 0.3 for replies, 0.0 for classifier).
        max_retries: Number of retry attempts on rate limit or server errors.

    Returns:
        The response content string. Never crashes, never returns empty string.
    """
    mock_mode = os.getenv("MOCK_LLM", "0").lower() in ("1", "true", "yes")
    api_key, base_url, model = _get_env_config()

    if mock_mode or not api_key:
        return _mock_chat(system, messages)

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        formatted_messages = [{"role": "system", "content": system}] + messages

        backoff = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=formatted_messages,
                    temperature=temperature,
                )
                content = response.choices[0].message.content or ""
                trimmed = content.strip()
                if trimmed:
                    return trimmed
                logger.warning("Empty response from LLM, returning friendly fallback.")
                return FRIENDLY_FALLBACK

            except (RateLimitError, InternalServerError, APIConnectionError) as err:
                logger.warning(
                    "LLM transient error (attempt %d/%d): %s. Retrying in %.1fs...",
                    attempt,
                    max_retries,
                    err,
                    backoff,
                )
                if attempt == max_retries:
                    raise
                time.sleep(backoff)
                backoff *= 2.0

            except APIStatusError as err:
                # Retry on 429 or 5xx HTTP status codes
                if err.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    logger.warning(
                        "LLM HTTP %d error (attempt %d/%d). Retrying in %.1fs...",
                        err.status_code,
                        attempt,
                        max_retries,
                        backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2.0
                else:
                    raise

    except Exception as exc:
        logger.error("LLM chat call failed: %s", exc)
        return FRIENDLY_FALLBACK

    return FRIENDLY_FALLBACK
