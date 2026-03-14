import { Activity, Wrench, CheckCircle } from 'lucide-react';
import type { ActivityEntry } from '../../lib/types';

interface Props {
  activities: ActivityEntry[];
}

const TOOL_COLORS: Record<string, string> = {
  generate_token: '#7c6cf0',
  create_customer: '#34d399',
  create_order: '#fbbf24',
  get_order_status: '#60a5fa',
  create_payment: '#34d399',
  discover_offers: '#fb923c',
  create_refund: '#f87171',
  get_settlements: '#a78bfa',
  create_payment_link: '#f472b6',
  manage_subscription: '#67e8f9',
  calculate_convenience_fee: '#fcd34d',
  currency_conversion: '#6ee7b7',
  reconcile_transactions: '#60a5fa',
  analyze_activity: '#a78bfa',
};

const TOOL_SHORT: Record<string, string> = {
  generate_token: 'Auth',
  create_customer: 'Customer',
  create_order: 'Order',
  get_order_status: 'Status',
  create_payment: 'Payment',
  discover_offers: 'Offers',
  create_refund: 'Refund',
  get_settlements: 'Settlements',
  create_payment_link: 'Pay Link',
  manage_subscription: 'Subscription',
  calculate_convenience_fee: 'Fees',
  currency_conversion: 'FX',
  reconcile_transactions: 'Recon',
  analyze_activity: 'Analyze',
};

export default function AgentActivityLog({ activities }: Props) {
  const recent = activities.slice(-30).reverse();

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <Activity size={13} style={{ color: 'var(--accent)' }} />
        <span className="text-xs font-semibold">Agent Activity</span>
        <div className="ml-auto flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full animate-pulse-ring" style={{ background: 'var(--success)' }} />
          <span className="text-[10px] font-medium" style={{ color: 'var(--success)' }}>Live</span>
        </div>
      </div>
      <div>
        {recent.length === 0 ? (
          <div className="px-4 py-10 text-center text-xs" style={{ color: 'var(--text-muted)' }}>
            Start chatting to see agent activity
          </div>
        ) : (
          recent.map((entry, i) => {
            const color = TOOL_COLORS[entry.tool_name] || '#7c6cf0';
            const isCall = entry.event === 'tool_call';
            const label = TOOL_SHORT[entry.tool_name] || entry.tool_name;
            return (
              <div
                key={i}
                className="animate-slide-up flex items-center gap-2.5 px-4 py-2"
                style={{
                  borderBottom: '1px solid var(--border)',
                  background: i === 0 ? `${color}06` : undefined,
                }}
              >
                <div className="shrink-0">
                  {isCall ? (
                    <Wrench size={11} style={{ color }} />
                  ) : (
                    <CheckCircle size={11} style={{ color }} />
                  )}
                </div>
                <div
                  className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                  style={{ background: `${color}12`, color }}
                >
                  {label}
                </div>
                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                  {isCall ? 'called' : 'done'}
                </span>
                <span className="ml-auto text-[10px] tabular-nums" style={{ color: 'var(--text-muted)' }}>
                  {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
