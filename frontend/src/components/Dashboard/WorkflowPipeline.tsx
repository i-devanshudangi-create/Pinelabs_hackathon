import { GitBranch, CheckCircle, XCircle, Loader2, Circle } from 'lucide-react';
import type { WorkflowStep } from '../../lib/types';

interface Props {
  steps: WorkflowStep[];
}

const STATUS_CONFIG = {
  pending: { color: '#44445a', bg: 'rgba(68,68,90,0.15)', Icon: Circle },
  running: { color: '#7c6cf0', bg: 'rgba(124,108,240,0.15)', Icon: Loader2 },
  success: { color: '#34d399', bg: 'rgba(52,211,153,0.12)', Icon: CheckCircle },
  failed: { color: '#f87171', bg: 'rgba(248,113,113,0.12)', Icon: XCircle },
};

export default function WorkflowPipeline({ steps }: Props) {
  if (steps.length === 0) return null;

  const latestByIndex = new Map<number, WorkflowStep>();
  let workflowType = '';
  for (const s of steps) {
    latestByIndex.set(s.step_index, s);
    if (s.workflow_type) workflowType = s.workflow_type;
  }
  const ordered = Array.from(latestByIndex.values()).sort((a, b) => a.step_index - b.step_index);

  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        padding: '12px 16px',
        borderBottom: '1px solid var(--border)',
      }}>
        <GitBranch size={13} style={{ color: '#7c6cf0' }} />
        <span style={{ fontSize: '12px', fontWeight: 600 }}>
          {workflowType === 'checkout' ? 'Checkout Pipeline' :
           workflowType === 'reconciliation' ? 'Reconciliation Flow' : 'Agent Workflow'}
        </span>
        <span style={{
          marginLeft: 'auto', fontSize: '10px', fontWeight: 500,
          padding: '2px 8px', borderRadius: '100px',
          background: ordered.every(s => s.status === 'success') ? 'rgba(52,211,153,0.12)' : 'rgba(124,108,240,0.12)',
          color: ordered.every(s => s.status === 'success') ? '#34d399' : '#7c6cf0',
        }}>
          {ordered.filter(s => s.status === 'success').length}/{ordered.length} done
        </span>
      </div>

      <div style={{ padding: '16px', overflowX: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0', minWidth: 'fit-content' }}>
          {ordered.map((step, i) => {
            const cfg = STATUS_CONFIG[step.status] || STATUS_CONFIG.pending;
            const StatusIcon = cfg.Icon;
            const isLast = i === ordered.length - 1;

            return (
              <div key={step.step_index} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
                  minWidth: '72px',
                }}>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: cfg.bg, border: `2px solid ${cfg.color}`,
                    transition: 'all 0.3s ease',
                    animation: step.status === 'running' ? 'pulse-ring 1.5s infinite' : undefined,
                  }}>
                    <StatusIcon
                      size={14}
                      style={{ color: cfg.color }}
                      className={step.status === 'running' ? 'animate-spin' : ''}
                    />
                  </div>
                  <span style={{
                    fontSize: '9px', fontWeight: 600,
                    color: step.status === 'running' ? cfg.color : 'var(--text-secondary)',
                    textAlign: 'center', maxWidth: '80px',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {step.step_name}
                  </span>
                </div>
                {!isLast && (
                  <div style={{
                    width: '24px', height: '2px', marginBottom: '20px',
                    background: step.status === 'success' ? '#34d399' :
                               step.status === 'failed' ? '#f87171' : 'var(--border)',
                    transition: 'background 0.3s ease',
                  }} />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
