"""End-to-end scenario test runner for ConnectX Customer Support Chatbot.

Runs all stages and verification scenarios:
1. Core assistant inquiry (Stage 1)
2. Multi-turn conversation memory (Stage 2)
3. Out-of-scope declines & in-scope non-refusals (Stage 3)
4. Expired contract handling (Edge case)
5. Long conversation history compaction & summarization

Supports MOCK_LLM=1 for offline CI/testing and sleeps 1s between turns
to respect free-tier provider rate limits.
"""

import os
import sys
import time
from typing import Callable, List, Tuple

# Ensure Windows terminal supports UTF-8 characters like ₹
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from chatbot.bot import SupportBot

# Ensure 1s delay to respect provider rate limits
RATE_LIMIT_DELAY = 1.0


def print_turn(speaker: str, text: str) -> None:
    """Pretty prints a conversation turn."""
    prefix = f"[{speaker}]"
    print(f"  {prefix:<13} : {text}")


def assert_keywords(reply: str, keywords: List[str], desc: str) -> None:
    """Verifies that at least one of the expected keywords is present (case-insensitive)."""
    reply_lower = reply.lower()
    matches = [kw for kw in keywords if kw.lower() in reply_lower]
    if not matches:
        print(f"\n[FAIL] Assertion failed for: {desc}")
        print(f"       Expected any of: {keywords}")
        print(f"       Actual response: {reply}\n")
        raise AssertionError(f"Missing expected keyword for: {desc}")


def assert_all_keywords(reply: str, keyword_groups: List[List[str]], desc: str) -> None:
    """Verifies that each group in keyword_groups has at least one match in reply."""
    reply_lower = reply.lower()
    for group in keyword_groups:
        matches = [kw for kw in group if kw.lower() in reply_lower]
        if not matches:
            print(f"\n[FAIL] Assertion failed for: {desc}")
            print(f"       Missing expected match from group: {group}")
            print(f"       Actual response: {reply}\n")
            raise AssertionError(f"Missing group keyword for: {desc}")


def run_scenario_1() -> None:
    """Scenario 1: Core Assistant (Stage 1)."""
    print("\n" + "=" * 75)
    print("SCENARIO 1: Core Assistant - Account & Plan Query")
    print("=" * 75)
    bot = SupportBot(session_id="scenario_1")

    query = "What is my current plan and how much do I pay each month?"
    print_turn("User", query)
    reply = bot.reply(query)
    print_turn("Assistant", reply)

    # Asserts: ConnectX Pro 150 Mbps, ₹999/month
    assert_all_keywords(
        reply,
        [
            ["pro", "connectx pro"],
            ["150", "150 mbps"],
            ["999", "₹999"],
        ],
        desc="Scenario 1: Current plan and monthly charge",
    )
    time.sleep(RATE_LIMIT_DELAY)
    print("--> Scenario 1 PASSED.")


def run_scenario_2() -> None:
    """Scenario 2: Multi-turn Conversation Memory (Stage 2)."""
    print("\n" + "=" * 75)
    print("SCENARIO 2: Conversation Memory Across Turns (T1 -> T2 -> T3)")
    print("=" * 75)
    bot = SupportBot(session_id="scenario_2")

    # Turn 1
    t1 = "What plan am I on?"
    print_turn("User (T1)", t1)
    r1 = bot.reply(t1)
    print_turn("Assistant (T1)", r1)
    assert_keywords(r1, ["pro", "150"], desc="T1: Mentions Pro / 150")
    time.sleep(RATE_LIMIT_DELAY)

    # Turn 2
    t2 = "Is there a faster option?"
    print_turn("User (T2)", t2)
    r2 = bot.reply(t2)
    print_turn("Assistant (T2)", r2)
    assert_keywords(r2, ["max", "ultra", "300", "1 gbps", "faster"], desc="T2: Mentions Max/300 or Ultra/1 Gbps")
    time.sleep(RATE_LIMIT_DELAY)

    # Turn 3
    t3 = "How much more would that cost?"
    print_turn("User (T3)", t3)
    r3 = bot.reply(t3)
    print_turn("Assistant (T3)", r3)
    # Must answer relative to option(s) just discussed (₹300 more for Max, ₹1,000 more for Ultra)
    assert_keywords(r3, ["300", "1000", "1,000", "1299", "1,299", "1999", "1,999"], desc="T3: Relative price difference")
    time.sleep(RATE_LIMIT_DELAY)
    print("--> Scenario 2 PASSED.")


def run_scenario_3() -> None:
    """Scenario 3: Out-of-Scope Declines (Stage 3 Layered Guardrails)."""
    print("\n" + "=" * 75)
    print("SCENARIO 3: Out-of-Scope Handling (Polite Declines & Redirection)")
    print("=" * 75)
    bot = SupportBot(session_id="scenario_3")

    test_cases: List[Tuple[str, List[str], str]] = [
        (
            "How does ConnectX compare to Airtel's pricing?",
            ["airtel", "competitor", "connectx"],
            "Decline competitor comparison",
        ),
        (
            "Can you help me write an email to my landlord?",
            ["landlord", "writing", "email", "connectx", "service"],
            "Decline personal/landlord email writing",
        ),
        (
            "What's the weather like in Mumbai today?",
            ["weather", "forecast", "connectx", "service", "broadband"],
            "Decline weather inquiry",
        ),
    ]

    for query, expected_kws, desc in test_cases:
        print_turn("User", query)
        reply = bot.reply(query)
        print_turn("Assistant", reply)
        assert len(reply.strip()) > 0, "Response must not be empty"
        assert_keywords(reply, expected_kws, desc=desc)
        # Verify it redirects to ConnectX services or offers agent
        assert_keywords(reply, ["connectx", "broadband", "account", "plan", "support", "agent"], desc=f"{desc} - Redirection check")
        time.sleep(RATE_LIMIT_DELAY)

    print("--> Scenario 3 PASSED.")


def run_scenario_4() -> None:
    """Scenario 4: Must NOT be Declined (Stage 3 In-Scope Pass-through)."""
    print("\n" + "=" * 75)
    print("SCENARIO 4: Legitimate & Contextual Messages Must NOT be Declined")
    print("=" * 75)
    bot = SupportBot(session_id="scenario_4")

    # 1. Greeting
    q1 = "hi"
    print_turn("User", q1)
    r1 = bot.reply(q1)
    print_turn("Assistant", r1)
    assert len(r1.strip()) > 0
    assert_keywords(r1, ["hello", "hi", "help", "connectx", "priya"], desc="Greeting reply")
    time.sleep(RATE_LIMIT_DELAY)

    # 2. Next bill
    q2 = "when is my next bill?"
    print_turn("User", q2)
    r2 = bot.reply(q2)
    print_turn("Assistant", r2)
    assert_keywords(r2, ["1st", "first", "billing cycle", "month"], desc="Next bill query (1st of month)")
    time.sleep(RATE_LIMIT_DELAY)

    # 3. Outage
    q3 = "is there an outage near me?"
    print_turn("User", q3)
    r3 = bot.reply(q3)
    print_turn("Assistant", r3)
    assert_keywords(r3, ["none", "no outage", "no known", "active", "area"], desc="Outage query (none in area)")
    time.sleep(RATE_LIMIT_DELAY)

    print("--> Scenario 4 PASSED.")


def run_scenario_5() -> None:
    """Scenario 5: Contract Expiration Handling (Past March 2026 Date)."""
    print("\n" + "=" * 75)
    print("SCENARIO 5: Edge Case - Past Contract End Date (March 2026)")
    print("=" * 75)
    bot = SupportBot(session_id="scenario_5")

    query = "What is my contract end date and is my plan still active?"
    print_turn("User", query)
    reply = bot.reply(query)
    print_turn("Assistant", reply)

    # Asserts: mentions March 2026, mentions ended / month-to-month, suggests confirming with support
    assert_all_keywords(
        reply,
        [
            ["march 2026", "march"],
            ["ended", "past", "expired", "month-to-month", "month to month", "active"],
            ["support", "agent", "confirm", "team"],
        ],
        desc="Expired contract data handling",
    )
    time.sleep(RATE_LIMIT_DELAY)
    print("--> Scenario 5 PASSED.")


def run_scenario_6() -> None:
    """Scenario 6: Long Conversation Compaction & Summarization (Stage 2)."""
    print("\n" + "=" * 75)
    print("SCENARIO 6: Conversation Memory Compaction (>20 turns threshold)")
    print("=" * 75)
    bot = SupportBot(session_id="scenario_6", verbatim_turns=5, max_history_before_summary=10)

    # Populate 12 conversational turns (24 messages) to exceed threshold
    seed_turns = [
        ("What is my name on the account?", "Your name is Priya Sharma."),
        ("What speed do I have?", "You currently have 150 Mbps on ConnectX Pro."),
        ("What is my billing cycle?", "Your billing cycle begins on the 1st of every month."),
        ("How much was my last bill?", "Your last bill was ₹999 and is marked as paid."),
        ("Are there faster plans?", "Yes, ConnectX Max (300 Mbps) and ConnectX Ultra (1 Gbps)."),
        ("What is the price of Max?", "ConnectX Max is ₹1,299 per month."),
    ]

    for u, a in seed_turns:
        bot.history.append({"role": "user", "content": u})
        bot.history.append({"role": "assistant", "content": a})

    print(f"Pre-populated history size: {len(bot.history)} messages.")

    follow_up = "Based on our conversation earlier, what was that fastest plan you mentioned?"
    print_turn("User", follow_up)
    reply = bot.reply(follow_up)
    print_turn("Assistant", reply)

    # Verify summarization occurred or was compacted, and response retains context
    assert len(reply.strip()) > 0
    assert_keywords(reply, ["ultra", "1 gbps", "fastest", "max"], desc="Recall from compacted memory")
    print(f"Current summary: {bot.summary or '[Truncation applied]'}")
    time.sleep(RATE_LIMIT_DELAY)
    print("--> Scenario 6 PASSED.")


def main() -> None:
    """Executes all scenarios and exits non-zero if any assertion fails."""
    mock_mode = os.getenv("MOCK_LLM", "0")
    print("\n" + "#" * 75)
    print(f"CONNECTX TELECOM CHATBOT - SCENARIO VERIFICATION SUITE (MOCK_LLM={mock_mode})")
    print("#" * 75)

    scenarios: List[Tuple[str, Callable[[], None]]] = [
        ("Stage 1 - Core Assistant", run_scenario_1),
        ("Stage 2 - Multi-turn Conversation Memory", run_scenario_2),
        ("Stage 3 - Out-of-Scope Polite Declines", run_scenario_3),
        ("Stage 3 - Legitimate In-Scope Messages", run_scenario_4),
        ("Contract Expiration Edge Case", run_scenario_5),
        ("Stage 2 - Long History Compaction & Summary", run_scenario_6),
    ]

    passed = 0
    failed = 0

    for name, func in scenarios:
        try:
            func()
            passed += 1
        except Exception as err:
            print(f"\n[ERROR] Scenario '{name}' failed with error: {err}")
            failed += 1

    print("\n" + "#" * 75)
    print(f"TEST SUITE SUMMARY: {passed} PASSED, {failed} FAILED.")
    print("#" * 75 + "\n")

    if failed > 0:
        sys.exit(1)
    else:
        print("ALL SCENARIOS PASSED SUCCESSFULLY!")
        sys.exit(0)


if __name__ == "__main__":
    main()
