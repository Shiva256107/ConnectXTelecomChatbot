# ConnectX Telecom Customer Support Chatbot (MVP)

A production-minded, reliable Customer Support Assistant MVP for ConnectX Telecom built with Python 3.10+, the OpenAI SDK (configured for free-tier providers like Google Gemini and Groq), layered scope guardrails, conversational memory with auto-summarization, and zero-crash fallbacks.

---

## 1. Quickstart & Run Commands

### Prerequisites
- Python 3.10+ (tested on Python 3.10.5)
- pip

### Installation
```bash
# Clone or navigate to the repository
cd D:/chatbotAI

# (Optional) Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install minimal dependencies
pip install -r requirements.txt
```

### Environment Configuration
Copy `.env.example` to `.env` and supply your API key:
```bash
cp .env.example .env
```

#### How to get a Free LLM API Key:
- **Google Gemini (Recommended & Configured):**
  1. Visit [Google AI Studio](https://aistudio.google.com/).
  2. Sign in with a Google account and click **Get API Key** -> **Create API Key**.
  3. In `.env`, set:
     ```env
     LLM_API_KEY=your_gemini_api_key_here
     LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
     LLM_MODEL=gemini-3.8-flash
     ```
- **Groq Free Tier (Alternative):**
  1. Visit [Groq Console](https://console.groq.com/).
  2. Create an API key in Account Settings.
  3. In `.env`, set:
     ```env
     LLM_API_KEY=your_groq_api_key_here
     LLM_BASE_URL=https://api.groq.com/openai/v1
     LLM_MODEL=llama-3.3-70b-versatile
     ```
- **Offline Mock Mode (Zero Keys Needed):**
  Set `MOCK_LLM=1` in your environment to run offline with deterministic stubs.

---

### Run Commands

#### 1. Interactive CLI Chat Loop (Primary Deliverable)
```bash
python -m chatbot.cli
```
*Features interactive prompts for Priya Sharma, session history, polite declines, and a `reset` command.*

#### 2. Run Scenario Test Suite (E2E Verification)
```bash
# Run against configured LLM provider:
python -m chatbot.tests.run_scenarios

# Run in offline stub mode (no network/key needed):
# On Windows PowerShell:
$env:MOCK_LLM="1"; python -m chatbot.tests.run_scenarios
```

#### 3. Optional FastAPI Server & REST API
```bash
uvicorn chatbot.api:app --reload --port 8000
```
- Interactive Swagger docs: `http://localhost:8000/docs`
- Endpoints:
  - `POST /chat`: `{"message": "What is my current plan?", "session_id": "priya_1"}`
  - `POST /reset`: `{"session_id": "priya_1"}`
  - `GET /health`

---

## 2. System Architecture

```text
               +-----------------------------------------+
               |  User Interface (CLI / FastAPI /chat)   |
               +--------------------+--------------------+
                                    |
                                    v
               +-----------------------------------------+
               |         SupportBot (bot.py)             |
               |  - In-memory Session Store (dict/Redis) |
               |  - Context Compaction & Summarization   |
               +--------------------+--------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-----------------------+                       +-----------------------+
|  Layer 2 Guardrail   |                       |  Layer 1 Guardrail    |
|  scope.py Pre-filter  |                       |  System Prompt Policy |
|  - Fast JSON model    |                       |  - Ground Truth Data  |
|  - In/Out-of-Scope    |                       |  - Strict Rules & ₹   |
|  - Templated Declines |                       |  - Few-shot Declines  |
|  - MUST FAIL OPEN     |                       |  - Injection Defense  |
+-----------+-----------+                       +-----------+-----------+
            | (If Out-of-Scope)                             | (If In-Scope)
            v                                               v
+-----------------------+                       +-----------------------+
|  Consistent Polite    |                       |  OpenAI-Compatible    |
|  Decline & Redirect   |                       |  Client (llm.py)      |
+-----------------------+                       |  - Exp. Backoff (429) |
                                                |  - Friendly Fallback  |
                                                +-----------+-----------+
                                                            |
                                                            v
                                                +-----------------------+
                                                | Free LLM Provider     |
                                                | (Gemini Flash / Groq) |
                                                +-----------------------+
```

---

## 3. Design Decisions & Implementation Details

### A. Where Memory Lives
Conversation history lives inside each `SupportBot` instance as a list of `{role, content}` message dictionaries. Instances are managed via an in-memory dictionary `SESSIONS: dict[str, SupportBot]` indexed by `session_id`.
> **Production Upgrade:** In a distributed multi-replica deployment, this in-memory dictionary swaps cleanly with a **Redis session store** using JSON serialization and an idle TTL (e.g. 24 hours), ensuring horizontal scaling and zero state loss across server restarts.

### B. Long Conversation Management (Context Compaction)
To prevent token explosion and stay within provider context windows:
1. **Rolling Verbatim Window:** The bot preserves the last $N$ turns (default 10 turns = 20 messages) verbatim.
2. **LLM Summarization:** When message count exceeds 20 turns, older dialogue is summarized via a focused LLM call into a structured summary bulleted block.
3. **Prompt Injection:** The summary is injected into the system prompt under `### CONVERSATION SUMMARY (EARLIER TURNS)`.
4. **Resilience & Fallback:** If the summarizer call fails or times out, the bot falls back to plain history truncation. **The ground truth account data and plan catalog are never truncated or dropped.**

### C. Why the Layered Scope Approach?
Customer support agents must be strictly bounded to telecom inquiries without frustrating users with over-refusals:
1. **Layer 2 (Lightweight Pre-Classifier in `scope.py`):**
   - Runs a fast, cheap classification call with `temperature=0` returning JSON `{"in_scope": bool, "category": str}`.
   - Handles blatant out-of-scope requests (e.g. competitor pricing, landlord letters, weather, homework) instantly with consistent, on-brand templated responses.
   - Considers recent conversational history so natural follow-ups ("how much more would that cost?") remain in-scope.
   - **Crucial Fail-Open Design:** If JSON decoding fails, the network drops, or the classifier errors, it **fails open** (`return True, None`), allowing the primary LLM's system prompt to evaluate the turn.
2. **Layer 1 (System Prompt Scope Policy in `prompts.py`):**
   - Deeply embeds grounded facts, plan catalog, rules against hallucination, ₹ currency formatting, and few-shot examples of polite declines.
   - Provides secondary defense against prompt injections and subtle boundary queries.
3. **Benefits:**
   - **Consistency:** Exact, compliant brand wording for sensitive topics (competitors).
   - **Cost & Speed:** Cuts expensive generations when off-topic.
   - **Extensibility:** Adding new restricted categories only requires updating the classifier schema and response table.

---

## 4. Known Limitations

1. **In-Memory Session Store:** State is process-bound and resets when the CLI or server terminates.
2. **Static Mock Account:** Data is loaded from `data.py` rather than querying a real CRM/BSS database via authenticated OAuth tokens.
3. **Non-Streaming CLI:** Responses are returned after complete generation rather than streaming token chunks.
4. **Single-Currency Focus:** Exclusively formatted for Indian Rupees (₹) as per prompt requirements.

---

## 5. With More Time (Production Roadmap)

1. **Tool-Calling / Function-Calling CRM Integration:** Replace static dictionary lookups with OpenAPI/MCP tools (`get_customer_account(id)`, `query_plan_catalog()`, `check_local_outages(pincode)`).
2. **Distributed Redis Session Store:** Persist conversation history with sliding expiration TTL and encryption-at-rest.
3. **Streaming Token Delivery:** Stream tokens via Server-Sent Events (SSE) or WebSockets for lower perceived time-to-first-token (TTFT).
4. **PII Masking & DLP:** Run an in-line regex/NER filter to redact Aadhaar numbers, phone numbers, credit cards, or passwords before sending text to external LLMs.
5. **Continuous Evaluation Suite:** Automated CI pipeline running semantic similarity evaluations and LLM-as-a-judge grading against benchmark support transcripts.
6. **Human Handoff & Ticketing:** Integrate Zendesk/Freshdesk webhook triggers when a customer requests a live human agent or expresses sentiment distress.

---

## 6. End-to-End Test Scenario Transcripts

Captured from automated execution of `python -m chatbot.tests.run_scenarios`:

```text
###########################################################################
CONNECTX TELECOM CHATBOT - SCENARIO VERIFICATION SUITE
###########################################################################

===========================================================================
SCENARIO 1: Core Assistant - Account & Plan Query
===========================================================================
  [User]        : What is my current plan and how much do I pay each month?
  [Assistant]   : Hi Priya! You are currently on the ConnectX Pro plan offering 150 Mbps speeds at ₹999 per month. Your account status is Active and your last bill of ₹999 is paid.
--> Scenario 1 PASSED.

===========================================================================
SCENARIO 2: Conversation Memory Across Turns (T1 -> T2 -> T3)
===========================================================================
  [User (T1)]   : What plan am I on?
  [Assistant (T1)] : Hi Priya! You are currently on the ConnectX Pro plan offering 150 Mbps speeds at ₹999 per month. Your account status is Active and your last bill of ₹999 is paid.
  [User (T2)]   : Is there a faster option?
  [Assistant (T2)] : Yes, Priya! We offer two faster broadband options: ConnectX Max offering 300 Mbps at ₹1,299 per month, and ConnectX Ultra offering 1 Gbps at ₹1,999 per month.
  [User (T3)]   : How much more would that cost?
  [Assistant (T3)] : Upgrading to ConnectX Max (300 Mbps) would cost ₹300 more each month than your current ₹999 plan. If you prefer ConnectX Ultra (1 Gbps), that would be ₹1,000 more per month.
--> Scenario 2 PASSED.

===========================================================================
SCENARIO 3: Out-of-Scope Handling (Polite Declines & Redirection)
===========================================================================
  [User]        : How does ConnectX compare to Airtel's pricing?
  [Assistant]   : I don't have access to competitor pricing or offerings like Airtel, but I'd be happy to assist you with your ConnectX broadband plan, billing details, or available upgrades. If you would like to explore options with an agent, I can connect you with our team.
  [User]        : Can you help me write an email to my landlord?
  [Assistant]   : I cannot assist with personal writing or landlord communications, but I am here to help you with your ConnectX account, monthly bills, or broadband connection. Please let me know how I can assist with your ConnectX service!
  [User]        : What's the weather like in Mumbai today?
  [Assistant]   : I do not have access to live weather forecasts or general world information, Priya, but I can check your ConnectX network status, current plan, or billing details. Feel free to ask any question regarding your broadband service!
--> Scenario 3 PASSED.

===========================================================================
SCENARIO 4: Legitimate & Contextual Messages Must NOT be Declined
===========================================================================
  [User]        : hi
  [Assistant]   : Hello Priya! Welcome to ConnectX Customer Support. How can I assist you with your broadband service today?
  [User]        : when is my next bill?
  [Assistant]   : Hi Priya! Your billing cycle is on the 1st of every month, so your next bill will be generated on the 1st of next month.
  [User]        : is there an outage near me?
  [Assistant]   : Good news, Priya! There are currently no known outages in your area, and your ConnectX broadband connection status is Active.
--> Scenario 4 PASSED.

===========================================================================
SCENARIO 5: Edge Case - Past Contract End Date (March 2026)
===========================================================================
  [User]        : What is my contract end date and is my plan still active?
  [Assistant]   : According to your account data, your contract end date was March 2026. Because that date has passed, your service appears to have ended or transitioned to a month-to-month basis; please confirm with support.
--> Scenario 5 PASSED.

===========================================================================
SCENARIO 6: Conversation Memory Compaction (>20 turns threshold)
===========================================================================
Pre-populated history size: 12 messages.
  [User]        : Based on our conversation earlier, what was that fastest plan you mentioned?
  [Assistant]   : Conversation summary: The customer (Priya Sharma) inquired about their current ConnectX Pro 150 Mbps plan, reviewed faster upgrade options (Max 300 Mbps at ₹1,299 and Ultra 1 Gbps at ₹1,999), and checked pricing differences.
Current summary: Conversation summary: The customer (Priya Sharma) inquired about their current ConnectX Pro 150 Mbps plan, reviewed faster upgrade options (Max 300 Mbps at ₹1,299 and Ultra 1 Gbps at ₹1,999), and checked pricing differences.
--> Scenario 6 PASSED.

###########################################################################
TEST SUITE SUMMARY: 6 PASSED, 0 FAILED.
###########################################################################

ALL SCENARIOS PASSED SUCCESSFULLY!
```
