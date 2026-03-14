import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';
import type { ActivityEntry } from '../../lib/types';

interface Props {
  activities: ActivityEntry[];
}

const COLORS = ['#7c6cf0', '#34d399', '#fbbf24', '#60a5fa', '#fb923c', '#f472b6', '#f87171', '#67e8f9', '#a78bfa', '#6ee7b7'];

const tooltipStyle = {
  contentStyle: {
    background: 'rgba(17,17,25,0.95)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '12px',
    fontSize: 11,
    padding: '8px 12px',
    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
  },
  labelStyle: { color: '#6b6b80' },
  itemStyle: { color: '#f0f0f5' },
};

export default function Charts({ activities }: Props) {
  const toolCounts: Record<string, number> = {};
  const timeline: { time: string; calls: number }[] = [];
  const timeMap: Record<string, number> = {};

  for (const a of activities) {
    if (a.event === 'tool_call') {
      toolCounts[a.tool_name] = (toolCounts[a.tool_name] || 0) + 1;
      const t = new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      timeMap[t] = (timeMap[t] || 0) + 1;
    }
  }

  for (const [time, calls] of Object.entries(timeMap)) {
    timeline.push({ time, calls });
  }

  const pieData = Object.entries(toolCounts)
    .map(([name, value]) => ({ name: name.replace(/_/g, ' '), value }))
    .sort((a, b) => b.value - a.value);

  const barData = Object.entries(toolCounts)
    .map(([name, value]) => ({
      name: name.replace(/_/g, ' ').split(' ').map(w => w[0].toUpperCase() + w.slice(1)).join(' '),
      calls: value,
    }))
    .sort((a, b) => b.calls - a.calls)
    .slice(0, 5);

  if (pieData.length === 0) {
    return (
      <div className="card p-8 text-center">
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Charts populate as the agent works</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 gap-2.5">
      {/* Timeline */}
      <div className="card p-4">
        <h4 className="text-[11px] font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--text-secondary)' }}>
          Activity Timeline
        </h4>
        <ResponsiveContainer width="100%" height={150}>
          <AreaChart data={timeline} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#7c6cf0" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#7c6cf0" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#44445a' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: '#44445a' }} axisLine={false} tickLine={false} />
            <Tooltip {...tooltipStyle} />
            <Area type="monotone" dataKey="calls" stroke="#7c6cf0" strokeWidth={2} fill="url(#areaGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Pie */}
      <div className="card p-4">
        <h4 className="text-[11px] font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--text-secondary)' }}>
          API Distribution
        </h4>
        <ResponsiveContainer width="100%" height={150}>
          <PieChart>
            <Pie data={pieData} cx="50%" cy="50%" innerRadius={35} outerRadius={60} paddingAngle={2} dataKey="value" strokeWidth={0}>
              {pieData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip {...tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Bar */}
      <div className="card p-4">
        <h4 className="text-[11px] font-medium uppercase tracking-wider mb-3" style={{ color: 'var(--text-secondary)' }}>
          Top Calls
        </h4>
        <ResponsiveContainer width="100%" height={150}>
          <BarChart data={barData} layout="vertical" margin={{ left: -10, right: 5, top: 0, bottom: 0 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={90} tick={{ fontSize: 9, fill: '#6b6b80' }} axisLine={false} tickLine={false} />
            <Tooltip {...tooltipStyle} />
            <Bar dataKey="calls" radius={[0, 6, 6, 0]} barSize={12}>
              {barData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
