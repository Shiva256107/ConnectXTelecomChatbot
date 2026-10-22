"""Interactive Command Line Interface for ConnectX Customer Support Chatbot.

Provides a terminal chat loop with session memory and graceful shutdown.
"""

import sys

# Ensure Windows terminal supports UTF-8 characters like ₹
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from chatbot.bot import get_or_create_bot
from chatbot.data import ACCOUNT_DATA


def run_cli() -> None:
    """Runs the interactive support chat session."""
    bot = get_or_create_bot("cli_user")
    customer = ACCOUNT_DATA["customer_name"]
    plan = ACCOUNT_DATA["plan"]

    print("=" * 65)
    print("      📡 ConnectX Telecom Customer Support Assistant")
    print(f"      Customer: {customer} | Current Plan: {plan}")
    print("=" * 65)
    print("Type your message below. Type 'exit', 'quit', or 'q' to end.")
    print("Type 'reset' to start a new conversation session.\n")

    while True:
        try:
            user_input = input(f"{customer} > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print("\nAssistant > Thank you for contacting ConnectX Support. Have a great day!")
                break

            if user_input.lower() == "reset":
                bot.clear()
                print("\nAssistant > Session reset. How can I help you today?\n")
                continue

            reply = bot.reply(user_input)
            print(f"\nAssistant > {reply}\n")

        except (KeyboardInterrupt, EOFError):
            print("\n\nAssistant > Goodbye! Thank you for choosing ConnectX.")
            sys.exit(0)


if __name__ == "__main__":
    run_cli()
