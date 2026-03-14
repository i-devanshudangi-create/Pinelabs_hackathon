import { useState, useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Send, Loader2, Sparkles, RotateCcw, CreditCard, Link2, BarChart3, RefreshCw, Mic, MicOff, VolumeX, AlertTriangle, Info, Shield, Bell, X } from 'lucide-react';
import MessageBubble from './MessageBubble';
import ToolAction from './ToolAction';
import DecisionPanel from './DecisionPanel';
import { useVoice } from '../../hooks/useVoice';
import type { Message, ToolCall, Decision, WorkflowStep, ProactiveAlert } from '../../lib/types';
import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  connected: boolean;
  sendWS: (data: any) => void;
  addListener: (fn: (msg: WSMessage) => void) => () => void;
  onToolEvent: (event: any) => void;
  onWorkflowStep?: (step: WorkflowStep) => void;
}

const SUGGESTIONS = [
  { text: "Buy a laptop for ₹50,000 — best EMI?", icon: CreditCard },
  { text: "Create a payment link for ₹2,500", icon: Link2 },
  { text: "Show me today's settlement summary", icon: BarChart3 },
  { text: "Set up a monthly subscription of ₹999", icon: RefreshCw },
];

const ALERT_ICONS = { info: Info, warning: AlertTriangle, danger: Shield };
const ALERT_COLORS = {
  info: { color: '#60a5fa', bg: 'rgba(96,165,250,0.08)', border: 'rgba(96,165,250,0.15)' },
  warning: { color: '#fbbf24', bg: 'rgba(251,191,36,0.08)', border: 'rgba(251,191,36,0.15)' },
  danger: { color: '#f87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.15)' },
};

export interface ChatPanelHandle {
  injectMessage: (msg: string) => void;
}

const ChatPanel = forwardRef<ChatPanelHandle, Props>(({ sendWS, addListener, onToolEvent, onWorkflowStep }, ref) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pendingTools, setPendingTools] = useState<ToolCall[]>([]);
  const [pendingDecisions, setPendingDecisions] = useState<Decision[]>([]);
  const [alerts, setAlerts] = useState<ProactiveAlert[]>([]);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sessionId = useRef(`session-${Date.now()}`);

  const voice = useVoice();

  useImperativeHandle(ref, () => ({
    injectMessage: (msg: string) => handleSend(msg),
  }));

  const scrollToBottom = useCallback(() => {
    setTimeout(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }), 50);
  }, []);

  useEffect(() => {
    const unsub = addListener((msg: WSMessage) => {
      if (msg.type === 'tool_call') {
        const tc: ToolCall = { ...msg.data, tool_result: undefined };
        setPendingTools((prev) => [...prev, tc]);
        onToolEvent(msg.data);
        scrollToBottom();
      } else if (msg.type === 'tool_result') {
        setPendingTools((prev) =>
          prev.map((t) =>
            t.tool_name === msg.data.tool_name && !t.tool_result
              ? { ...t, tool_result: msg.data.tool_result }
              : t
          )
        );
        onToolEvent(msg.data);
        scrollToBottom();
      } else if (msg.type === 'decision') {
        setPendingDecisions((prev) => [...prev, msg.data as Decision]);
        scrollToBottom();
      } else if (msg.type === 'workflow_step') {
        onWorkflowStep?.(msg.data as WorkflowStep);
      } else if (msg.type === 'proactive_alert') {
        const incoming = msg.data as ProactiveAlert;
        setAlerts((prev) => {
          const isDuplicate = prev.some(
            (a) => a.title === incoming.title && a.message === incoming.message
          );
          return isDuplicate ? prev : [...prev, incoming];
        });
      } else if (msg.type === 'response') {
        const assistantMsg: Message = {
          id: `msg-${Date.now()}`,
          role: 'assistant',
          content: msg.data.response,
          timestamp: new Date().toISOString(),
          toolCalls: msg.data.tool_calls || [],
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setPendingTools([]);
        setPendingDecisions([]);
        setLoading(false);
        scrollToBottom();
        if (autoSpeak && msg.data.response) {
          voice.speak(msg.data.response);
        }
      } else if (msg.type === 'error') {
        setLoading(false);
        setPendingTools([]);
        setPendingDecisions([]);
      }
    });
    return unsub;
  }, [addListener, onToolEvent, onWorkflowStep, scrollToBottom, autoSpeak, voice]);

  const handleSend = (text?: string) => {
    const msg = text || input.trim();
    if (!msg || loading) return;

    const userMsg: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: msg,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    if (inputRef.current) {
      inputRef.current.style.height = '40px';
      inputRef.current.style.lineHeight = '40px';
      inputRef.current.style.overflowY = 'hidden';
    }
    setLoading(true);
    setPendingTools([]);
    setPendingDecisions([]);
    sendWS({ message: msg, session_id: sessionId.current });
    scrollToBottom();
  };

  const handleClear = () => {
    setMessages([]);
    setPendingTools([]);
    setPendingDecisions([]);
    setAlerts([]);
    sessionId.current = `session-${Date.now()}`;
  };

  const handleMicToggle = () => {
    if (voice.listening) {
      voice.stopListening();
    } else {
      voice.startListening((text) => {
        setInput(text);
        if (inputRef.current) {
          const el = inputRef.current;
          el.style.lineHeight = '1.5';
          el.style.height = 'auto';
          const h = Math.min(el.scrollHeight, 150);
          el.style.height = h + 'px';
          el.style.overflowY = h >= 150 ? 'auto' : 'hidden';
        }
      }, input);
    }
  };

  const isEmpty = messages.length === 0 && !loading;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-primary)', position: 'relative' }}>
      {/* Alerts Bell Button */}
      {alerts.length > 0 && (
        <div style={{ position: 'absolute', top: '12px', left: '16px', zIndex: 50 }}>
          <button
            onClick={() => setAlertsOpen(!alertsOpen)}
            style={{
              position: 'relative',
              width: '40px',
              height: '40px',
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              background: alertsOpen ? 'rgba(96,165,250,0.15)' : 'var(--bg-card)',
              border: `1px solid ${alertsOpen ? 'rgba(96,165,250,0.3)' : 'var(--border)'}`,
              transition: 'all 0.2s',
            }}
          >
            <Bell size={16} style={{ color: alertsOpen ? '#60a5fa' : 'var(--text-muted)' }} />
            <span
              style={{
                position: 'absolute',
                top: '-4px',
                right: '-4px',
                minWidth: '18px',
                height: '18px',
                borderRadius: '9px',
                background: 'var(--gradient-accent)',
                color: '#fff',
                fontSize: '10px',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0 4px',
              }}
            >
              {alerts.length}
            </span>
          </button>

          {/* Alerts Dropdown Panel */}
          {alertsOpen && (
            <div
              style={{
                position: 'absolute',
                top: '48px',
                left: '0',
                width: '360px',
                maxHeight: '420px',
                overflowY: 'auto',
                borderRadius: '16px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                boxShadow: '0 12px 40px rgba(0,0,0,0.4)',
                padding: '0',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 16px',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Proactive Alerts ({alerts.length})
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => { setAlerts([]); setAlertsOpen(false); }}
                    style={{
                      fontSize: '11px', color: 'var(--text-muted)', cursor: 'pointer',
                      background: 'none', border: 'none', padding: '2px 6px',
                    }}
                  >
                    Clear all
                  </button>
                  <button
                    onClick={() => setAlertsOpen(false)}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', background: 'none', border: 'none', padding: '2px',
                    }}
                  >
                    <X size={14} style={{ color: 'var(--text-muted)' }} />
                  </button>
                </div>
              </div>
              <div style={{ padding: '8px' }}>
                {alerts.map((alert, i) => {
                  const cfg = ALERT_COLORS[alert.severity] || ALERT_COLORS.info;
                  const AlertIcon = ALERT_ICONS[alert.severity] || Info;
                  return (
                    <div
                      key={`alert-${i}`}
                      style={{
                        display: 'flex', alignItems: 'flex-start', gap: '10px',
                        padding: '12px', borderRadius: '12px', marginBottom: '4px',
                        background: cfg.bg, border: `1px solid ${cfg.border}`,
                      }}
                    >
                      <AlertIcon size={14} style={{ color: cfg.color, flexShrink: 0, marginTop: '2px' }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: cfg.color, marginBottom: '3px' }}>
                          {alert.title}
                        </div>
                        <div style={{ fontSize: '12px', lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                          {alert.message}
                        </div>
                        {alert.suggested_action && (
                          <button
                            onClick={() => { handleSend(alert.suggested_action); setAlertsOpen(false); }}
                            style={{
                              display: 'inline-flex', alignItems: 'center', gap: '5px',
                              marginTop: '6px', padding: '4px 12px', borderRadius: '6px',
                              fontSize: '11px', fontWeight: 600, cursor: 'pointer',
                              background: 'var(--bg-card)', border: '1px solid var(--border)',
                              color: 'var(--accent-light)',
                            }}
                          >
                            Investigate
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'space-between',
              height: '100%',
              padding: '0 32px',
            }}
          >
            <div style={{ flex: 1 }} />
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div className="animate-float" style={{ marginBottom: '28px' }}>
                <div
                  className="glow-accent"
                  style={{
                    width: '80px',
                    height: '80px',
                    borderRadius: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'var(--gradient-accent)',
                  }}
                >
                  <Sparkles size={36} color="#fff" />
                </div>
              </div>
              <h2
                className="gradient-text"
                style={{ fontSize: '28px', fontWeight: 700, marginBottom: '12px', letterSpacing: '-0.02em' }}
              >
                Commerce Assistant
              </h2>
              <p
                style={{
                  fontSize: '15px',
                  textAlign: 'center',
                  maxWidth: '460px',
                  lineHeight: 1.6,
                  color: 'var(--text-secondary)',
                }}
              >
                Autonomously create orders, process payments, discover offers,
                and manage your Pine Labs commerce — just ask.
              </p>
            </div>
            <div style={{ flex: 1 }} />
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '16px',
                width: '100%',
                maxWidth: '672px',
                paddingBottom: '24px',
              }}
            >
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(s.text)}
                  className="card group cursor-pointer"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '16px',
                    padding: '16px 20px',
                    textAlign: 'left',
                  }}
                >
                  <div
                    style={{
                      flexShrink: 0,
                      width: '42px',
                      height: '42px',
                      borderRadius: '12px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'var(--accent-glow)',
                    }}
                  >
                    <s.icon size={20} style={{ color: 'var(--accent-light)' }} />
                  </div>
                  <span style={{ fontSize: '14px', lineHeight: 1.4, color: 'var(--text-secondary)' }}>
                    {s.text}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div
            style={{
              width: '100%',
              maxWidth: '768px',
              margin: '0 auto',
              padding: '32px 24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '24px',
            }}
          >
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} onSpeak={voice.speak} />
            ))}

            {/* Pending tool actions + decisions */}
            {(pendingTools.length > 0 || pendingDecisions.length > 0) && (
              <div className="animate-slide-up" style={{ display: 'flex', gap: '16px' }}>
                <div
                  style={{
                    flexShrink: 0,
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginTop: '4px',
                    background: 'var(--accent-glow)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <Loader2 size={16} className="animate-spin" style={{ color: 'var(--accent)' }} />
                </div>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {pendingDecisions.map((d, i) => (
                    <DecisionPanel key={`decision-${i}`} decision={d} />
                  ))}
                  {pendingTools.map((tc, i) => (
                    <ToolAction key={i} toolCall={tc} pending={!tc.tool_result} />
                  ))}
                </div>
              </div>
            )}

            {loading && pendingTools.length === 0 && pendingDecisions.length === 0 && (
              <div className="animate-fade-in" style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'var(--accent-glow)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <Loader2 size={16} className="animate-spin" style={{ color: 'var(--accent)' }} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Thinking</span>
                  <span style={{ display: 'flex', gap: '4px' }}>
                    {[0, 1, 2].map(i => (
                      <span
                        key={i}
                        style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          background: 'var(--accent)',
                          animation: `fade-in 0.6s ease-in-out ${i * 0.2}s infinite alternate`,
                        }}
                      />
                    ))}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input Bar */}
      <div
        className="shrink-0"
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--bg-secondary)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          padding: '8px 24px 10px',
        }}
      >
        {!isEmpty && (
          <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
            <button
              onClick={handleClear}
              className="flex items-center gap-2 text-[12px] px-4 py-1.5 rounded-full transition-all hover:opacity-80 cursor-pointer"
              style={{ background: 'var(--bg-card)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              <RotateCcw size={11} />
              Clear chat
            </button>
            <button
              onClick={() => setAutoSpeak(!autoSpeak)}
              className="flex items-center gap-2 text-[12px] px-4 py-1.5 rounded-full transition-all hover:opacity-80 cursor-pointer"
              style={{
                background: autoSpeak ? 'rgba(52,211,153,0.1)' : 'var(--bg-card)',
                color: autoSpeak ? '#34d399' : 'var(--text-muted)',
                border: `1px solid ${autoSpeak ? 'rgba(52,211,153,0.3)' : 'var(--border)'}`,
              }}
            >
              {autoSpeak ? '🔊 Auto-speak ON' : '🔇 Auto-speak'}
            </button>
            {voice.speaking && (
              <button
                onClick={() => voice.stopSpeaking()}
                className="flex items-center gap-2 text-[12px] px-4 py-1.5 rounded-full transition-all hover:opacity-80 cursor-pointer animate-fade-in"
                style={{
                  background: 'rgba(248,113,113,0.1)',
                  color: '#f87171',
                  border: '1px solid rgba(248,113,113,0.3)',
                }}
              >
                <VolumeX size={12} />
                Stop Speaking
              </button>
            )}
          </div>
        )}
        <div
          className="glass-strong"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            borderRadius: '16px',
            padding: '8px 16px',
            width: '100%',
            maxWidth: '672px',
            boxSizing: 'border-box',
          }}
        >
          {/* Mic button */}
          {voice.supported && (
            <button
              onClick={handleMicToggle}
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                cursor: 'pointer',
                background: voice.listening ? 'rgba(248,113,113,0.15)' : 'var(--bg-card)',
                border: `1px solid ${voice.listening ? 'rgba(248,113,113,0.3)' : 'var(--border)'}`,
                animation: voice.listening ? 'pulse-ring 1.5s infinite' : undefined,
              }}
            >
              {voice.listening ? (
                <MicOff size={15} style={{ color: '#f87171' }} />
              ) : (
                <Mic size={15} style={{ color: 'var(--text-muted)' }} />
              )}
            </button>
          )}
          <textarea
            ref={inputRef}
            rows={1}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              fontSize: '14px',
              color: 'var(--text-primary)',
              minWidth: 0,
              resize: 'none',
              lineHeight: '40px',
              maxHeight: '150px',
              overflowY: 'hidden',
              fontFamily: 'inherit',
              padding: 0,
              margin: 0,
              height: '40px',
            }}
            placeholder={loading ? 'Agent is working...' : voice.listening ? 'Listening...' : 'Ask anything about payments...'}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              const el = e.target;
              el.style.lineHeight = '1.5';
              el.style.height = 'auto';
              const h = Math.min(el.scrollHeight, 150);
              el.style.height = h + 'px';
              el.style.overflowY = h >= 150 ? 'auto' : 'hidden';
              if (e.target.value === '') {
                el.style.lineHeight = '40px';
                el.style.height = '40px';
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            disabled={loading}
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="transition-all disabled:opacity-20 cursor-pointer"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              background: input.trim() && !loading ? 'var(--gradient-accent)' : 'var(--bg-card)',
            }}
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" style={{ color: 'var(--text-secondary)' }} />
            ) : (
              <Send size={16} style={{ color: input.trim() ? '#fff' : 'var(--text-muted)' }} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
});

ChatPanel.displayName = 'ChatPanel';
export default ChatPanel;
