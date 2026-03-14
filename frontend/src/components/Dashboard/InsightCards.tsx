import { AlertTriangle, Info, MessageSquare, Shield, Zap } from 'lucide-react';
import type { ActivityEntry } from '../../lib/types';

interface Props {
  activities: ActivityEntry[];
  onAskAgent?: (message: string) => void;
}

interface Insight {
  severity: 'info' | 'warning' | 'danger';
  title: string;
  message: string;
  action?: string;
}

const SEVERITY_CONFIG = {
  info: { color: '#60a5fa', bg: 'rgba(96,165,250,0.08)', border: 'rgba(96,165,250,0.15)', Icon: Info },
  warning: { color: '#fbbf24', bg: 'rgba(251,191,36,0.08)', border: 'rgba(251,191,36,0.15)', Icon: AlertTriangle },
  danger: { color: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.15)', Icon: Shield },
};

function generateInsights(activities: ActivityEntry[]): Insight[] {
  const insights: Insight[] = [];
  if (activities.length === 0) return insights;

  const results = activities.filter(a => a.event === 'tool_result');
  const calls = activities.filter(a => a.event === 'tool_call');

  const failures = results.filter(a =>
    a.tool_result?.error || a.tool_result?.success === false
  );
  const failureRate = results.length > 0 ? (failures.length / results.length) * 100 : 0;

  if (failureRate > 30) {
    insights.push({
      severity: 'danger',
      title: 'High Failure Rate',
      message: `${failures.length} of ${results.length} API calls failed (${failureRate.toFixed(0)}%). This is above the 30% threshold.`,
      action: 'Investigate recent API failures and suggest fixes.',
    });
  } else if (failureRate > 10) {
    insights.push({
      severity: 'warning',
      title: 'Elevated Failures',
      message: `${failures.length} failures detected (${failureRate.toFixed(0)}% rate).`,
      action: 'What caused the recent failures?',
    });
  }

  const paymentCalls = calls.filter(a => a.tool_name === 'create_payment');
  const methodCounts: Record<string, number> = {};
  for (const c of paymentCalls) {
    const method = c.tool_input?.payment_method || 'UNKNOWN';
    methodCounts[method] = (methodCounts[method] || 0) + 1;
  }
  const topMethod = Object.entries(methodCounts).sort((a, b) => b[1] - a[1])[0];
  if (topMethod) {
    insights.push({
      severity: 'info',
      title: 'Popular Payment Method',
      message: `${topMethod[0]} is the most used method (${topMethod[1]} calls). Consider optimizing checkout for this method.`,
    });
  }

  const orderCalls = calls.filter(a => a.tool_name === 'create_order');
  const paymentResults = results.filter(a => a.tool_name === 'create_payment' && !a.tool_result?.error);
  if (orderCalls.length > paymentResults.length + 1 && orderCalls.length >= 3) {
    const gap = orderCalls.length - paymentResults.length;
    insights.push({
      severity: 'warning',
      title: 'Unpaid Orders',
      message: `${gap} orders created but not paid. Potential cart abandonment.`,
      action: 'Show me the status of my recent orders.',
    });
  }

  if (calls.length > 0) {
    const toolCounts: Record<string, number> = {};
    for (const c of calls) toolCounts[c.tool_name] = (toolCounts[c.tool_name] || 0) + 1;
    const top = Object.entries(toolCounts).sort((a, b) => b[1] - a[1])[0];
    insights.push({
      severity: 'info',
      title: 'Most Active API',
      message: `${top[0].replace(/_/g, ' ')} called ${top[1]} times — your busiest endpoint.`,
    });
  }

  if (calls.length >= 10) {
    const recent5 = calls.slice(-5);
    const older5 = calls.slice(-10, -5);
    if (recent5.length > older5.length * 1.5) {
      insights.push({
        severity: 'info',
        title: 'Volume Spike',
        message: 'API call volume increased significantly in the last batch. Monitor for rate limiting.',
      });
    }
  }

  return insights;
}

export default function InsightCards({ activities, onAskAgent }: Props) {
  const insights = generateInsights(activities);
  if (insights.length === 0) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
        <Zap size={12} style={{ color: '#fbbf24' }} />
        <span style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
          Smart Insights
        </span>
      </div>
      {insights.map((insight, i) => {
        const cfg = SEVERITY_CONFIG[insight.severity];
        const SevIcon = cfg.Icon;
        return (
          <div
            key={i}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: '10px',
              padding: '10px 14px', borderRadius: '10px',
              background: cfg.bg, border: `1px solid ${cfg.border}`,
            }}
          >
            <SevIcon size={14} style={{ color: cfg.color, flexShrink: 0, marginTop: '1px' }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: cfg.color, marginBottom: '2px' }}>
                {insight.title}
              </div>
              <div style={{ fontSize: '11px', lineHeight: 1.4, color: 'var(--text-secondary)' }}>
                {insight.message}
              </div>
            </div>
            {insight.action && onAskAgent && (
              <button
                onClick={() => onAskAgent(insight.action!)}
                style={{
                  display: 'flex', alignItems: 'center', gap: '4px',
                  padding: '4px 10px', borderRadius: '6px', flexShrink: 0,
                  fontSize: '10px', fontWeight: 600, cursor: 'pointer',
                  background: 'var(--bg-card)', border: '1px solid var(--border)',
                  color: 'var(--accent-light)',
                }}
              >
                <MessageSquare size={10} />
                Ask
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
