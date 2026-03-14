import { GitCompare, AlertTriangle, XCircle, Clock } from 'lucide-react';
import type { ActivityEntry } from '../../lib/types';

interface Props {
  activities: ActivityEntry[];
}

interface ReconData {
  total_orders: number;
  paid_orders: number;
  unpaid_orders: number;
  settled: number;
  unsettled: number;
  refunded: number;
  mismatches: { order_id?: string; type: string; message: string }[];
  summary: string;
}

function extractReconData(activities: ActivityEntry[]): ReconData | null {
  for (let i = activities.length - 1; i >= 0; i--) {
    const a = activities[i];
    if (a.tool_name === 'reconcile_transactions' && a.event === 'tool_result' && a.tool_result) {
      return a.tool_result as unknown as ReconData;
    }
  }
  return null;
}

const TYPE_CONFIG: Record<string, { color: string; Icon: any }> = {
  PAID_NOT_SETTLED: { color: '#fbbf24', Icon: Clock },
  CREATED_NOT_PAID: { color: '#f87171', Icon: XCircle },
  ERROR: { color: '#f87171', Icon: AlertTriangle },
  SYSTEM_ERROR: { color: '#f87171', Icon: AlertTriangle },
};

export default function ReconciliationMatrix({ activities }: Props) {
  const data = extractReconData(activities);
  if (!data) return null;

  const cells = [
    { label: 'Total Orders', value: data.total_orders, color: '#60a5fa' },
    { label: 'Paid', value: data.paid_orders, color: '#34d399' },
    { label: 'Unpaid', value: data.unpaid_orders, color: '#f87171' },
    { label: 'Settled', value: data.settled, color: '#7c6cf0' },
    { label: 'Unsettled', value: data.unsettled, color: '#fbbf24' },
    { label: 'Refunded', value: data.refunded, color: '#fb923c' },
  ];

  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '12px 16px',
        borderBottom: '1px solid var(--border)',
      }}>
        <GitCompare size={13} style={{ color: '#7c6cf0' }} />
        <span style={{ fontSize: '12px', fontWeight: 600 }}>Reconciliation</span>
        {data.mismatches.length === 0 ? (
          <span style={{ marginLeft: 'auto', fontSize: '10px', fontWeight: 500, padding: '2px 8px', borderRadius: '100px', background: 'rgba(52,211,153,0.12)', color: '#34d399' }}>
            Healthy
          </span>
        ) : (
          <span style={{ marginLeft: 'auto', fontSize: '10px', fontWeight: 500, padding: '2px 8px', borderRadius: '100px', background: 'rgba(248,113,113,0.12)', color: '#f87171' }}>
            {data.mismatches.length} issue{data.mismatches.length > 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div style={{ padding: '14px 16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
          {cells.map((c) => (
            <div key={c.label} style={{
              padding: '10px',
              borderRadius: '10px',
              background: `${c.color}08`,
              border: `1px solid ${c.color}15`,
              textAlign: 'center',
            }}>
              <div style={{ fontSize: '18px', fontWeight: 700, color: c.color }}>{c.value}</div>
              <div style={{ fontSize: '9px', fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: '2px' }}>
                {c.label}
              </div>
            </div>
          ))}
        </div>

        {data.summary && (
          <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '0 0 8px', lineHeight: 1.4 }}>
            {data.summary}
          </p>
        )}

        {data.mismatches.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {data.mismatches.slice(0, 5).map((m, i) => {
              const cfg = TYPE_CONFIG[m.type] || TYPE_CONFIG.ERROR;
              const MIcon = cfg.Icon;
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '8px 10px', borderRadius: '8px',
                  background: `${cfg.color}08`, border: `1px solid ${cfg.color}12`,
                }}>
                  <MIcon size={12} style={{ color: cfg.color, flexShrink: 0 }} />
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{m.message}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
