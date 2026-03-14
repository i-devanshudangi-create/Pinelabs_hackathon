import { Bot, User } from 'lucide-react';
import type { Message } from '../../lib/types';
import ToolAction from './ToolAction';

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={`animate-slide-up flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className="shrink-0 w-8 h-8 rounded-xl flex items-center justify-center mt-0.5"
        style={{
          background: isUser ? 'var(--gradient-accent)' : 'var(--bg-card)',
          border: isUser ? 'none' : '1px solid var(--border)',
        }}
      >
        {isUser ? <User size={14} color="#fff" /> : <Bot size={14} style={{ color: 'var(--accent-light)' }} />}
      </div>

      <div className={`flex-1 max-w-[85%] ${isUser ? 'flex flex-col items-end' : ''}`}>
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mb-2 space-y-1 w-full">
            {message.toolCalls.map((tc, i) => (
              <ToolAction key={i} toolCall={tc} />
            ))}
          </div>
        )}

        {message.content && (
          <div
            className="rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap"
            style={{
              background: isUser ? 'var(--accent)' : 'var(--bg-card)',
              border: isUser ? 'none' : '1px solid var(--border)',
              borderTopRightRadius: isUser ? '6px' : undefined,
              borderTopLeftRadius: !isUser ? '6px' : undefined,
              color: isUser ? '#fff' : 'var(--text-primary)',
              maxWidth: 'fit-content',
            }}
          >
            {message.content}
          </div>
        )}

        <div className="text-xs mt-1.5 px-1" style={{ color: 'var(--text-muted)' }}>
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
    </div>
  );
}
