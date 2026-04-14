import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getBotStatus, getEvents } from '@/lib/api';
import { Swords, Users, ScrollText, Radio, AlertTriangle } from 'lucide-react';

export default function Dashboard() {
  const { activeCampaign } = useOutletContext();
  const [status, setStatus] = useState(null);
  const [recentEvents, setRecentEvents] = useState([]);

  useEffect(() => {
    getBotStatus().then(r => setStatus(r.data)).catch(() => {});
    if (activeCampaign?.id) {
      getEvents(activeCampaign.id, 10).then(r => setRecentEvents(r.data)).catch(() => {});
    }
  }, [activeCampaign]);

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="dashboard-page">
      {/* Campaign Header */}
      <div className="gm-card-header-bg rounded-md p-6 border border-zinc-800" data-testid="campaign-header">
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>
          {activeCampaign?.name || 'No Active Campaign'}
        </h1>
        <p className="text-sm text-zinc-400 mt-2 max-w-2xl leading-relaxed">
          {activeCampaign?.world_summary || 'Create a campaign to get started. Use the Campaigns page or /new_campaign in Discord.'}
        </p>
        {activeCampaign?.tone && (
          <span className="inline-block mt-3 px-2.5 py-0.5 text-xs font-medium bg-amber-500/15 text-amber-500 rounded-md border border-amber-500/20">
            {activeCampaign.tone}
          </span>
        )}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="stats-grid">
        {[
          { label: 'Campaigns', value: status?.campaigns ?? '-', icon: Swords, color: 'text-amber-500' },
          { label: 'NPCs', value: status?.npcs ?? '-', icon: Users, color: 'text-emerald-500' },
          { label: 'Events', value: status?.events ?? '-', icon: ScrollText, color: 'text-blue-500' },
          { label: 'Status', value: 'Online', icon: Radio, color: 'text-emerald-500' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-zinc-900 border border-zinc-800 rounded-md p-4" data-testid={`stat-${label.toLowerCase()}`}>
            <div className="flex items-center justify-between">
              <span className="text-xs text-zinc-500 uppercase tracking-wider">{label}</span>
              <Icon className={`w-4 h-4 ${color}`} />
            </div>
            <p className="text-2xl font-bold text-zinc-100 mt-1">{value}</p>
          </div>
        ))}
      </div>

      {/* Recent Events */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-md" data-testid="recent-events">
        <div className="p-4 border-b border-zinc-800">
          <h2 className="text-lg font-semibold text-zinc-200 tracking-tight" style={{ fontFamily: 'Manrope, sans-serif' }}>Recent Events</h2>
        </div>
        <div className="gm-log-viewer" style={{ maxHeight: '20rem', borderRadius: 0, border: 'none' }}>
          {recentEvents.length === 0 ? (
            <div className="flex items-center gap-2 text-zinc-600">
              <AlertTriangle className="w-4 h-4" />
              <span>No events recorded yet. Start a session via Discord commands.</span>
            </div>
          ) : (
            recentEvents.map((ev, i) => (
              <div key={ev.id || i} className="mb-1">
                <span className="event-type">[{ev.event_type}]</span>{' '}
                <span className="text-zinc-300">{ev.summary}</span>{' '}
                {ev.timestamp && <span className="event-time">{new Date(ev.timestamp).toLocaleTimeString()}</span>}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Quick Info */}
      {!activeCampaign && (
        <div className="bg-zinc-900 border border-amber-500/20 rounded-md p-5" data-testid="setup-guide">
          <h3 className="text-lg font-medium text-amber-500 mb-2" style={{ fontFamily: 'Manrope, sans-serif' }}>Getting Started</h3>
          <ol className="text-sm text-zinc-400 space-y-1.5 list-decimal list-inside">
            <li>Create a campaign from the Campaigns page</li>
            <li>Add NPCs in the NPC Manager</li>
            <li>Configure channel modes for your Discord server</li>
            <li>Set tone and rules for your session</li>
            <li>Use <code className="font-mono text-amber-500/80 bg-zinc-800 px-1.5 py-0.5 rounded text-xs">/gm</code> in Discord to begin</li>
          </ol>
        </div>
      )}
    </div>
  );
}
