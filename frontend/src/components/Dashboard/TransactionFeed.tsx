import { ArrowUpRight, ArrowDownLeft, Clock, CheckCircle2, XCircle, ArrowRightLeft } from 'lucide-react';
import type { ActivityEntry } from '../../lib/types';

interface Transaction {
  id: string;
  type: string;
  tool: string;
  amount?: number;
  currency?: string;
  status: 'success' | 'pending' | 'failed';
  timestamp: string;
  details: string;
}

interface Props {
  activities: ActivityEntry[];
}

function extractTransactions(activities: ActivityEntry[]): Transaction[] {
  const txns: Transaction[] = [];
  for (const a of activities) {
    if (a.event !== 'tool_result') continue;
    const result = a.tool_result || {};
    if (a.tool_name === 'create_order') {
      const data = result.data || result;
      txns.push({
        id: data.order_id || `ord-${txns.length}`,
        type: 'Order',
        tool: a.tool_name,
        amount: data.order_amount?.value,
        currency: data.order_amount?.currency || 'INR',
        status: data.status === 'FAILED' ? 'failed' : result.success === false ? 'failed' : 'success',
        timestamp: a.timestamp,
        details: data.order_id ? `ID: ${data.order_id.slice(-12)}` : 'Created',
      });
    } else if (a.tool_name === 'create_payment') {
      const data = result.data || result;
      const pay = data.payments?.[0] || {};
      txns.push({
        id: pay.id || `pay-${txns.length}`,
        type: 'Payment',
        tool: a.tool_name,
        amount: pay.payment_amount?.value,
        currency: pay.payment_amount?.currency || 'INR',
        status: pay.status === 'PROCESSED' ? 'success' : pay.status === 'FAILED' ? 'failed' : 'pending',
        timestamp: a.timestamp,
        details: pay.payment_method || 'Processing',
      });
    } else if (a.tool_name === 'create_refund') {
      txns.push({ id: `ref-${txns.length}`, type: 'Refund', tool: a.tool_name, status: result.error ? 'failed' : 'success', timestamp: a.timestamp, details: 'Refund initiated' });
    } else if (a.tool_name === 'create_payment_link') {
      txns.push({ id: `lnk-${txns.length}`, type: 'Pay Link', tool: a.tool_name, status: result.error ? 'failed' : 'success', timestamp: a.timestamp, details: 'Link generated' });
    }
  }
  return txns.reverse();
}

function fmt(paisa?: number, cur?: string): string {
  if (!paisa) return '';
  return `${cur === 'INR' ? '₹' : cur + ' '}${(paisa / 100).toLocaleString('en-IN')}`;
}

const StatusBadge = ({ status }: { status: string }) => {
  const cfg = {
    success: { icon: CheckCircle2, color: '#34d399', bg: 'rgba(52,211,153,0.1)' },
    failed: { icon: XCircle, color: '#f87171', bg: 'rgba(248,113,113,0.1)' },
    pending: { icon: Clock, color: '#fbbf24', bg: 'rgba(251,191,36,0.1)' },
  }[status] || { icon: Clock, color: '#fbbf24', bg: 'rgba(251,191,36,0.1)' };
  const Icon = cfg.icon;
  return (
    <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-md" style={{ background: cfg.bg }}>
      <Icon size={10} style={{ color: cfg.color }} />
      <span className="text-[10px] font-medium capitalize" style={{ color: cfg.color }}>{status}</span>
    </div>
  );
};

export default function TransactionFeed({ activities }: Props) {
  const txns = extractTransactions(activities);

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <ArrowRightLeft size={13} style={{ color: 'var(--success)' }} />
        <span className="text-xs font-semibold">Transactions</span>
        {txns.length > 0 && (
          <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-md" style={{ background: 'var(--success-glow)', color: 'var(--success)' }}>
            {txns.length}
          </span>
        )}
      </div>
      <div className="max-h-[280px] overflow-y-auto">
        {txns.length === 0 ? (
          <div className="px-4 py-10 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
            Transactions appear as the agent processes them
          </div>
        ) : (
          txns.map((txn, i) => (
            <div
              key={i}
              className="animate-slide-up flex items-center gap-3 px-4 py-2.5"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <div
                className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
                style={{ background: txn.type === 'Refund' ? 'rgba(248,113,113,0.1)' : 'rgba(52,211,153,0.1)' }}
              >
                {txn.type === 'Refund' ? (
                  <ArrowDownLeft size={13} style={{ color: '#f87171' }} />
                ) : (
                  <ArrowUpRight size={13} style={{ color: '#34d399' }} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium">{txn.type}</span>
                  <StatusBadge status={txn.status} />
                </div>
                <div className="text-[10px] mt-0.5 truncate" style={{ color: 'var(--text-muted)' }}>
                  {txn.details}
                </div>
              </div>
              <div className="text-right shrink-0">
                {txn.amount ? (
                  <div className="text-xs font-bold" style={{ color: txn.type === 'Refund' ? '#f87171' : '#34d399' }}>
                    {txn.type === 'Refund' ? '-' : '+'}{fmt(txn.amount, txn.currency)}
                  </div>
                ) : null}
                <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {new Date(txn.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
