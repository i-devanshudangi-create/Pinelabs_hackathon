import { useState, useCallback, useEffect } from 'react';
import { Zap, LayoutDashboard, X } from 'lucide-react';
import ChatPanel from './components/Chat/ChatPanel';
import DashboardPanel from './components/Dashboard/DashboardPanel';
import { useWebSocket } from './hooks/useWebSocket';
import type { ActivityEntry } from './lib/types';
import type { WSMessage } from './hooks/useWebSocket';

export default function App() {
  const chatWS = useWebSocket('/ws/chat');
  const dashWS = useWebSocket('/ws/dashboard');
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [dashboardOpen, setDashboardOpen] = useState(false);

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

  useEffect(() => {
    const unsub = dashWS.addListener((msg: WSMessage) => {
      if (msg.type === 'dashboard_event' && msg.data) {
        setActivities((prev) => [...prev, msg.data as ActivityEntry]);
      }
    });
    return unsub;
  }, [dashWS.addListener]);

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* Top Bar */}
      <header
        className="shrink-0 flex items-center justify-between px-6 h-12"
        style={{ background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: 'var(--gradient-accent)' }}
          >
            <Zap size={14} color="#fff" />
          </div>
          <span className="font-semibold text-sm tracking-tight">PlurAgent</span>
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{ background: 'var(--accent-glow)', color: 'var(--accent-light)' }}
          >
            v1.0
          </span>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full animate-pulse-ring" style={{ background: 'var(--success)' }} />
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
              {chatWS.connected ? 'Live' : 'Connecting...'}
            </span>
          </div>

          <button
            onClick={() => setDashboardOpen((o) => !o)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 cursor-pointer"
            style={{
              background: dashboardOpen ? 'var(--accent-glow)' : 'var(--bg-card)',
              border: `1px solid ${dashboardOpen ? 'var(--accent)' : 'var(--border)'}`,
              color: dashboardOpen ? 'var(--accent-light)' : 'var(--text-secondary)',
            }}
          >
            <LayoutDashboard size={14} />
            Dashboard
          </button>
        </div>
      </header>

      {/* Full-width Chat */}
      <div className="flex-1 min-h-0">
        <ChatPanel
          connected={chatWS.connected}
          sendWS={chatWS.send}
          addListener={chatWS.addListener}
          onToolEvent={handleToolEvent}
        />
      </div>

      {/* Dashboard Drawer Backdrop */}
      <div
        className={`drawer-backdrop ${dashboardOpen ? 'open' : ''}`}
        onClick={() => setDashboardOpen(false)}
      />

      {/* Dashboard Drawer */}
      <div className={`drawer-panel ${dashboardOpen ? 'open' : ''}`}>
        <div
          className="flex items-center justify-between px-5 h-12 shrink-0"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <LayoutDashboard size={15} style={{ color: 'var(--accent-light)' }} />
            <span className="font-semibold text-sm">Dashboard</span>
          </div>
          <button
            onClick={() => setDashboardOpen(false)}
            className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors cursor-pointer"
            style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          >
            <X size={14} />
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto">
          <DashboardPanel activities={activities} />
        </div>
      </div>
    </div>
  );
}
