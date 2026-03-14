import { LayoutDashboard, Radio } from 'lucide-react';
import StatsCards from './StatsCards';
import AgentActivityLog from './AgentActivityLog';
import TransactionFeed from './TransactionFeed';
import Charts from './Charts';
import type { ActivityEntry } from '../../lib/types';

interface Props {
  activities: ActivityEntry[];
}

function computeStats(activities: ActivityEntry[]): Record<string, number> {
  const stats: Record<string, number> = {};
  for (const a of activities) {
    if (a.event !== 'tool_call') continue;
    const map: Record<string, string> = {
      create_order: 'orders',
      create_payment: 'payments',
      create_refund: 'refunds',
      create_customer: 'customers',
      create_payment_link: 'payment_links',
      manage_subscription: 'subscriptions',
      discover_offers: 'offers',
      currency_conversion: 'international',
    };
    const key = map[a.tool_name];
    if (key) stats[key] = (stats[key] || 0) + 1;
  }
  return stats;
}

export default function DashboardPanel({ activities }: Props) {
  const stats = computeStats(activities);
  const totalCalls = activities.filter(a => a.event === 'tool_call').length;

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
      {/* Header */}
      <div
        className="flex items-center gap-3 px-6 h-12 shrink-0"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <LayoutDashboard size={15} style={{ color: 'var(--accent-light)' }} />
        <span className="text-sm font-semibold">Dashboard</span>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg" style={{ background: 'var(--accent-glow)' }}>
            <Radio size={10} style={{ color: 'var(--accent-light)' }} />
            <span className="text-[10px] font-medium" style={{ color: 'var(--accent-light)' }}>
              {totalCalls} API calls
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
        <StatsCards stats={stats} />
        <Charts activities={activities} />
        <div className="grid grid-cols-2 gap-2.5">
          <TransactionFeed activities={activities} />
          <AgentActivityLog activities={activities} />
        </div>
      </div>
    </div>
  );
}
