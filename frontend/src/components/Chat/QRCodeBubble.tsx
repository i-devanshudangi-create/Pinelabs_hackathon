import { QRCodeSVG } from 'qrcode.react';
import { Copy, Check, ExternalLink } from 'lucide-react';
import { useState } from 'react';

interface Props {
  url: string;
}

export default function QRCodeBubble({ url }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '12px',
        padding: '20px',
        borderRadius: '16px',
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        marginTop: '8px',
      }}
    >
      <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
        Scan to Pay
      </div>
      <div style={{ padding: '12px', borderRadius: '12px', background: '#fff' }}>
        <QRCodeSVG value={url} size={140} level="M" />
      </div>
      <div style={{ display: 'flex', gap: '8px' }}>
        <button
          onClick={handleCopy}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: '8px',
            fontSize: '11px',
            fontWeight: 500,
            cursor: 'pointer',
            background: copied ? 'rgba(52,211,153,0.15)' : 'var(--accent-glow)',
            border: '1px solid var(--border)',
            color: copied ? '#34d399' : 'var(--accent-light)',
          }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy Link'}
        </button>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: '8px',
            fontSize: '11px',
            fontWeight: 500,
            textDecoration: 'none',
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            color: 'var(--text-secondary)',
          }}
        >
          <ExternalLink size={12} />
          Open
        </a>
      </div>
    </div>
  );
}
