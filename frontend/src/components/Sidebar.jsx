import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Users, BookOpen, Shield, Radio, ScrollText, Swords, Settings, Download } from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/campaigns', icon: Swords, label: 'Campaigns' },
  { to: '/npcs', icon: Users, label: 'NPCs' },
  { to: '/lore', icon: BookOpen, label: 'Lore' },
  { to: '/rules', icon: Shield, label: 'Rules & Tone' },
  { to: '/channels', icon: Radio, label: 'Channels' },
  { to: '/logs', icon: ScrollText, label: 'Event Log' },
];

export default function Sidebar() {
  return (
    <aside className="w-64 border-r border-zinc-800 bg-zinc-950 flex flex-col h-screen shrink-0" data-testid="sidebar">
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <Settings className="w-5 h-5 text-amber-500" />
          <h1 className="text-lg font-bold text-zinc-100 tracking-tight" style={{ fontFamily: 'Manrope, sans-serif' }}>
            GM Control
          </h1>
        </div>
        <p className="text-xs text-zinc-500 mt-1">Game Master Dashboard</p>
      </div>
      <nav className="flex-1 p-3 flex flex-col gap-0.5 overflow-y-auto" data-testid="sidebar-nav">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `gm-sidebar-link ${isActive ? 'active' : ''}`}
            data-testid={`nav-${label.toLowerCase().replace(/\s+/g, '-')}`}
          >
            <Icon className="w-4 h-4 shrink-0" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-zinc-800">
        <div className="text-xs text-zinc-600 px-2">
          Discord RP Bot v1.0
        </div>
      </div>
    </aside>
  );
}
