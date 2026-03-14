import { Bot, User, Volume2 } from 'lucide-react';
import type { Message } from '../../lib/types';
import ToolAction from './ToolAction';
import QRCodeBubble from './QRCodeBubble';

interface Props {
  message: Message;
  onSpeak?: (text: string) => void;
}

function extractPaymentLink(message: Message): string | null {
  if (message.toolCalls) {
    for (const tc of message.toolCalls) {
      if (tc.tool_name === 'create_payment_link' && tc.tool_result) {
        const result = tc.tool_result;
        const url = result.payment_url || result.payment_link_url
                    || result.data?.payment_url || result.data?.payment_link_url
                    || result.url || result.data?.url
                    || result.link || result.data?.link;
        if (url && typeof url === 'string' && url.startsWith('http')) return url;
      }
    }
  }
  if (message.content) {
    const urlMatch = message.content.match(/https?:\/\/[^\s)<]+(?:payment|pay|checkout|plural)[^\s)<]*/i);
    if (urlMatch) return urlMatch[0];
  }
  return null;
}

export default function MessageBubble({ message, onSpeak }: Props) {
  const isUser = message.role === 'user';
  const paymentLink = !isUser ? extractPaymentLink(message) : null;

  return (
    <div
      className="animate-slide-up"
      style={{
        display: 'flex',
        gap: '16px',
        flexDirection: isUser ? 'row-reverse' : 'row',
      }}
    >
      <div
        style={{
          flexShrink: 0,
          width: '36px',
          height: '36px',
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginTop: '2px',
          background: isUser ? 'var(--gradient-accent)' : 'var(--bg-card)',
          border: isUser ? 'none' : '1px solid var(--border)',
        }}
      >
        {isUser ? <User size={16} color="#fff" /> : <Bot size={16} style={{ color: 'var(--accent-light)' }} />}
      </div>

      <div
        style={{
          flex: 1,
          maxWidth: '85%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: isUser ? 'flex-end' : 'flex-start',
        }}
      >
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div style={{ marginBottom: '12px', width: '100%', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {message.toolCalls.map((tc, i) => (
              <ToolAction key={i} toolCall={tc} />
            ))}
          </div>
        )}

        {message.content && (
          <div
            style={{
              borderRadius: '16px',
              padding: '14px 20px',
              fontSize: '14px',
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              background: isUser ? 'var(--accent)' : 'var(--bg-card)',
              border: isUser ? 'none' : '1px solid var(--border)',
              borderTopRightRadius: isUser ? '6px' : '16px',
              borderTopLeftRadius: isUser ? '16px' : '6px',
              color: isUser ? '#fff' : 'var(--text-primary)',
              maxWidth: 'fit-content',
            }}
          >
            {message.content}
          </div>
        )}

        {paymentLink && <QRCodeBubble url={paymentLink} />}

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px', paddingLeft: '4px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          {!isUser && onSpeak && message.content && (
            <button
              onClick={() => onSpeak(message.content)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '22px', height: '22px', borderRadius: '6px',
                cursor: 'pointer',
                background: 'var(--bg-card)', border: '1px solid var(--border)',
              }}
              title="Read aloud"
            >
              <Volume2 size={11} style={{ color: 'var(--text-muted)' }} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
