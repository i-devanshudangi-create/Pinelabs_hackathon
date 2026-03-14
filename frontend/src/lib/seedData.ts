import type { ActivityEntry, WorkflowStep } from './types';

function at(hour: number, minute: number, second = 0): string {
  const d = new Date();
  d.setHours(hour, minute, second, 0);
  return d.toISOString();
}

function pair(tool: string, input: Record<string, any>, result: Record<string, any>, hour: number, minute: number): ActivityEntry[] {
  return [
    { event: 'tool_call', tool_name: tool, tool_input: input, timestamp: at(hour, minute, 0) },
    { event: 'tool_result', tool_name: tool, tool_result: result, timestamp: at(hour, minute, 30) },
  ];
}

function auth(hour: number, minute: number): ActivityEntry[] {
  return pair('generate_token', {}, { success: true, token_type: 'Bearer' }, hour, minute);
}

export const SEED_ACTIVITIES: ActivityEntry[] = [

  // ════════════════════════════════════════════════════════
  //  9:30 – 10:00 — Shop opens, first transactions
  // ════════════════════════════════════════════════════════

  ...auth(9, 30),

  // 9:35 — Bulk order for wholesale buyer (₹25,000)
  ...pair('discover_offers', { amount: 2500000 }, { success: true, offers: [{ offer_id: 'OFF-MORN-01', description: 'Bulk purchase 5% cashback', discount: 125000 }] }, 9, 35),
  ...pair('calculate_convenience_fee', { amount: 2500000, payment_method: 'CARD' }, { success: true, convenience_fee: 45000, total: 2545000 }, 9, 37),
  ...pair('calculate_convenience_fee', { amount: 2500000, payment_method: 'UPI' }, { success: true, convenience_fee: 0, total: 2500000 }, 9, 38),
  ...pair('create_order', { amount: 2500000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m01', status: 'CREATED', order_amount: { value: 2500000, currency: 'INR' } } }, 9, 40),
  ...pair('create_payment', { order_id: 'v1-260314-m01', amount: 2500000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-m01', status: 'PROCESSED', payment_amount: { value: 2500000, currency: 'INR' }, payment_method: 'UPI' }] } }, 9, 42),

  // 9:45 — Small retail order (₹899)
  ...auth(9, 45),
  ...pair('create_order', { amount: 89900, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m02', status: 'CREATED', order_amount: { value: 89900, currency: 'INR' } } }, 9, 46),
  ...pair('create_payment', { order_id: 'v1-260314-m02', amount: 89900, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-m02', status: 'PROCESSED', payment_amount: { value: 89900, currency: 'INR' }, payment_method: 'CARD' }] } }, 9, 47),

  // 9:50 — Customer registration + subscription setup
  ...pair('create_customer', { email: 'ravi.sharma@gmail.com', phone: '9876543210', name: 'Ravi Sharma' }, { success: true, customer_id: 'cust-001' }, 9, 50),
  ...pair('manage_subscription', { customer_id: 'cust-001', plan: 'premium-monthly', amount: 99900 }, { success: true, subscription_id: 'sub-001', status: 'ACTIVE' }, 9, 52),

  // ════════════════════════════════════════════════════════
  //  10:00 – 10:30 — Building up
  // ════════════════════════════════════════════════════════

  // 10:00 — Payment link for remote customer (₹3,500)
  ...auth(10, 0),
  ...pair('create_order', { amount: 350000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m03', status: 'CREATED', order_amount: { value: 350000, currency: 'INR' } } }, 10, 2),
  ...pair('create_payment_link', { amount: 350000, description: 'Invoice #INV-2026-0314' }, { success: true, payment_url: 'https://pci.pluralonline.com/pay/121524/v1-260314-m03' }, 10, 4),

  // 10:10 — Failed card payment + UPI retry (₹1,750)
  ...pair('create_order', { amount: 175000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m04', status: 'CREATED', order_amount: { value: 175000, currency: 'INR' } } }, 10, 10),
  ...pair('create_payment', { order_id: 'v1-260314-m04', amount: 175000, payment_method: 'CARD' }, { error: 'Card declined — insufficient funds' }, 10, 12),
  ...pair('create_payment', { order_id: 'v1-260314-m04', amount: 175000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-m04', status: 'PROCESSED', payment_amount: { value: 175000, currency: 'INR' }, payment_method: 'UPI' }] } }, 10, 14),

  // 10:20 — International buyer (currency conversion + order)
  ...auth(10, 20),
  ...pair('currency_conversion', { amount: 150, from: 'USD', to: 'INR' }, { success: true, converted_amount: 12525, rate: 83.5 }, 10, 22),
  ...pair('create_order', { amount: 1252500, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m05', status: 'CREATED', order_amount: { value: 1252500, currency: 'INR' } } }, 10, 24),
  ...pair('create_payment', { order_id: 'v1-260314-m05', amount: 1252500, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-m05', status: 'PROCESSED', payment_amount: { value: 1252500, currency: 'INR' }, payment_method: 'CARD' }] } }, 10, 26),

  // ════════════════════════════════════════════════════════
  //  10:30 – 11:00 — Getting busier
  // ════════════════════════════════════════════════════════

  // 10:30 — Discover offers for upcoming sale
  ...pair('discover_offers', { amount: 500000 }, { success: true, offers: [{ offer_id: 'OFF-FLASH-01', description: '₹200 off on UPI payments', discount: 20000 }, { offer_id: 'OFF-FLASH-02', description: 'No-cost EMI on HDFC cards', discount: 0 }] }, 10, 30),

  // 10:40 — Order + netbanking timeout + card retry (₹4,200)
  ...pair('create_order', { amount: 420000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m06', status: 'CREATED', order_amount: { value: 420000, currency: 'INR' } } }, 10, 40),
  ...pair('create_payment', { order_id: 'v1-260314-m06', amount: 420000, payment_method: 'NETBANKING' }, { error: 'Gateway timeout — bank server unreachable' }, 10, 42),
  ...pair('create_payment', { order_id: 'v1-260314-m06', amount: 420000, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-m06', status: 'PROCESSED', payment_amount: { value: 420000, currency: 'INR' }, payment_method: 'CARD' }] } }, 10, 44),

  // ════════════════════════════════════════════════════════
  //  11:00 – 11:30 — Peak hours start
  // ════════════════════════════════════════════════════════

  // 11:00 — Re-auth + high-value electronics order (₹49,999)
  ...auth(11, 0),
  ...pair('discover_offers', { amount: 4999900 }, { success: true, offers: [{ offer_id: 'OFF-ELEC-01', description: 'Save ₹5,000 on Credit Card EMI', discount: 500000 }, { offer_id: 'OFF-ELEC-02', description: '10% instant discount on ICICI', discount: 499990 }] }, 11, 2),
  ...pair('calculate_convenience_fee', { amount: 4999900, payment_method: 'CARD' }, { success: true, convenience_fee: 89998, total: 5089898 }, 11, 4),
  ...pair('calculate_convenience_fee', { amount: 4999900, payment_method: 'UPI' }, { success: true, convenience_fee: 0, total: 4999900 }, 11, 5),
  ...pair('create_order', { amount: 4999900, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m07', status: 'CREATED', order_amount: { value: 4999900, currency: 'INR' } } }, 11, 7),
  ...pair('create_payment', { order_id: 'v1-260314-m07', amount: 4999900, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-m07', status: 'PROCESSED', payment_amount: { value: 4999900, currency: 'INR' }, payment_method: 'UPI' }] } }, 11, 9),

  // 11:15 — Rapid-fire small orders (food delivery merchant)
  ...pair('create_order', { amount: 25000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m08', status: 'CREATED', order_amount: { value: 25000, currency: 'INR' } } }, 11, 15),
  ...pair('create_payment', { order_id: 'v1-260314-m08', amount: 25000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-m08', status: 'PROCESSED', payment_amount: { value: 25000, currency: 'INR' }, payment_method: 'UPI' }] } }, 11, 16),
  ...pair('create_order', { amount: 35000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m09', status: 'CREATED', order_amount: { value: 35000, currency: 'INR' } } }, 11, 18),
  ...pair('create_payment', { order_id: 'v1-260314-m09', amount: 35000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-m09', status: 'PROCESSED', payment_amount: { value: 35000, currency: 'INR' }, payment_method: 'UPI' }] } }, 11, 19),
  ...pair('create_order', { amount: 42000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m10', status: 'CREATED', order_amount: { value: 42000, currency: 'INR' } } }, 11, 21),
  ...pair('create_payment', { order_id: 'v1-260314-m10', amount: 42000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-m10', status: 'PROCESSED', payment_amount: { value: 42000, currency: 'INR' }, payment_method: 'UPI' }] } }, 11, 22),

  // ════════════════════════════════════════════════════════
  //  11:30 – 12:00 — Peak continues
  // ════════════════════════════════════════════════════════

  // 11:30 — New customer + order (₹12,500)
  ...pair('create_customer', { email: 'priya.patel@gmail.com', phone: '8765432109', name: 'Priya Patel' }, { success: true, customer_id: 'cust-002' }, 11, 30),
  ...pair('create_order', { amount: 1250000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m11', status: 'CREATED', order_amount: { value: 1250000, currency: 'INR' } } }, 11, 32),
  ...pair('create_payment', { order_id: 'v1-260314-m11', amount: 1250000, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-m11', status: 'PROCESSED', payment_amount: { value: 1250000, currency: 'INR' }, payment_method: 'CARD' }] } }, 11, 34),

  // 11:40 — Refund for defective product
  ...auth(11, 40),
  ...pair('get_order_status', { order_id: 'v1-260314-m02' }, { success: true, data: { order_id: 'v1-260314-m02', status: 'PAID', order_amount: { value: 89900, currency: 'INR' } } }, 11, 42),
  ...pair('create_refund', { order_id: 'v1-260314-m02', amount: 89900, reason: 'Defective product returned' }, { success: true, refund_id: 'ref-001', status: 'INITIATED' }, 11, 44),

  // 11:50 — Payment link batch (invoicing)
  ...pair('create_order', { amount: 150000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m12', status: 'CREATED', order_amount: { value: 150000, currency: 'INR' } } }, 11, 50),
  ...pair('create_payment_link', { amount: 150000, description: 'Invoice #INV-2026-0315' }, { success: true, payment_url: 'https://pci.pluralonline.com/pay/121524/v1-260314-m12' }, 11, 52),
  ...pair('create_order', { amount: 275000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m13', status: 'CREATED', order_amount: { value: 275000, currency: 'INR' } } }, 11, 54),
  ...pair('create_payment_link', { amount: 275000, description: 'Invoice #INV-2026-0316' }, { success: true, payment_url: 'https://pci.pluralonline.com/pay/121524/v1-260314-m13' }, 11, 56),

  // ════════════════════════════════════════════════════════
  //  12:00 – 12:30 — Midday
  // ════════════════════════════════════════════════════════

  // 12:00 — Subscription customer #2
  ...pair('create_customer', { email: 'arjun.mehta@outlook.com', phone: '7654321098', name: 'Arjun Mehta' }, { success: true, customer_id: 'cust-003' }, 12, 0),
  ...pair('manage_subscription', { customer_id: 'cust-003', plan: 'starter-annual', amount: 599900 }, { success: true, subscription_id: 'sub-002', status: 'ACTIVE' }, 12, 2),

  // 12:15 — Currency conversion + international order ($275)
  ...pair('currency_conversion', { amount: 275, from: 'USD', to: 'INR' }, { success: true, converted_amount: 22963, rate: 83.5 }, 12, 15),
  ...pair('currency_conversion', { amount: 200, from: 'EUR', to: 'INR' }, { success: true, converted_amount: 18200, rate: 91.0 }, 12, 17),
  ...pair('create_order', { amount: 2296300, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-m14', status: 'CREATED', order_amount: { value: 2296300, currency: 'INR' } } }, 12, 19),
  ...pair('create_payment', { order_id: 'v1-260314-m14', amount: 2296300, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-m14', status: 'PROCESSED', payment_amount: { value: 2296300, currency: 'INR' }, payment_method: 'CARD' }] } }, 12, 21),

  // ════════════════════════════════════════════════════════
  //  12:30 – 13:00 — Post-lunch
  // ════════════════════════════════════════════════════════

  // 12:30 — Re-auth + order (₹7,800)
  ...auth(12, 30),
  ...pair('create_order', { amount: 780000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-a01', status: 'CREATED', order_amount: { value: 780000, currency: 'INR' } } }, 12, 32),
  ...pair('discover_offers', { amount: 780000 }, { success: true, offers: [{ offer_id: 'OFF-AFT-01', description: 'Flat ₹300 off on orders above ₹5,000', discount: 30000 }] }, 12, 34),
  ...pair('create_payment', { order_id: 'v1-260314-a01', amount: 780000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-a01', status: 'PROCESSED', payment_amount: { value: 780000, currency: 'INR' }, payment_method: 'UPI' }] } }, 12, 36),

  // 12:45 — Wallet payment (₹600)
  ...pair('create_order', { amount: 60000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-a02', status: 'CREATED', order_amount: { value: 60000, currency: 'INR' } } }, 12, 45),
  ...pair('create_payment', { order_id: 'v1-260314-a02', amount: 60000, payment_method: 'WALLET' }, { success: true, data: { payments: [{ id: 'pay-a02', status: 'PROCESSED', payment_amount: { value: 60000, currency: 'INR' }, payment_method: 'WALLET' }] } }, 12, 47),

  // ════════════════════════════════════════════════════════
  //  13:00 – 13:30 — Afternoon flow
  // ════════════════════════════════════════════════════════

  // 13:00 — Failed UPI + card retry (₹2,100)
  ...pair('create_order', { amount: 210000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-a03', status: 'CREATED', order_amount: { value: 210000, currency: 'INR' } } }, 13, 0),
  ...pair('create_payment', { order_id: 'v1-260314-a03', amount: 210000, payment_method: 'UPI' }, { error: 'UPI timeout — transaction expired after 5 minutes' }, 13, 2),
  ...pair('create_payment', { order_id: 'v1-260314-a03', amount: 210000, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-a03', status: 'PROCESSED', payment_amount: { value: 210000, currency: 'INR' }, payment_method: 'CARD' }] } }, 13, 4),

  // 13:15 — Batch of 4 quick orders (café POS)
  ...pair('create_order', { amount: 15000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-a04', status: 'CREATED', order_amount: { value: 15000, currency: 'INR' } } }, 13, 15),
  ...pair('create_payment', { order_id: 'v1-260314-a04', amount: 15000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-a04', status: 'PROCESSED', payment_amount: { value: 15000, currency: 'INR' }, payment_method: 'UPI' }] } }, 13, 16),
  ...pair('create_order', { amount: 22000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-a05', status: 'CREATED', order_amount: { value: 22000, currency: 'INR' } } }, 13, 18),
  ...pair('create_payment', { order_id: 'v1-260314-a05', amount: 22000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-a05', status: 'PROCESSED', payment_amount: { value: 22000, currency: 'INR' }, payment_method: 'UPI' }] } }, 13, 19),
  ...pair('create_order', { amount: 18500, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-a06', status: 'CREATED', order_amount: { value: 18500, currency: 'INR' } } }, 13, 21),
  ...pair('create_payment', { order_id: 'v1-260314-a06', amount: 18500, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-a06', status: 'PROCESSED', payment_amount: { value: 18500, currency: 'INR' }, payment_method: 'CARD' }] } }, 13, 22),
  ...pair('create_order', { amount: 31000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-a07', status: 'CREATED', order_amount: { value: 31000, currency: 'INR' } } }, 13, 24),
  ...pair('create_payment', { order_id: 'v1-260314-a07', amount: 31000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-a07', status: 'PROCESSED', payment_amount: { value: 31000, currency: 'INR' }, payment_method: 'UPI' }] } }, 13, 25),

  // ════════════════════════════════════════════════════════
  //  13:30 – 14:00 — Afternoon continued
  // ════════════════════════════════════════════════════════

  // 13:30 — Refund for duplicate order
  ...pair('get_order_status', { order_id: 'v1-260314-m08' }, { success: true, data: { order_id: 'v1-260314-m08', status: 'PAID', order_amount: { value: 25000, currency: 'INR' } } }, 13, 30),
  ...pair('create_refund', { order_id: 'v1-260314-m08', amount: 25000, reason: 'Duplicate order' }, { success: true, refund_id: 'ref-002', status: 'INITIATED' }, 13, 32),

  // 13:40 — New customer + subscription
  ...pair('create_customer', { email: 'neha.gupta@yahoo.com', phone: '6543210987', name: 'Neha Gupta' }, { success: true, customer_id: 'cust-004' }, 13, 40),
  ...pair('manage_subscription', { customer_id: 'cust-004', plan: 'enterprise-monthly', amount: 249900 }, { success: true, subscription_id: 'sub-003', status: 'ACTIVE' }, 13, 42),

  // 13:50 — Payment link for B2B invoice
  ...pair('create_order', { amount: 8500000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-a08', status: 'CREATED', order_amount: { value: 8500000, currency: 'INR' } } }, 13, 50),
  ...pair('create_payment_link', { amount: 8500000, description: 'B2B Invoice #INV-2026-B001' }, { success: true, payment_url: 'https://pci.pluralonline.com/pay/121524/v1-260314-a08' }, 13, 52),

  // ════════════════════════════════════════════════════════
  //  14:00 – 14:30 — Late afternoon rush
  // ════════════════════════════════════════════════════════

  // 14:00 — Re-auth + big sale (₹34,999)
  ...auth(14, 0),
  ...pair('discover_offers', { amount: 3499900 }, { success: true, offers: [{ offer_id: 'OFF-EVE-01', description: '₹3,000 cashback on SBI Credit Card', discount: 300000 }, { offer_id: 'OFF-EVE-02', description: 'No-cost EMI 6 months HDFC', discount: 0 }, { offer_id: 'OFF-EVE-03', description: '₹500 off via UPI', discount: 50000 }] }, 14, 2),
  ...pair('calculate_convenience_fee', { amount: 3499900, payment_method: 'CARD' }, { success: true, convenience_fee: 62998, total: 3562898 }, 14, 4),
  ...pair('calculate_convenience_fee', { amount: 3499900, payment_method: 'UPI' }, { success: true, convenience_fee: 0, total: 3499900 }, 14, 5),
  ...pair('create_order', { amount: 3499900, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-e01', status: 'CREATED', order_amount: { value: 3499900, currency: 'INR' } } }, 14, 7),
  ...pair('create_payment', { order_id: 'v1-260314-e01', amount: 3499900, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-e01', status: 'PROCESSED', payment_amount: { value: 3499900, currency: 'INR' }, payment_method: 'CARD' }] } }, 14, 9),

  // 14:15 — Multiple small orders (afternoon rush)
  ...pair('create_order', { amount: 45000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-e02', status: 'CREATED', order_amount: { value: 45000, currency: 'INR' } } }, 14, 15),
  ...pair('create_payment', { order_id: 'v1-260314-e02', amount: 45000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-e02', status: 'PROCESSED', payment_amount: { value: 45000, currency: 'INR' }, payment_method: 'UPI' }] } }, 14, 16),
  ...pair('create_order', { amount: 67000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-e03', status: 'CREATED', order_amount: { value: 67000, currency: 'INR' } } }, 14, 18),
  ...pair('create_payment', { order_id: 'v1-260314-e03', amount: 67000, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-e03', status: 'PROCESSED', payment_amount: { value: 67000, currency: 'INR' }, payment_method: 'CARD' }] } }, 14, 19),
  ...pair('create_order', { amount: 19900, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-e04', status: 'CREATED', order_amount: { value: 19900, currency: 'INR' } } }, 14, 21),
  ...pair('create_payment', { order_id: 'v1-260314-e04', amount: 19900, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-e04', status: 'PROCESSED', payment_amount: { value: 19900, currency: 'INR' }, payment_method: 'UPI' }] } }, 14, 22),

  // ════════════════════════════════════════════════════════
  //  14:30 – 15:00 — Winding down
  // ════════════════════════════════════════════════════════

  // 14:30 — Failed payment cascade + eventual success (₹8,500)
  ...pair('create_order', { amount: 850000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-e05', status: 'CREATED', order_amount: { value: 850000, currency: 'INR' } } }, 14, 30),
  ...pair('create_payment', { order_id: 'v1-260314-e05', amount: 850000, payment_method: 'CARD' }, { error: 'Authentication failed — 3DS verification declined' }, 14, 32),
  ...pair('create_payment', { order_id: 'v1-260314-e05', amount: 850000, payment_method: 'NETBANKING' }, { error: 'Session expired — user did not complete' }, 14, 34),
  ...pair('create_payment', { order_id: 'v1-260314-e05', amount: 850000, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-e05', status: 'PROCESSED', payment_amount: { value: 850000, currency: 'INR' }, payment_method: 'UPI' }] } }, 14, 36),

  // 14:40 — Order status check + settlement query
  ...pair('get_order_status', { order_id: 'v1-260314-m07' }, { success: true, data: { order_id: 'v1-260314-m07', status: 'PAID', order_amount: { value: 4999900, currency: 'INR' } } }, 14, 40),
  ...pair('get_settlements', { from_date: '2026-03-14', to_date: '2026-03-14' }, { success: true, settlements: [{ settlement_id: 'stl-001', amount: 8764800, status: 'COMPLETED', date: '2026-03-14' }] }, 14, 42),

  // 14:50 — Customer + high-value order (₹15,000)
  ...pair('create_customer', { email: 'ankit.verma@proton.me', phone: '5432109876', name: 'Ankit Verma' }, { success: true, customer_id: 'cust-005' }, 14, 50),
  ...pair('create_order', { amount: 1500000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-e06', status: 'CREATED', order_amount: { value: 1500000, currency: 'INR' } } }, 14, 52),
  ...pair('create_payment', { order_id: 'v1-260314-e06', amount: 1500000, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-e06', status: 'PROCESSED', payment_amount: { value: 1500000, currency: 'INR' }, payment_method: 'CARD' }] } }, 14, 54),

  // ════════════════════════════════════════════════════════
  //  15:00 – 15:30 — Final session
  // ════════════════════════════════════════════════════════

  // 15:00 — Payment links for deliveries
  ...pair('create_order', { amount: 320000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-e07', status: 'CREATED', order_amount: { value: 320000, currency: 'INR' } } }, 15, 0),
  ...pair('create_payment_link', { amount: 320000, description: 'Delivery #DEL-2026-0315-A' }, { success: true, payment_url: 'https://pci.pluralonline.com/pay/121524/v1-260314-e07' }, 15, 2),
  ...pair('create_order', { amount: 180000, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-e08', status: 'CREATED', order_amount: { value: 180000, currency: 'INR' } } }, 15, 4),
  ...pair('create_payment_link', { amount: 180000, description: 'Delivery #DEL-2026-0315-B' }, { success: true, payment_url: 'https://pci.pluralonline.com/pay/121524/v1-260314-e08' }, 15, 6),

  // 15:10 — Last orders
  ...auth(15, 10),
  ...pair('create_order', { amount: 99900, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-n01', status: 'CREATED', order_amount: { value: 99900, currency: 'INR' } } }, 15, 11),
  ...pair('create_payment', { order_id: 'v1-260314-n01', amount: 99900, payment_method: 'UPI' }, { success: true, data: { payments: [{ id: 'pay-n01', status: 'PROCESSED', payment_amount: { value: 99900, currency: 'INR' }, payment_method: 'UPI' }] } }, 15, 13),
  ...pair('create_order', { amount: 259900, currency: 'INR' }, { success: true, data: { order_id: 'v1-260314-n02', status: 'CREATED', order_amount: { value: 259900, currency: 'INR' } } }, 15, 14),
  ...pair('create_payment', { order_id: 'v1-260314-n02', amount: 259900, payment_method: 'CARD' }, { success: true, data: { payments: [{ id: 'pay-n02', status: 'PROCESSED', payment_amount: { value: 259900, currency: 'INR' }, payment_method: 'CARD' }] } }, 15, 16),

  // 15:20 — End-of-session analysis
  ...pair('analyze_activity', { query: 'daily summary', activities: [] }, { total_api_calls: 78, failure_rate: 6.4, tool_breakdown: { create_order: 28, create_payment: 30, generate_token: 6, discover_offers: 4, create_payment_link: 5, create_customer: 5 }, payment_methods: { UPI: 16, CARD: 11, WALLET: 1, NETBANKING: 1 }, insights: [{ severity: 'info', message: 'Healthy failure rate: 6.4%.' }, { severity: 'info', message: 'UPI is the dominant payment method (55%).' }, { severity: 'info', message: 'Most called API: create_payment (30 calls).' }], query: 'daily summary' }, 15, 20),

  // 15:25 — Reconciliation
  ...pair('reconcile_transactions', { order_ids: [
    'v1-260314-m01', 'v1-260314-m02', 'v1-260314-m03', 'v1-260314-m04', 'v1-260314-m05',
    'v1-260314-m06', 'v1-260314-m07', 'v1-260314-m08', 'v1-260314-m09', 'v1-260314-m10',
    'v1-260314-m11', 'v1-260314-m12', 'v1-260314-m13', 'v1-260314-m14',
    'v1-260314-a01', 'v1-260314-a02', 'v1-260314-a03', 'v1-260314-a04', 'v1-260314-a05',
    'v1-260314-a06', 'v1-260314-a07', 'v1-260314-a08',
    'v1-260314-e01', 'v1-260314-e02', 'v1-260314-e03', 'v1-260314-e04', 'v1-260314-e05',
    'v1-260314-e06', 'v1-260314-e07', 'v1-260314-e08',
    'v1-260314-n01', 'v1-260314-n02',
  ] }, {
    total_orders: 31,
    paid_orders: 25,
    unpaid_orders: 6,
    settled: 20,
    unsettled: 5,
    refunded: 2,
    mismatches: [
      { order_id: 'v1-260314-m03', type: 'CREATED_NOT_PAID', message: 'Order m03 — payment link sent, awaiting completion' },
      { order_id: 'v1-260314-m12', type: 'CREATED_NOT_PAID', message: 'Order m12 — invoice link pending (₹1,500)' },
      { order_id: 'v1-260314-m13', type: 'CREATED_NOT_PAID', message: 'Order m13 — invoice link pending (₹2,750)' },
      { order_id: 'v1-260314-a08', type: 'CREATED_NOT_PAID', message: 'Order a08 — B2B invoice pending (₹85,000)' },
      { order_id: 'v1-260314-e07', type: 'CREATED_NOT_PAID', message: 'Order e07 — delivery link pending (₹3,200)' },
      { order_id: 'v1-260314-e08', type: 'CREATED_NOT_PAID', message: 'Order e08 — delivery link pending (₹1,800)' },
    ],
    summary: '25/31 orders paid (80.6%). 20 settled, 5 awaiting settlement. 6 payment links still pending. 2 refunds processed. Total volume: ₹1,04,847. UPI: 55%, Card: 38%, Others: 7%.',
  }, 15, 25),

  // 15:28 — Final settlement check
  ...pair('get_settlements', { from_date: '2026-03-14', to_date: '2026-03-14' }, { success: true, settlements: [{ settlement_id: 'stl-001', amount: 8764800, status: 'COMPLETED', date: '2026-03-14' }, { settlement_id: 'stl-002', amount: 5823700, status: 'COMPLETED', date: '2026-03-14' }, { settlement_id: 'stl-003', amount: 3456200, status: 'PENDING', date: '2026-03-14' }] }, 15, 28),
];

const WF_ID = 'seed-wf-checkout';

export const SEED_WORKFLOW_STEPS: WorkflowStep[] = [
  { workflow_id: WF_ID, step_index: 0, total_steps: 7, step_name: 'Starting', status: 'success', workflow_type: 'checkout' },
  { workflow_id: WF_ID, step_index: 1, total_steps: 7, step_name: 'Authenticating', status: 'success', tool_name: 'generate_token', workflow_type: 'checkout' },
  { workflow_id: WF_ID, step_index: 2, total_steps: 7, step_name: 'Discovering Offers', status: 'success', tool_name: 'discover_offers', workflow_type: 'checkout' },
  { workflow_id: WF_ID, step_index: 3, total_steps: 7, step_name: 'Comparing Fees', status: 'success', tool_name: 'calculate_convenience_fee', workflow_type: 'checkout' },
  { workflow_id: WF_ID, step_index: 4, total_steps: 7, step_name: 'Creating Order', status: 'success', tool_name: 'create_order', workflow_type: 'checkout' },
  { workflow_id: WF_ID, step_index: 5, total_steps: 7, step_name: 'Processing Payment', status: 'success', tool_name: 'create_payment', workflow_type: 'checkout' },
  { workflow_id: WF_ID, step_index: 6, total_steps: 7, step_name: 'Done', status: 'success', workflow_type: 'checkout' },
];
