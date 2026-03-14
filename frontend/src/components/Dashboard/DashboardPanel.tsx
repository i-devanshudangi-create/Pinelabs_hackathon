import { LayoutDashboard, Radio } from 'lucide-react';
import StatsCards from './StatsCards';
import AgentActivityLog from './AgentActivityLog';
import TransactionFeed from './TransactionFeed';
import Charts from './Charts';
import WorkflowPipeline from './WorkflowPipeline';
import InsightCards from './InsightCards';
import ReconciliationMatrix from './ReconciliationMatrix';
import type { ActivityEntry, WorkflowStep } from '../../lib/types';

interface Props {
  activities: ActivityEntry[];
  workflowSteps: WorkflowStep[];
  onAskAgent?: (message: string) => void;
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

export default function DashboardPanel({ activities, workflowSteps, onAskAgent }: Props) {
  const stats = computeStats(activities);
  const totalCalls = activities.filter(a => a.event === 'tool_call').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--bg-primary)' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '0 20px',
          height: '48px',
          flexShrink: 0,
          borderBottom: '1px solid var(--border)',
        }}
      >
        <LayoutDashboard size={15} style={{ color: 'var(--accent-light)' }} />
        <span style={{ fontSize: '14px', fontWeight: 600 }}>Dashboard</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 10px', borderRadius: '8px', background: 'var(--accent-glow)' }}>
          <Radio size={10} style={{ color: 'var(--accent-light)' }} />
          <span style={{ fontSize: '10px', fontWeight: 500, color: 'var(--accent-light)' }}>
            {totalCalls} API calls
          </span>
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <WorkflowPipeline steps={workflowSteps} />
          <InsightCards activities={activities} onAskAgent={onAskAgent} />
          <StatsCards stats={stats} />
          <Charts activities={activities} />
          <ReconciliationMatrix activities={activities} />
          <TransactionFeed activities={activities} />
          <AgentActivityLog activities={activities} />
        </div>
      </div>
    </div>
  );
}
