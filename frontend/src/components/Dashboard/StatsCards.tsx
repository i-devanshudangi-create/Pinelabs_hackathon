import { ShoppingCart, CreditCard, RotateCcw, Users, Link2, TrendingUp, Zap, Globe } from 'lucide-react';

interface Props {
  stats: Record<string, number>;
}

const CARDS = [
  { key: 'orders', label: 'Orders', icon: ShoppingCart, color: '#fbbf24', gradient: 'linear-gradient(135deg, rgba(251,191,36,0.12), rgba(251,191,36,0.03))' },
  { key: 'payments', label: 'Payments', icon: CreditCard, color: '#34d399', gradient: 'linear-gradient(135deg, rgba(52,211,153,0.12), rgba(52,211,153,0.03))' },
  { key: 'refunds', label: 'Refunds', icon: RotateCcw, color: '#f87171', gradient: 'linear-gradient(135deg, rgba(248,113,113,0.12), rgba(248,113,113,0.03))' },
  { key: 'customers', label: 'Customers', icon: Users, color: '#60a5fa', gradient: 'linear-gradient(135deg, rgba(96,165,250,0.12), rgba(96,165,250,0.03))' },
  { key: 'payment_links', label: 'Pay Links', icon: Link2, color: '#f472b6', gradient: 'linear-gradient(135deg, rgba(244,114,182,0.12), rgba(244,114,182,0.03))' },
  { key: 'subscriptions', label: 'Subscriptions', icon: TrendingUp, color: '#67e8f9', gradient: 'linear-gradient(135deg, rgba(103,232,249,0.12), rgba(103,232,249,0.03))' },
  { key: 'offers', label: 'Offers', icon: Zap, color: '#fb923c', gradient: 'linear-gradient(135deg, rgba(251,146,60,0.12), rgba(251,146,60,0.03))' },
  { key: 'international', label: 'Intl', icon: Globe, color: '#6ee7b7', gradient: 'linear-gradient(135deg, rgba(110,231,183,0.12), rgba(110,231,183,0.03))' },
];

export default function StatsCards({ stats }: Props) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
      {CARDS.map(({ key, label, icon: Icon, color, gradient }) => {
        const value = stats[key] || 0;
        return (
          <div
            key={key}
            style={{
              borderRadius: '14px',
              padding: '14px 16px',
              background: gradient,
              border: `1px solid ${color}15`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '11px', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                {label}
              </span>
              <div style={{ width: '28px', height: '28px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: `${color}18` }}>
                <Icon size={13} style={{ color }} />
              </div>
            </div>
            <div style={{ fontSize: '22px', fontWeight: 700, letterSpacing: '-0.02em', color }}>
              {value}
            </div>
          </div>
        );
      })}
    </div>
  );
}
