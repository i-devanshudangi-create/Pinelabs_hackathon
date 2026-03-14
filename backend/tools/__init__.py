from __future__ import annotations

from .auth import generate_token
from .customers import create_customer
from .orders import create_order, get_order_status
from .payments import create_payment
from .offers import discover_offers
from .refunds import create_refund
from .settlements import get_settlements
from .payment_links import create_payment_link
from .subscriptions import manage_subscription
from .convenience_fee import calculate_convenience_fee
from .international import currency_conversion

TOOL_REGISTRY: dict[str, callable] = {
    "generate_token": generate_token,
    "create_customer": create_customer,
    "create_order": create_order,
    "get_order_status": get_order_status,
    "create_payment": create_payment,
    "discover_offers": discover_offers,
    "create_refund": create_refund,
    "get_settlements": get_settlements,
    "create_payment_link": create_payment_link,
    "manage_subscription": manage_subscription,
    "calculate_convenience_fee": calculate_convenience_fee,
    "currency_conversion": currency_conversion,
}

TOOL_DEFINITIONS = [
    {
        "name": "generate_token",
        "description": "Authenticate with Pine Labs Plural API and obtain a Bearer access token. Must be called before any other Pine Labs API call. Returns an access_token and its expiry.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "create_customer",
        "description": "Create a new customer profile in the Pine Labs Plural system. This stores the customer's details for future orders and payments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "first_name": {"type": "string", "description": "Customer's first name"},
                "last_name": {"type": "string", "description": "Customer's last name"},
                "email": {"type": "string", "description": "Customer's email address"},
                "phone": {"type": "string", "description": "Customer's phone number (10 digits)"},
                "merchant_customer_reference": {"type": "string", "description": "Unique merchant-side customer identifier"},
            },
            "required": ["first_name", "last_name", "email", "phone"],
        },
    },
    {
        "name": "create_order",
        "description": "Create a new payment order in Pine Labs Plural. This is required before initiating any payment. Amount is in paisa (e.g. 100 = ₹1). Returns an order_id needed for payment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Order amount in paisa (100 paisa = ₹1). Example: 4500000 for ₹45,000"},
                "currency": {"type": "string", "description": "Currency code (e.g. INR)", "default": "INR"},
                "merchant_order_reference": {"type": "string", "description": "Unique merchant-side order reference ID"},
                "notes": {"type": "string", "description": "Optional notes for the order"},
                "customer_id": {"type": "string", "description": "Pine Labs customer ID if available"},
                "callback_url": {"type": "string", "description": "URL to receive payment completion callback"},
            },
            "required": ["amount", "currency"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Get the current status and details of an order by its Pine Labs order ID. Returns order status (PENDING, PROCESSED, CANCELLED, FAILED), payment details, and more.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Pine Labs order ID (e.g. v1-240820090251-aa-xwuI7J)"},
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "create_payment",
        "description": "Execute a payment against an existing order. Supports multiple payment methods: CARD, UPI (collect/intent/QR), NETBANKING, WALLET, BNPL. For UPI collect, provide the customer's VPA. Returns payment status and any challenge URL for customer action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Pine Labs order ID to pay against"},
                "payment_method": {
                    "type": "string",
                    "enum": ["CARD", "UPI", "NETBANKING", "WALLET", "BNPL"],
                    "description": "Payment method to use",
                },
                "amount": {"type": "integer", "description": "Payment amount in paisa"},
                "currency": {"type": "string", "description": "Currency code (e.g. INR)", "default": "INR"},
                "upi_vpa": {"type": "string", "description": "Customer's UPI VPA (required for UPI collect flow, e.g. user@upi)"},
                "upi_mode": {
                    "type": "string",
                    "enum": ["COLLECT", "INTENT", "QR"],
                    "description": "UPI transaction mode. COLLECT sends request to VPA, INTENT generates deep link, QR generates QR code",
                    "default": "COLLECT",
                },
                "card_number": {"type": "string", "description": "Card number (required for CARD payment)"},
                "card_expiry_month": {"type": "string", "description": "Card expiry month MM"},
                "card_expiry_year": {"type": "string", "description": "Card expiry year YYYY"},
                "card_cvv": {"type": "string", "description": "Card CVV"},
                "card_holder_name": {"type": "string", "description": "Name on card"},
            },
            "required": ["order_id", "payment_method", "amount"],
        },
    },
    {
        "name": "discover_offers",
        "description": "Discover available EMI and BNPL offers for a given amount. Uses the Pine Labs Affordability Suite to find the best financing options including credit EMI, debit EMI, and cardless EMI plans across banks. Returns offers with monthly installment amounts, interest rates, and tenure options.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Transaction amount in paisa to discover offers for"},
                "card_number": {"type": "string", "description": "First 6 or full card number to get card-specific EMI offers (optional)"},
                "product_code": {"type": "string", "description": "Product/category code for offer filtering (optional)"},
            },
            "required": ["amount"],
        },
    },
    {
        "name": "create_refund",
        "description": "Initiate a refund for a processed order. Can do full or partial refunds. Returns the refund status and details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Pine Labs order ID to refund"},
                "payment_id": {"type": "string", "description": "Payment ID within the order to refund"},
                "amount": {"type": "integer", "description": "Refund amount in paisa. If not provided, full refund is issued."},
                "merchant_refund_reference": {"type": "string", "description": "Unique merchant-side refund reference"},
            },
            "required": ["order_id", "payment_id"],
        },
    },
    {
        "name": "get_settlements",
        "description": "Get settlement information. Can retrieve all settlements or filter by UTR number. Returns settlement amounts, dates, UTR numbers, and associated transactions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "utr": {"type": "string", "description": "UTR number to filter specific settlement (optional)"},
                "from_date": {"type": "string", "description": "Start date filter in YYYY-MM-DD format (optional)"},
                "to_date": {"type": "string", "description": "End date filter in YYYY-MM-DD format (optional)"},
            },
            "required": [],
        },
    },
    {
        "name": "create_payment_link",
        "description": "Generate a shareable payment link that can be sent to customers via email/SMS/WhatsApp. The customer can then pay through the link using any supported payment method.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Payment amount in paisa"},
                "currency": {"type": "string", "description": "Currency code (e.g. INR)", "default": "INR"},
                "description": {"type": "string", "description": "Description/purpose of the payment link"},
                "customer_name": {"type": "string", "description": "Customer name"},
                "customer_email": {"type": "string", "description": "Customer email for sending link"},
                "customer_phone": {"type": "string", "description": "Customer phone for sending link"},
                "expiry_minutes": {"type": "integer", "description": "Link expiry time in minutes", "default": 1440},
            },
            "required": ["amount", "description"],
        },
    },
    {
        "name": "manage_subscription",
        "description": "Manage subscriptions: create a new subscription plan and subscription, or pause/resume/cancel an existing subscription. For creation, specify plan details and frequency. For management, provide the subscription_id and action.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create_plan", "create_subscription", "pause", "resume", "cancel", "get_status"],
                    "description": "Action to perform on the subscription",
                },
                "plan_name": {"type": "string", "description": "Name of the subscription plan (for create_plan)"},
                "plan_amount": {"type": "integer", "description": "Plan amount in paisa (for create_plan)"},
                "currency": {"type": "string", "description": "Currency code", "default": "INR"},
                "frequency": {
                    "type": "string",
                    "enum": ["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"],
                    "description": "Billing frequency (for create_plan)",
                },
                "plan_id": {"type": "string", "description": "Plan ID (for create_subscription)"},
                "subscription_id": {"type": "string", "description": "Subscription ID (for pause/resume/cancel/get_status)"},
                "customer_id": {"type": "string", "description": "Customer ID (for create_subscription)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "calculate_convenience_fee",
        "description": "Calculate the convenience fee for a transaction based on the payment method and amount. Returns the fee amount and total amount including fee.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Transaction amount in paisa"},
                "payment_method": {
                    "type": "string",
                    "enum": ["CARD", "UPI", "NETBANKING", "WALLET"],
                    "description": "Payment method to calculate fee for",
                },
            },
            "required": ["amount", "payment_method"],
        },
    },
    {
        "name": "currency_conversion",
        "description": "Convert between currencies for international payments. Provides the exchange rate and converted amount. Useful for cross-border payment scenarios.",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Amount in paisa of the source currency"},
                "source_currency": {"type": "string", "description": "Source currency code (e.g. INR)"},
                "target_currency": {"type": "string", "description": "Target currency code (e.g. USD, EUR, GBP)"},
            },
            "required": ["amount", "source_currency", "target_currency"],
        },
    },
]
