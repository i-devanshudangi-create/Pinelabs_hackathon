import { useState, useCallback, useEffect, useRef } from 'react';
import { Zap, LayoutDashboard } from 'lucide-react';
import ChatPanel from './components/Chat/ChatPanel';
import DashboardPanel from './components/Dashboard/DashboardPanel';
import { useWebSocket } from './hooks/useWebSocket';
import type { ActivityEntry, WorkflowStep } from './lib/types';
import type { WSMessage } from './hooks/useWebSocket';

export default function App() {
  const chatWS = useWebSocket('/ws/chat');
  const dashWS = useWebSocket('/ws/dashboard');
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([]);
  const [dashboardOpen, setDashboardOpen] = useState(false);
  const [splitPercent, setSplitPercent] = useState(50);
  const dragging = useRef(false);
  const chatPanelRef = useRef<{ injectMessage: (msg: string) => void }>(null);

  const handleToolEvent = useCallback((eventData: any) => {
    const entry: ActivityEntry = {
      event: eventData.tool_result ? 'tool_result' : 'tool_call',
      tool_name: eventData.tool_name,
      tool_input: eventData.tool_input,
      tool_result: eventData.tool_result,
      timestamp: eventData.timestamp || new Date().toISOString(),
    };
    setActivities((prev) => [...prev, entry]);
  }, []);

  const handleWorkflowStep = useCallback((step: WorkflowStep) => {
    setWorkflowSteps((prev) => {
      const existing = prev.findIndex(
        (s) => s.workflow_id === step.workflow_id && s.step_index === step.step_index
      );
      if (existing >= 0) {
        const updated = [...prev];
        updated[existing] = step;
        return updated;
      }
      return [...prev, step];
    });
  }, []);

  const handleAskAgent = useCallback((message: string) => {
    chatPanelRef.current?.injectMessage(message);
  }, []);

  useEffect(() => {
    const unsub = dashWS.addListener((msg: WSMessage) => {
      if (msg.type === 'dashboard_event' && msg.data) {
        if (msg.data.event === 'workflow_step') {
          handleWorkflowStep(msg.data as unknown as WorkflowStep);
        } else {
          setActivities((prev) => [...prev, msg.data as ActivityEntry]);
        }
      }
    });
    return unsub;
  }, [dashWS.addListener, handleWorkflowStep]);

  const onDividerMouseDown = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const pct = (e.clientX / window.innerWidth) * 100;
      setSplitPercent(Math.min(80, Math.max(25, pct)));
    };
    const onMouseUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg-primary)' }}>
      {/* Header */}
      <header
        style={{
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 32px',
          height: '56px',
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--gradient-accent)',
            }}
          >
            <Zap size={16} color="#fff" />
          </div>
          <span style={{ fontWeight: 600, fontSize: '15px', letterSpacing: '-0.01em' }}>PlurAgent</span>
          <span
            style={{
              fontSize: '11px',
              padding: '2px 10px',
              borderRadius: '100px',
              background: 'var(--accent-glow)',
              color: 'var(--accent-light)',
            }}
          >
            v2.0
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div className="animate-pulse-ring" style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)' }} />
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              {chatWS.connected ? 'Live' : 'Connecting...'}
            </span>
          </div>

          <button
            onClick={() => setDashboardOpen((o) => !o)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'all 0.2s',
              background: dashboardOpen ? 'var(--accent-glow)' : 'var(--bg-card)',
              border: `1px solid ${dashboardOpen ? 'var(--accent)' : 'var(--border)'}`,
              color: dashboardOpen ? 'var(--accent-light)' : 'var(--text-secondary)',
            }}
          >
            <LayoutDashboard size={15} />
            Dashboard
          </button>
        </div>
      </header>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* Chat panel */}
        <div style={{ width: dashboardOpen ? `${splitPercent}%` : '100%', height: '100%', transition: dragging.current ? 'none' : 'width 0.3s ease' }}>
          <ChatPanel
            ref={chatPanelRef}
            connected={chatWS.connected}
            sendWS={chatWS.send}
            addListener={chatWS.addListener}
            onToolEvent={handleToolEvent}
            onWorkflowStep={handleWorkflowStep}
          />
        </div>

        {/* Resizable divider */}
        {dashboardOpen && (
          <div
            onMouseDown={onDividerMouseDown}
            style={{
              width: '6px',
              cursor: 'col-resize',
              background: 'var(--border)',
              position: 'relative',
              flexShrink: 0,
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--accent)'; }}
            onMouseLeave={(e) => { if (!dragging.current) (e.currentTarget as HTMLElement).style.background = 'var(--border)'; }}
          >
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                display: 'flex',
                flexDirection: 'column',
                gap: '3px',
              }}
            >
              {[0, 1, 2].map((i) => (
                <div key={i} style={{ width: '3px', height: '3px', borderRadius: '50%', background: 'var(--text-muted)' }} />
              ))}
            </div>
          </div>
        )}

        {/* Dashboard panel */}
        {dashboardOpen && (
          <div style={{ flex: 1, height: '100%', overflow: 'hidden' }}>
            <DashboardPanel
              activities={activities}
              workflowSteps={workflowSteps}
              onAskAgent={handleAskAgent}
            />
          </div>
        )}
      </div>
    </div>
  );
}
