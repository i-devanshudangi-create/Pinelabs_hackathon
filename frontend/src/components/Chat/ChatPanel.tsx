import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Sparkles, RotateCcw, CreditCard, Link2, BarChart3, RefreshCw } from 'lucide-react';
import MessageBubble from './MessageBubble';
import ToolAction from './ToolAction';
import type { Message, ToolCall } from '../../lib/types';
import type { WSMessage } from '../../hooks/useWebSocket';

interface Props {
  connected: boolean;
  sendWS: (data: any) => void;
  addListener: (fn: (msg: WSMessage) => void) => () => void;
  onToolEvent: (event: any) => void;
}

const SUGGESTIONS = [
  { text: "Buy a laptop for ₹50,000 — best EMI?", icon: CreditCard },
  { text: "Create a payment link for ₹2,500", icon: Link2 },
  { text: "Show me today's settlement summary", icon: BarChart3 },
  { text: "Set up a monthly subscription of ₹999", icon: RefreshCw },
];

export default function ChatPanel({ sendWS, addListener, onToolEvent }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pendingTools, setPendingTools] = useState<ToolCall[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionId = useRef(`session-${Date.now()}`);

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
        setLoading(false);
        scrollToBottom();
      } else if (msg.type === 'error') {
        setLoading(false);
        setPendingTools([]);
      }
    });
    return unsub;
  }, [addListener, onToolEvent, scrollToBottom]);

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
    setLoading(true);
    setPendingTools([]);
    sendWS({ message: msg, session_id: sessionId.current });
    scrollToBottom();
  };

  const handleClear = () => {
    setMessages([]);
    setPendingTools([]);
    sessionId.current = `session-${Date.now()}`;
  };

  const isEmpty = messages.length === 0 && !loading;

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg-secondary)' }}>
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-full px-8">
            {/* Hero */}
            <div className="animate-float mb-6">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center glow-accent"
                style={{ background: 'var(--gradient-accent)' }}
              >
                <Sparkles size={28} color="#fff" />
              </div>
            </div>
            <h2 className="text-xl font-semibold mb-2 gradient-text">Commerce Assistant</h2>
            <p className="text-sm text-center mb-8 max-w-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
              Autonomously create orders, process payments, discover offers, and manage your Pine Labs commerce — just ask.
            </p>

            {/* Suggestion Grid */}
            <div className="grid grid-cols-2 gap-2.5 w-full max-w-sm">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(s.text)}
                  className="card group flex items-start gap-2.5 p-3.5 text-left cursor-pointer"
                >
                  <div
                    className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mt-0.5 transition-colors"
                    style={{ background: 'var(--accent-glow)' }}
                  >
                    <s.icon size={14} style={{ color: 'var(--accent-light)' }} />
                  </div>
                  <span className="text-xs leading-snug" style={{ color: 'var(--text-secondary)' }}>
                    {s.text}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="px-5 py-4 space-y-4">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {pendingTools.length > 0 && (
              <div className="animate-slide-up flex gap-3">
                <div
                  className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-1"
                  style={{ background: 'var(--accent-glow)', border: '1px solid var(--border)' }}
                >
                  <Loader2 size={14} className="animate-spin" style={{ color: 'var(--accent)' }} />
                </div>
                <div className="flex-1 space-y-1.5">
                  {pendingTools.map((tc, i) => (
                    <ToolAction key={i} toolCall={tc} pending={!tc.tool_result} />
                  ))}
                </div>
              </div>
            )}

            {loading && pendingTools.length === 0 && (
              <div className="animate-fade-in flex gap-3 items-center px-1">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center"
                  style={{ background: 'var(--accent-glow)', border: '1px solid var(--border)' }}
                >
                  <Loader2 size={14} className="animate-spin" style={{ color: 'var(--accent)' }} />
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Thinking</span>
                  <span className="flex gap-0.5">
                    {[0, 1, 2].map(i => (
                      <span
                        key={i}
                        className="w-1 h-1 rounded-full"
                        style={{
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
      <div className="shrink-0 px-4 pb-4 pt-2">
        {!isEmpty && (
          <div className="flex justify-center mb-2">
            <button
              onClick={handleClear}
              className="flex items-center gap-1.5 text-xs px-3 py-1 rounded-full transition-all hover:opacity-80"
              style={{ background: 'var(--bg-card)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              <RotateCcw size={10} />
              Clear chat
            </button>
          </div>
        )}
        <div
          className="flex items-center gap-3 rounded-2xl px-4 py-3 glass-strong"
        >
          <input
            ref={inputRef}
            className="flex-1 bg-transparent border-none outline-none text-sm"
            placeholder={loading ? 'Agent is working...' : 'Ask anything about payments...'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            disabled={loading}
            style={{ color: 'var(--text-primary)' }}
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="w-9 h-9 rounded-xl flex items-center justify-center transition-all disabled:opacity-20"
            style={{ background: input.trim() && !loading ? 'var(--gradient-accent)' : 'var(--bg-card)' }}
          >
            {loading ? (
              <Loader2 size={15} className="animate-spin" style={{ color: 'var(--text-secondary)' }} />
            ) : (
              <Send size={15} style={{ color: input.trim() ? '#fff' : 'var(--text-muted)' }} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
