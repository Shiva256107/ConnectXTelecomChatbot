"""SupportBot implementation with in-memory session management,
layered guardrails, and conversation summarization.
"""

import logging
from typing import Dict, List, Optional
from chatbot.llm import FRIENDLY_FALLBACK, chat
from chatbot.prompts import build_summarizer_prompt, build_system_prompt
from chatbot.scope import check_scope

logger = logging.getLogger(__name__)

# Production Note: For multi-instance, distributed deployments, replace this
# in-memory dictionary with a Redis session store (e.g. redis-py with TTL).
SESSIONS: Dict[str, "SupportBot"] = {}


class SupportBot:
    """Manages conversation state, context compaction, and customer support dialogue."""

    def __init__(
        self,
        session_id: str = "default",
        verbatim_turns: int = 10,
        max_history_before_summary: int = 20,
    ) -> None:
        """Initializes SupportBot instance.

        Args:
            session_id: Unique identifier for the user session.
            verbatim_turns: Number of recent turns (turns = user+assistant pairs) to keep verbatim.
            max_history_before_summary: Threshold of messages before triggering summarization.
        """
        self.session_id: str = session_id
        self.verbatim_turns: int = verbatim_turns
        self.max_history_before_summary: int = max_history_before_summary
        self.history: List[Dict[str, str]] = []
        self.summary: str = ""

    def _maybe_compact_history(self) -> None:
        """Summarizes older conversation turns when history exceeds the threshold.

        Keeps the last N turns verbatim. Summarizes older turns with one LLM call.
        Falls back to plain truncation if summarization fails.
        Never drops system prompt or account data.
        """
        # If history exceeds threshold (e.g. > 20 messages)
        if len(self.history) <= self.max_history_before_summary:
            return

        split_index = len(self.history) - (self.verbatim_turns * 2)
        if split_index <= 0:
            return

        older_turns = self.history[:split_index]
        self.history = self.history[split_index:]

        # Attempt LLM summarization
        try:
            summarizer_system = build_summarizer_prompt()
            summary_request = [
                {
                    "role": "user",
                    "content": (
                        f"Previous summary: {self.summary}\n\n"
                        f"Older dialogue to incorporate:\n"
                        + "\n".join(
                            f"{turn['role'].upper()}: {turn['content']}"
                            for turn in older_turns
                        )
                    ),
                }
            ]
            new_summary = chat(
                system=summarizer_system,
                messages=summary_request,
                temperature=0.2,
            )
            if new_summary and new_summary.strip() and new_summary != FRIENDLY_FALLBACK:
                self.summary = new_summary.strip()
            else:
                logger.warning("Summarization returned blank/fallback. Falling back to plain truncation.")
        except Exception as err:
            logger.warning("Summarization call failed (%s). Falling back to plain truncation.", err)

    def reply(self, user_message: str) -> str:
        """Processes a customer message and produces a safe, grounded response.

        Args:
            user_message: The message typed by the customer.

        Returns:
            The agent's reply. Never crashes, never returns empty string.
        """
        clean_user_msg = (user_message or "").strip()
        if not clean_user_msg:
            return "Hello Priya! How can I assist you with your ConnectX broadband service today?"

        try:
            # Stage 3 (Layer 2): Pre-classifier out-of-scope check
            is_in_scope, decline_reply = check_scope(clean_user_msg, history=self.history)
            if not is_in_scope and decline_reply:
                # Obvious out-of-scope caught by pre-classifier
                self.history.append({"role": "user", "content": clean_user_msg})
                self.history.append({"role": "assistant", "content": decline_reply})
                return decline_reply

            # Stage 2: Context compaction & summarization check
            self._maybe_compact_history()

            # Append current turn to history
            self.history.append({"role": "user", "content": clean_user_msg})

            # Stage 1: Build system prompt with persona, account data, catalog, and rules
            system_prompt = build_system_prompt(summary=self.summary)

            # Call primary LLM
            assistant_reply = chat(
                system=system_prompt,
                messages=self.history,
                temperature=0.3,
            )

            # Fallback guarantee: never return empty or blank
            if not assistant_reply or not assistant_reply.strip():
                assistant_reply = FRIENDLY_FALLBACK

            self.history.append({"role": "assistant", "content": assistant_reply})
            return assistant_reply

        except Exception as err:
            logger.error("Error generating bot reply: %s", err)
            fallback = FRIENDLY_FALLBACK
            self.history.append({"role": "assistant", "content": fallback})
            return fallback

    def clear(self) -> None:
        """Resets conversation history and memory."""
        self.history.clear()
        self.summary = ""


def get_or_create_bot(session_id: str = "default") -> SupportBot:
    """Retrieves or instantiates a SupportBot for the given session ID."""
    if session_id not in SESSIONS:
        SESSIONS[session_id] = SupportBot(session_id=session_id)
    return SESSIONS[session_id]


def reset_session(session_id: str = "default") -> None:
    """Clears history for the given session ID."""
    if session_id in SESSIONS:
        SESSIONS[session_id].clear()
