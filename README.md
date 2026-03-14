# PlurAgent — Agentic Commerce & Intelligent Payments Platform

An AI-powered commerce assistant that autonomously handles the full payment lifecycle through natural language, deeply integrating 12 Pine Labs Plural APIs as agent tools.

Built for the **Pine Labs AI Hackathon** (March 14, 2026).

## Architecture

- **Backend**: Python FastAPI + AWS Bedrock Claude (tool use)
- **Frontend**: React + Vite + Tailwind CSS + Recharts
- **AI Engine**: Claude 3.5 Sonnet via AWS Bedrock with native tool use
- **Real-time**: WebSocket for live chat streaming and dashboard updates

## Quick Start

### 1. Configure Environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your credentials
```

### 2. Start Backend

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn main:app --reload --port 8000
```

### 3. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — you'll see the split-pane interface with chat (left) and dashboard (right).

## Pine Labs API Tools (12)

| Tool | Description |
|------|-------------|
| `generate_token` | Authenticate with Pine Labs Plural |
| `create_customer` | Create customer profiles |
| `create_order` | Create payment orders |
| `get_order_status` | Check order status |
| `create_payment` | Execute payments (Card/UPI/Wallet/BNPL/NetBanking) |
| `discover_offers` | Find best EMI/BNPL offers |
| `create_refund` | Process refunds |
| `get_settlements` | Query settlements |
| `create_payment_link` | Generate shareable payment links |
| `manage_subscription` | Create/manage subscriptions |
| `calculate_convenience_fee` | Calculate transaction fees |
| `currency_conversion` | Cross-border currency conversion |

## Demo Scenarios

**1. Smart Shopping Agent**
> "I want to buy a phone for ₹45,000. What are the best EMI options?"

**2. Merchant Operations**
> "Show me today's settlements and refund order XYZ"

**3. Cross-Border Intelligence**
> "I need to pay a US vendor $500. Convert and create a payment link."

**4. Subscription Management**
> "Set up a monthly subscription of ₹999 for my SaaS product"

**5. Payment Link Generation**
> "Create a payment link for ₹2,500 for invoice #1234 and send to customer@email.com"

**6. Multi-step Commerce Flow**
> "Register a new customer John Doe, create an order for ₹10,000, and find the best payment method"
