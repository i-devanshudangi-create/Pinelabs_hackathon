import { useState } from 'react';
import { Brain, ChevronDown, ChevronUp, CheckCircle, XCircle, Zap } from 'lucide-react';
import type { Decision } from '../../lib/types';

interface Props {
  decision: Decision;
}

const CONFIDENCE_COLORS = {
  high: '#34d399',
  medium: '#fbbf24',
  low: '#f87171',
};

export default function DecisionPanel({ decision }: Props) {
  const [expanded, setExpanded] = useState(false);
  const confColor = CONFIDENCE_COLORS[decision.confidence] || CONFIDENCE_COLORS.medium;

  return (
    <div
      className="animate-slide-up"
      style={{
        borderRadius: '12px',
        overflow: 'hidden',
        background: 'rgba(124, 108, 240, 0.04)',
        border: '1px solid rgba(124, 108, 240, 0.12)',
      }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          width: '100%',
          padding: '10px 14px',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          textAlign: 'left',
        }}
      >
        <Brain size={14} style={{ color: '#7c6cf0', flexShrink: 0 }} />
        <span style={{ fontSize: '12px', fontWeight: 600, color: '#7c6cf0', flex: 1 }}>
          {decision.title}
        </span>
        <span style={{
          fontSize: '10px',
          fontWeight: 600,
          padding: '2px 8px',
          borderRadius: '100px',
          background: `${confColor}18`,
          color: confColor,
          textTransform: 'uppercase',
        }}>
          {decision.confidence}
        </span>
        {expanded ? <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />}
      </button>

      {expanded && (
        <div style={{ padding: '0 14px 12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {decision.reasoning && (
            <p style={{ fontSize: '12px', lineHeight: 1.5, color: 'var(--text-secondary)', margin: 0 }}>
              {decision.reasoning}
            </p>
          )}

          {decision.chosen && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 12px',
              borderRadius: '8px',
              background: 'rgba(52, 211, 153, 0.08)',
              border: '1px solid rgba(52, 211, 153, 0.15)',
            }}>
              <Zap size={12} style={{ color: '#34d399' }} />
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#34d399' }}>
                Chosen: {decision.chosen}
              </span>
            </div>
          )}

          {decision.options_considered.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {decision.options_considered.map((opt, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0' }}>
                  {opt.option === decision.chosen ? (
                    <CheckCircle size={11} style={{ color: '#34d399', flexShrink: 0 }} />
                  ) : (
                    <XCircle size={11} style={{ color: '#f87171', flexShrink: 0 }} />
                  )}
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                    <strong>{opt.option}</strong>: {opt.verdict}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
