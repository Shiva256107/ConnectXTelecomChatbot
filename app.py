
import os
import streamlit as st
from dotenv import load_dotenv
from google import genai

# ==================================================
# 1. CONFIGURATION
# ==================================================

load_dotenv()

st.set_page_config(
    page_title="ConnectX Telecom Support",
    page_icon="📡",
    layout="centered",
)

ACCOUNT = {
    "customer_name": "Shiva",
    "plan": "ConnectX Pro — 150 Mbps",
    "monthly_charge": "₹999",
    "billing_cycle": "1st of every month",
    "last_bill": "₹999",
    "last_bill_status": "Paid",
    "current_status": "Active",
    "known_outages": "None in your area",
    "contract_end": "March 2026",
}



SYSTEM_PROMPT = f"""
You are ConnectX Telecom's customer support assistant.

SUPPORTED TOPICS:
- Account information
- Billing and payments
- ConnectX plans and upgrades
- Internet connectivity and outages

VERIFIED CUSTOMER ACCOUNT DATA:
{ACCOUNT}

CONVERSATION RULES:
1. Use the conversation history to understand follow-up questions.
2. Resolve references such as "it", "that", "the faster option",
   and "how much more" using the previous conversation.
3. Answer the user's latest question directly. Avoid repeating
   the entire previous answer unnecessarily.
4. Keep account facts grounded in the verified account data.
5. Conversation history provides context, but it does not make
   an unverified statement into a verified account fact.
6. Never invent plan names, prices, discounts, or outage details.
7. If an upgrade price is unavailable, explain what is missing
   and suggest contacting ConnectX support.
8. Politely decline competitor pricing and unrelated requests.
9. Keep responses concise, helpful, and professional.
10. The supplied contract end date is March 2026. Do not assume
    that the contract has been renewed.
"""




# ==================================================
# 2. SCOPE CONTROL
# ==================================================

def check_scope(message, history):
    text = message.lower().strip()

    # Competitor pricing comparisons are out of scope.
    competitors = [
        "airtel", "jio", "vodafone", "competitor",
        "other telecom provider",
    ]
    comparison_terms = [
        "compare", "comparison", "pricing", "price",
        "cheaper", "cost",
    ]

    if (
        any(term in text for term in competitors)
        and any(term in text for term in comparison_terms)
    ):
        return (
            "I'm sorry, I can help with ConnectX account, billing, "
            "plans, and connectivity, but I can't compare competitor "
            "pricing."
        )

    # Clearly unrelated requests, including the test examples.
    unrelated_terms = [
        "weather", "landlord", "write an email",
        "email to my landlord", "recipe",
        "movie recommendation", "write my essay",
    ]

    if any(term in text for term in unrelated_terms):
        return (
            "I'm here to help with ConnectX Telecom account, billing, "
            "plans, and connectivity. I can't assist with that "
            "unrelated request."
        )

    # Questions clearly related to telecom support.
    telecom_terms = [
        "plan", "bill", "billing", "₹", "rs.",
        "rupee", "charge", "payment", "paid",
        "outage", "internet", "wifi", "wi-fi",
        "connection", "connectivity", "speed",
        "mbps", "upgrade", "contract", "account",
        "network", "recharge", "refund", "connectx",
    ]

    if any(term in text for term in telecom_terms):
        return None

    # Allow contextual follow-ups when a telecom conversation exists.
    follow_up_terms = [
        "it", "that", "this", "more", "faster",
        "much", "cost", "why", "when",
    ]

    if history and any(
        term in text.split() for term in follow_up_terms
    ):
        previous_text = " ".join(
            item["content"].lower() for item in history[-6:]
        )

        if any(term in previous_text for term in telecom_terms):
            return None

    return (
        "I'm here to help with ConnectX Telecom account, billing, "
        "plans, and connectivity. Could you ask a question related "
        "to these services?"
    )


# ==================================================
# 3. GEMINI API + CONVERSATION HISTORY
# ==================================================


def get_response(client, user_message, history):
    refusal = check_scope(user_message, history)

    if refusal:
        return refusal

    contents = []

    # Preserve the order of the recent conversation.
    for item in history[-12:]:
        role = "user" if item["role"] == "user" else "model"

        contents.append({
            "role": role,
            "parts": [{"text": item["content"]}]
        })

    # Add the current question once.
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
        contents=contents,
        config={
            "system_instruction": SYSTEM_PROMPT,
            "temperature": 0.2,
            "max_output_tokens": 350,
        },
    )

    if not response.text:
        return "Sorry, I couldn't generate an answer. Please try again."

    return response.text.strip()


# ==================================================
# 4. STREAMLIT CHAT INTERFACE
# ==================================================



st.title("📡 ConnectX Telecom Support")
st.caption("Your AI-powered telecom support assistant")

st.markdown("### 👋 Hi, Shiva!")
st.write("How can I help you with your ConnectX account today?")

st.markdown("#### 💡 Try asking")

examples = [
    "What is my current plan?",
    "Is my last bill paid?",
    "Are there any outages in my area?",
]

cols = st.columns(3)

for i, question in enumerate(examples):
    with cols[i]:
        if st.button(question, use_container_width=True):
            st.session_state.pending_question = question


with st.sidebar:
    st.subheader("Customer Account")
    st.write(f"**Name:** {ACCOUNT['customer_name']}")
    st.write(f"**Plan:** {ACCOUNT['plan']}")
    st.write(f"**Monthly charge:** {ACCOUNT['monthly_charge']}")
    st.write(f"**Status:** {ACCOUNT['current_status']}")
    st.caption("Demonstration using the provided mock account.")

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# Initialize history for this session.
if "messages" not in st.session_state:
    st.session_state.messages = []


# Display earlier messages.
for item in st.session_state.messages:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])


# Check API key and initialize Gemini.
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error(
        "GEMINI_API_KEY is missing. Add it to your .env file "
        "and restart the app."
    )
    st.stop()

client = genai.Client(api_key=api_key)


# Receive and process the next message.
typed_message = st.chat_input("Ask about your plan, billing, or connection...")
user_message = typed_message

if not user_message and "pending_question" in st.session_state:
    user_message = st.session_state.pop("pending_question")

if user_message and user_message.strip():
    user_message = user_message.strip()

    # Snapshot history before adding the current question.
    previous_history = list(st.session_state.messages)

    st.session_state.messages.append({
        "role": "user",
        "content": user_message,
    })

    with st.chat_message("user"):
        st.markdown(user_message)

    with st.chat_message("assistant"):
        with st.spinner("Preparing your answer..."):
            try:
                answer = get_response(
                    client,
                    user_message,
                    previous_history,
                )
            except Exception as exc:
                print(f"Gemini API error: {exc}")
                answer = (
                    "Sorry, the support service is temporarily "
                    "unavailable. Check your API key, model name, "
                    "internet connection, and API quota, then retry."
                )

        st.markdown(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
    })
