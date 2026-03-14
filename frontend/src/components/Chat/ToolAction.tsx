import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import type { ToolCall } from '../../lib/types';

const TOOL_LABELS: Record<string, string> = {
  generate_token: 'Authenticating',
  create_customer: 'Creating Customer',
  create_order: 'Creating Order',
  get_order_status: 'Checking Order',
  create_payment: 'Processing Payment',
  discover_offers: 'Finding Offers',
  create_refund: 'Processing Refund',
  get_settlements: 'Fetching Settlements',
  create_payment_link: 'Generating Link',
  manage_subscription: 'Managing Subscription',
  calculate_convenience_fee: 'Calculating Fees',
  currency_conversion: 'Converting Currency',
};

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
};

interface Props {
  toolCall: ToolCall;
  pending?: boolean;
}

export default function ToolAction({ toolCall, pending }: Props) {
  const label = TOOL_LABELS[toolCall.tool_name] || toolCall.tool_name;
  const color = TOOL_COLORS[toolCall.tool_name] || '#7c6cf0';
  const hasError = toolCall.tool_result?.error;

  return (
    <div
      className="animate-slide-up flex items-center gap-2.5 rounded-xl px-3 py-2"
      style={{ background: `${color}0a`, border: `1px solid ${color}15` }}
    >
      <div className="shrink-0">
        {pending ? (
          <Loader2 size={13} className="animate-spin" style={{ color }} />
        ) : hasError ? (
          <AlertCircle size={13} style={{ color: 'var(--danger)' }} />
        ) : (
          <CheckCircle size={13} style={{ color }} />
        )}
      </div>
      <span className="text-xs font-medium" style={{ color }}>{label}</span>
      {toolCall.tool_input && Object.keys(toolCall.tool_input).length > 0 && (
        <span className="text-xs truncate ml-auto" style={{ color: 'var(--text-muted)', maxWidth: 180 }}>
          {Object.entries(toolCall.tool_input).slice(0, 2).map(([k, v]) =>
            `${k}: ${typeof v === 'string' ? v.slice(0, 20) : JSON.stringify(v)}`
          ).join(', ')}
        </span>
      )}
    </div>
  );
}
