# PlurAgent — Agentic Commerce & Intelligent Payments Platform

An AI-powered commerce assistant that autonomously handles the full payment lifecycle through natural language, deeply integrating 14 Pine Labs Plural APIs as agent tools.

Built for the **Pine Labs AI Hackathon** (March 14, 2026).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Configuration](#environment-configuration)
- [Running the Application](#running-the-application)
- [API Reference](#api-reference)
- [Pine Labs Tool Reference](#pine-labs-tool-reference)
- [Agent Intelligence](#agent-intelligence)
- [Frontend](#frontend)
- [Testing](#testing)
- [Demo Scenarios](#demo-scenarios)

---

## Overview

PlurAgent is a full-stack agentic commerce platform that turns natural language requests into real Pine Labs API calls. Users interact through a conversational chat interface, and an AI agent (Claude on AWS Bedrock) autonomously:

- Authenticates, creates customers, orders, and payments
- Discovers EMI/BNPL offers and compares convenience fees
- Processes refunds, queries settlements, and generates payment links
- Manages subscriptions, handles currency conversion, and reconciles transactions
- Makes intelligent decisions (choosing the cheapest payment method, retrying failed payments with fallback methods)

The platform includes a **real-time dashboard** that visualizes every tool call, decision, and workflow step as it happens.

---

## Architecture

PlurAgent uses a **microservices architecture** with three backend services communicating over HTTP, and a React frontend connected via WebSocket for real-time streaming.

```
┌─────────────────┐         Vite Proxy          ┌──────────────────┐
│    Frontend      │  /api, /ws/* → :8000        │    Gateway       │
│   React + Vite   │ ──────────────────────────► │   FastAPI :8000  │
│     :5173        │  WebSocket (chat/dashboard)  │                  │
└─────────────────┘                              └────────┬─────────┘
                                                          │
                                          HTTP POST       │   Streaming
                                          /agent/chat     │   NDJSON
                                                          ▼
                                                 ┌──────────────────┐
                                                 │   Agent Service   │
                                                 │  Bedrock Claude   │
                                                 │   FastAPI :8001   │
                                                 └────────┬─────────┘
                                                          │
                                          GET /tools/defs │   POST /tools/execute
                                                          ▼
                                                 ┌──────────────────┐
                                                 │  Pine Labs Svc    │
                                                 │  14 API Tools     │
                                                 │   FastAPI :8002   │
                                                 └──────────────────┘
                                                          │
                                                          ▼
                                                 ┌──────────────────┐
                                                 │ Pine Labs Plural  │
                                                 │   UAT Sandbox     │
                                                 └──────────────────┘
```

### Data Flow

1. User sends a message over the **WebSocket** (`/ws/chat`).
2. **Gateway** forwards the conversation to the **Agent Service** via streaming HTTP POST.
3. **Agent Service** sends the conversation to **AWS Bedrock (Claude)** with all 14 tool definitions.
4. When Claude decides to use a tool, the Agent calls the **Pine Labs Service** to execute it.
5. Events (`tool_call`, `tool_result`, `decision`, `workflow_step`, `response`) stream back through the Gateway to the frontend.
6. Gateway simultaneously broadcasts events to the **Dashboard WebSocket** (`/ws/dashboard`) for live visualization.

### Why Microservices?

| Concern | Service | Benefit |
|---------|---------|---------|
| Routing, session management, alerts | Gateway | Decoupled from AI logic |
| AI reasoning, tool orchestration | Agent | Can swap LLM providers independently |
| API integration, tool schemas | Pine Labs | Isolated credential management |

A **monolithic backend** is also available under `backend/` for simpler local development.

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Frontend** | React | 19 |
| | TypeScript | 5.9 |
| | Vite | 8 |
| | Tailwind CSS | 4 |
| | Recharts | 3.8 |
| | Lucide React | 0.577 |
| | qrcode.react | 4.2 |
| **Backend** | Python | 3.11+ |
| | FastAPI | latest |
| | Uvicorn | latest |
| | httpx | latest |
| **AI** | AWS Bedrock | Claude Sonnet |
| | boto3 | latest |
| **Payments** | Pine Labs Plural API | v1 (UAT) |
| **Real-time** | WebSocket | native |

---

## Project Structure

```
Pinelabs_hackathon/
├── frontend/                          # React frontend application
│   ├── src/
│   │   ├── main.tsx                   # Entry point
│   │   ├── App.tsx                    # Root layout (split-pane chat + dashboard)
│   │   ├── index.css                  # Global styles, CSS variables, dark theme
│   │   ├── lib/
│   │   │   └── types.ts              # TypeScript interfaces (Message, ToolCall, etc.)
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts        # WebSocket connection hook
│   │   │   └── useVoice.ts            # Voice input hook
│   │   └── components/
│   │       ├── Chat/
│   │       │   ├── ChatPanel.tsx       # Chat UI, input, suggestions, message list
│   │       │   ├── MessageBubble.tsx   # User/assistant message rendering
│   │       │   ├── ToolAction.tsx      # Tool call status indicator
│   │       │   ├── DecisionPanel.tsx   # Agent decision reasoning display
│   │       │   └── QRCodeBubble.tsx    # QR code for payment links
│   │       └── Dashboard/
│   │           ├── DashboardPanel.tsx  # Dashboard container
│   │           ├── StatsCards.tsx      # Aggregate metric cards
│   │           ├── Charts.tsx          # Area, pie, and bar charts
│   │           ├── TransactionFeed.tsx # Live order/payment/refund feed
│   │           └── AgentActivityLog.tsx# Chronological tool call log
│   ├── package.json
│   ├── vite.config.ts                 # Vite config with WebSocket proxy
│   └── index.html
│
├── services/                          # Microservices backend
│   ├── gateway/                       # API Gateway (port 8000)
│   │   ├── main.py                    # REST + WebSocket endpoints, alert engine
│   │   ├── config.py                  # Service URLs, CORS origins
│   │   └── requirements.txt
│   ├── agent/                         # AI Agent Service (port 8001)
│   │   ├── main.py                    # FastAPI wrapper
│   │   ├── agent.py                   # Bedrock Claude tool-use loop, NDJSON streaming
│   │   ├── config.py                  # AWS credentials, model ID
│   │   └── requirements.txt
│   └── pinelabs/                      # Pine Labs Tool Service (port 8002)
│       ├── main.py                    # Tool definitions + execute endpoint
│       ├── tools.py                   # 14 tool implementations
│       ├── pine_client.py             # HTTP client with token caching
│       ├── config.py                  # Pine Labs credentials
│       └── requirements.txt
│
├── backend/                           # Monolithic backend (alternative)
│   ├── main.py                        # Single FastAPI app with everything
│   ├── agent.py                       # Agent logic (embedded)
│   ├── config.py
│   ├── tools/                         # Tool implementations
│   │   ├── __init__.py                # TOOL_REGISTRY, TOOL_DEFINITIONS
│   │   ├── pine_client.py
│   │   ├── auth.py
│   │   ├── customers.py
│   │   ├── orders.py
│   │   ├── payments.py
│   │   ├── offers.py
│   │   ├── refunds.py
│   │   ├── settlements.py
│   │   ├── payment_links.py
│   │   ├── subscriptions.py
│   │   ├── convenience_fee.py
│   │   └── international.py
│   ├── requirements.txt
│   └── .env.example
│
├── tests/                             # Test suite
│   ├── conftest.py                    # Pytest fixtures, base URLs
│   ├── test_agent_service.py          # Agent service unit tests
│   ├── test_pinelabs_service.py       # Pine Labs service tests
│   ├── test_gateway_service.py        # Gateway endpoint tests
│   ├── test_e2e.py                    # End-to-end integration tests
│   └── test_edge_cases.py            # Edge case coverage
│
├── start.sh                           # One-command microservices launcher
├── pytest.ini                         # Pytest configuration
├── .env                               # Root environment variables
└── README.md                          # This file
```

---

## Getting Started

### Prerequisites

- **Python 3.11+** with `pip`
- **Node.js 18+** with `npm`
- **AWS Account** with Bedrock access (Claude model enabled)
- **Pine Labs Plural** UAT sandbox credentials

### Installation

```bash
git clone <repository-url>
cd Pinelabs_hackathon
```

Install backend dependencies (for each service or the monolithic backend):

```bash
# Microservices
pip install -r services/gateway/requirements.txt
pip install -r services/agent/requirements.txt
pip install -r services/pinelabs/requirements.txt

# OR monolithic
pip install -r backend/requirements.txt
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

---

## Environment Configuration

Create a `.env` file in the project root (used by the microservices) and/or `backend/.env` (for the monolithic backend).

```env
# ── Pine Labs Plural API ────────────────────────
PINE_LABS_BASE_URL=https://pluraluat.v2.pinepg.in/api
PINE_LABS_CLIENT_ID=your_client_id_here
PINE_LABS_CLIENT_SECRET=your_client_secret_here
PINE_LABS_MID=your_merchant_id_here

# ── AWS Bedrock ─────────────────────────────────
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_SESSION_TOKEN=your_session_token       # optional, for temporary credentials
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

# ── Application ─────────────────────────────────
FRONTEND_ORIGIN=http://localhost:5173
```

| Variable | Description |
|----------|-------------|
| `PINE_LABS_BASE_URL` | Pine Labs Plural API base URL (UAT sandbox) |
| `PINE_LABS_CLIENT_ID` | OAuth2 client ID from Pine Labs dashboard |
| `PINE_LABS_CLIENT_SECRET` | OAuth2 client secret |
| `PINE_LABS_MID` | Merchant ID assigned by Pine Labs |
| `AWS_REGION` | AWS region where Bedrock is available |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key with Bedrock permissions |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `AWS_SESSION_TOKEN` | STS session token (only for temporary credentials) |
| `BEDROCK_MODEL_ID` | Claude model identifier on Bedrock |
| `FRONTEND_ORIGIN` | Allowed CORS origin for the frontend |

---

## Running the Application

### Option 1: Microservices (Recommended)

Start all services with a single command:

```bash
chmod +x start.sh
./start.sh
```

This launches:

| Service | Port | URL |
|---------|------|-----|
| Pine Labs Service | 8002 | http://localhost:8002 |
| Agent Service | 8001 | http://localhost:8001 |
| Gateway | 8000 | http://localhost:8000 |
| Frontend | 5173 | http://localhost:5173 |

Open **http://localhost:5173** in your browser.

### Option 2: Monolithic Backend

```bash
# Terminal 1: Backend
cd backend
python3 -m uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Open **http://localhost:5173**.

### Option 3: Individual Services (Development)

Start each service separately for fine-grained control:

```bash
# Terminal 1: Pine Labs Service
cd services/pinelabs
python3 -m uvicorn main:app --host 0.0.0.0 --port 8002

# Terminal 2: Agent Service
cd services/agent
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001

# Terminal 3: Gateway
cd services/gateway
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 4: Frontend
cd frontend
npm run dev
```

---

## API Reference

### Gateway Service (port 8000)

#### Health Check

```
GET /api/health
```

Returns the status of all downstream services.

```json
{
  "status": "ok",
  "services": {
    "gateway": "ok",
    "agent": "ok",
    "pinelabs": "ok"
  }
}
```

#### Chat (REST)

```
POST /api/chat
```

Synchronous chat endpoint. Waits for the full agent response before returning.

**Request:**

```json
{
  "session_id": "my-session",
  "message": "Authenticate and create an order for ₹1,000"
}
```

**Response:**

```json
{
  "response": "I've authenticated and created order ORD-123 for ₹1,000...",
  "tool_calls": [
    {
      "tool_name": "generate_token",
      "tool_input": {},
      "tool_result": { "success": true, "message": "Authentication successful" },
      "timestamp": "2026-03-14T10:00:00Z"
    }
  ],
  "session_id": "my-session"
}
```

#### Activity Log

```
GET /api/activity
```

Returns the last 100 tool call/result events.

#### Clear Session

```
DELETE /api/session/{session_id}
```

Clears the conversation history for a given session.

#### Chat WebSocket

```
WebSocket /ws/chat
```

Streaming chat interface. Send JSON messages, receive NDJSON events in real time.

**Send:**

```json
{ "message": "Buy a laptop for ₹50,000", "session_id": "ws-default" }
```

**Receive (streamed events):**

```json
{"type": "workflow_step", "data": {"workflow_id": "abc123", "step_index": 0, "total_steps": 7, "step_name": "Starting", "status": "running"}}
{"type": "tool_call", "data": {"tool_name": "generate_token", "tool_input": {}, "timestamp": "..."}}
{"type": "tool_result", "data": {"tool_name": "generate_token", "tool_result": {"success": true}, "timestamp": "..."}}
{"type": "decision", "data": {"title": "Payment Decision", "reasoning": "UPI has zero fees...", "chosen": "UPI"}}
{"type": "response", "data": {"response": "Here's your order summary...", "tool_calls": [...]}}
```

#### Dashboard WebSocket

```
WebSocket /ws/dashboard
```

Receives broadcast events for real-time dashboard updates. Events mirror tool calls, decisions, and workflow steps from the chat.

### Agent Service (port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/agent/chat` | POST | Streaming chat (NDJSON response) |

### Pine Labs Service (port 8002)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tools/definitions` | GET | Returns all 14 tool schemas for Claude |
| `/tools/execute` | POST | Execute a named tool with input parameters |

**Execute a tool:**

```json
POST /tools/execute
{
  "tool_name": "create_order",
  "tool_input": { "amount": 100000, "currency": "INR" }
}
```

---

## Pine Labs Tool Reference

PlurAgent integrates **14 Pine Labs Plural API tools** that the AI agent can invoke autonomously.

### Authentication

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `generate_token` | Authenticate with Pine Labs and obtain a Bearer token. Must be called before any other API call. | None |

### Customer Management

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `create_customer` | Create a customer profile in Pine Labs. | `first_name`, `last_name`, `email`, `phone` |

### Order Management

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `create_order` | Create a payment order. Amounts in **paisa** (₹1 = 100 paisa). Returns an `order_id`. | `amount`, `currency` |
| `get_order_status` | Query the current status of an order. | `order_id` |

### Payment Processing

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `create_payment` | Execute a payment against an order. Supports CARD, UPI, NETBANKING, WALLET, BNPL. | `order_id`, `payment_method`, `amount` |
| `discover_offers` | Find available EMI/BNPL offers for a given amount. | `amount` |
| `calculate_convenience_fee` | Calculate the convenience fee for a given payment method and amount. | `amount`, `payment_method` |

### Refunds & Settlements

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `create_refund` | Process a full or partial refund for a paid order. | `order_id`, `payment_id` |
| `get_settlements` | Query settlement data, optionally filtered by UTR or date range. | None |

### Payment Links & Subscriptions

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `create_payment_link` | Generate a shareable payment link. | `amount`, `description` |
| `manage_subscription` | Create plans, subscriptions; pause/resume/cancel/get status. | `action` |

### International & Analytics

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `currency_conversion` | Convert between currencies for cross-border payments. | `amount`, `source_currency`, `target_currency` |
| `reconcile_transactions` | Cross-reference orders, payments, and settlements to find mismatches. | None (optional `order_ids`) |
| `analyze_activity` | Analyze activity data for failure rates, patterns, and insights. | `query` |

---

## Agent Intelligence

The AI agent is more than a simple API wrapper. It includes several autonomous intelligence layers:

### 1. Intelligent Decisioning

Before executing any payment, the agent:

1. Checks `discover_offers` for EMI/BNPL options
2. Calculates `convenience_fee` for at least 2 payment methods
3. Compares options and **explicitly recommends** the best choice with reasoning
4. Presents the decision before executing

Example decision: *"I recommend UPI because: zero convenience fee vs ₹150 for card, and instant settlement."*

### 2. Smart Retry Engine

When a payment fails, the agent follows a **fallback chain** instead of giving up:

```
CARD → UPI → WALLET → NETBANKING → BNPL → Payment Link
```

Each retry includes an explanation of why it is switching methods, and all attempts are tracked and reported.

### 3. Agentic Checkout Orchestration

When a user expresses purchase intent, the agent executes a **full autonomous pipeline** without asking for each step:

1. `generate_token` — Authenticate
2. `discover_offers` — Find best deals
3. `calculate_convenience_fee` — Compare costs (CARD vs UPI)
4. `create_order` — Place the order
5. Present decision with reasoning
6. `create_payment_link` — Generate shareable link
7. Deliver complete summary

### 4. Smart Reconciliation

When asked to reconcile, the agent:

1. Fetches settlements and order statuses
2. Cross-references paid vs. settled vs. refunded
3. Reports mismatches (paid but unsettled, created but unpaid)
4. Provides actionable suggestions

### 5. Proactive Alert Engine

The Gateway runs a background task that monitors the activity log and **proactively pushes alerts** to connected clients:

- **Multiple Failures** — Warns when several API calls fail in succession
- **Unpaid Orders** — Detects orders created but never paid

Alerts include severity levels (`info`, `warning`, `danger`) and suggested follow-up actions.

### 6. Workflow Detection

The agent detects multi-step workflows from natural language keywords and streams `workflow_step` events so the frontend can display progress indicators.

---

## Frontend

### UI Design

The frontend features a **dark theme** split-pane interface:

- **Left Panel** — Conversational chat with the AI agent
- **Right Panel** — Real-time analytics dashboard (togglable)
- **Resizable Divider** — Drag to adjust panel widths

**Design tokens:**

| Token | Value |
|-------|-------|
| Background | `#06060b` / `#0c0c14` |
| Accent | Purple gradient `#7c6cf0` → `#c084fc` |
| Success | Green |
| Warning | Amber |
| Danger | Red |
| Font | Inter |

### Chat Features

- **Suggestion chips** — Pre-built prompts for common scenarios
- **Tool call indicators** — Real-time status badges (pending, success, error) for each API call
- **Decision panels** — Expandable reasoning cards showing why the agent chose a specific action
- **Workflow progress** — Step-by-step progress bar for multi-tool workflows
- **QR codes** — Automatically rendered for generated payment links
- **Proactive alerts** — System-initiated notifications for failures or pending actions
- **Markdown rendering** — Rich text formatting in assistant responses

### Dashboard Features

- **Stats Cards** — Aggregate counts for orders, payments, refunds, and total amount
- **Charts** — Area chart (activity over time), pie chart (tool distribution), bar chart (payment methods)
- **Transaction Feed** — Live list of orders, payments, and refunds
- **Agent Activity Log** — Chronological log of every tool invocation

### WebSocket Integration

The frontend uses two concurrent WebSocket connections:

| Connection | Path | Purpose |
|------------|------|---------|
| Chat | `/ws/chat` | Send messages, receive streaming agent events |
| Dashboard | `/ws/dashboard` | Receive broadcast events for dashboard updates |

Both are managed through the `useWebSocket` custom hook, which handles connection lifecycle, reconnection, and listener registration.

---

## Testing

The test suite covers unit, integration, and end-to-end scenarios.

### Run Tests

```bash
# Ensure all services are running first
./start.sh

# In another terminal
pytest                          # Run all tests
pytest tests/test_e2e.py        # End-to-end tests only
pytest -m slow                  # Only long-running integration tests
pytest -m "not slow"            # Quick tests only
```

### Test Coverage

| Test File | Coverage |
|-----------|----------|
| `test_gateway_service.py` | Health check, REST chat, activity log, session clearing |
| `test_agent_service.py` | Agent streaming, tool orchestration, error handling |
| `test_pinelabs_service.py` | Tool definitions, tool execution, auth flow |
| `test_e2e.py` | Full auth flow, order creation, WebSocket streaming, session isolation, multi-step conversations |
| `test_edge_cases.py` | Invalid inputs, missing params, concurrent sessions |

### Key E2E Scenarios

- **Full auth flow** — Send "Authenticate" through Gateway, verify `generate_token` is called
- **Auth + order** — Single conversation turn creates both token and order
- **WebSocket streaming** — Verifies `tool_call` → `tool_result` → `response` event ordering
- **Session isolation** — Two sessions do not share conversation context
- **Multi-step conversation** — Auth → order → follow-up question tests memory

---

## Demo Scenarios

### 1. Smart Shopping Agent

> "I want to buy a phone for ₹45,000. What are the best EMI options?"

The agent will authenticate, discover offers, compare fees across CARD and UPI, create an order, recommend the optimal payment method, and generate a payment link.

### 2. Merchant Operations

> "Show me today's settlements and refund order XYZ"

Queries settlement data for the current date range and initiates a refund on the specified order.

### 3. Cross-Border Intelligence

> "I need to pay a US vendor $500. Convert and create a payment link."

Performs currency conversion from USD to INR and generates a payment link for the converted amount.

### 4. Subscription Management

> "Set up a monthly subscription of ₹999 for my SaaS product"

Creates a subscription plan with monthly frequency and the specified amount.

### 5. Payment Link Generation

> "Create a payment link for ₹2,500 for invoice #1234 and send to customer@email.com"

Generates a payment link with the description and customer details, rendered as a QR code in the chat.

### 6. Multi-step Commerce Flow

> "Register a new customer John Doe, create an order for ₹10,000, and find the best payment method"

Executes the full pipeline: customer creation → order creation → offer discovery → fee comparison → recommendation.

### 7. Transaction Reconciliation

> "Reconcile my recent transactions and check for mismatches"

Cross-references orders, payments, and settlements; reports any unpaid orders, unsettled payments, or refund discrepancies.

---

## Test Credentials

For the Pine Labs **UAT sandbox**:

| Credential | Value |
|------------|-------|
| Test Card (Visa) | `4012001037141112` |
| Card Expiry | Any future date |
| Card CVV | `123` |
| UPI VPA (success) | `success@upi` |
| UPI VPA (failure) | `failure@upi` |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Agent service error` in chat | Verify AWS credentials and Bedrock model access in `.env` |
| `403` from Pine Labs API | Check `PINE_LABS_CLIENT_ID` and `PINE_LABS_CLIENT_SECRET` |
| WebSocket not connecting | Ensure the Gateway is running on port 8000 and Vite proxy is configured |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in the relevant service directory |
| Frontend blank screen | Run `npm install` in `frontend/` and verify `npm run dev` is running |
| Services not starting | Check that ports 8000, 8001, 8002, and 5173 are not already in use |

---

## License

Built for the Pine Labs AI Hackathon 2026. All rights reserved.
