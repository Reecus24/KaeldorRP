import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getChannels, createChannel, deleteChannel } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { toast } from 'sonner';
import { Plus, Trash2, Radio, Hash } from 'lucide-react';

const modeLabels = { ic: 'In-Character', ooc: 'Out-of-Character', admin: 'Admin' };
const modeColors = { ic: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20', ooc: 'bg-blue-500/15 text-blue-400 border-blue-500/20', admin: 'bg-amber-500/15 text-amber-400 border-amber-500/20' };

export default function ChannelConfig() {
  const { activeCampaign } = useOutletContext();
  const [channels, setChannels] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState({ guild_id: '', channel_id: '', channel_name: '', mode: 'ic' });

  const load = () => {
    if (!activeCampaign?.id) return;
    getChannels(activeCampaign.id).then(r => setChannels(r.data)).catch(() => {});
  };

  useEffect(() => { load(); }, [activeCampaign]);

  const handleSave = async () => {
    if (!form.channel_id.trim()) { toast.error('Channel ID is required'); return; }
    try {
      await createChannel({ ...form, campaign_id: activeCampaign.id });
      toast.success('Channel configured');
      setDialogOpen(false);
      setForm({ guild_id: '', channel_id: '', channel_name: '', mode: 'ic' });
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    }
  };

  const handleDelete = async (id) => {
    await deleteChannel(id); toast.success('Removed'); load();
  };

  if (!activeCampaign) return <div className="p-8 text-zinc-500">Select or create a campaign first.</div>;

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="channels-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>Channels</h1>
          <p className="text-sm text-zinc-500 mt-1">Configure Discord channel modes for {activeCampaign.name}</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="add-channel-btn">
              <Plus className="w-4 h-4 mr-1.5" /> Add Channel
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
            <DialogHeader>
              <DialogTitle style={{ fontFamily: 'Manrope, sans-serif' }}>Configure Channel</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 mt-2">
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Guild (Server) ID</label>
                <Input value={form.guild_id} onChange={e => setForm({ ...form, guild_id: e.target.value })} placeholder="Discord server ID"
                  className="bg-zinc-950 border-zinc-800 text-zinc-100 font-mono text-sm" data-testid="channel-guild-input" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Channel ID *</label>
                <Input value={form.channel_id} onChange={e => setForm({ ...form, channel_id: e.target.value })} placeholder="Discord channel ID"
                  className="bg-zinc-950 border-zinc-800 text-zinc-100 font-mono text-sm" data-testid="channel-id-input" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Channel Name (optional)</label>
                <Input value={form.channel_name} onChange={e => setForm({ ...form, channel_name: e.target.value })} placeholder="#channel-name"
                  className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="channel-name-input" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Mode</label>
                <Select value={form.mode} onValueChange={v => setForm({ ...form, mode: v })}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="channel-mode-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-800">
                    <SelectItem value="ic">In-Character (IC)</SelectItem>
                    <SelectItem value="ooc">Out-of-Character (OOC)</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleSave} className="w-full bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="save-channel-btn">
                Save Channel Config
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-md p-4 text-xs text-zinc-500">
        <Radio className="w-4 h-4 text-amber-500/70 inline mr-2" />
        Channels can also be configured via Discord using <code className="font-mono text-amber-500/80 bg-zinc-800 px-1.5 py-0.5 rounded">/set_channel_mode</code>. Enter channel IDs from Discord (right-click channel &gt; Copy Channel ID).
      </div>

      {channels.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-md p-8 text-center text-zinc-500">
          No channels configured. Add channel modes to control bot behavior.
        </div>
      ) : (
        <div className="grid gap-3">
          {channels.map(ch => (
            <div key={ch.id} className="bg-zinc-900 border border-zinc-800 rounded-md p-4 flex items-center justify-between hover:border-zinc-700 transition-colors" data-testid={`channel-row-${ch.id}`}>
              <div className="flex items-center gap-3">
                <Hash className="w-4 h-4 text-zinc-500" />
                <div>
                  <p className="text-sm font-medium text-zinc-200">{ch.channel_name || ch.channel_id}</p>
                  <p className="text-xs text-zinc-600 font-mono">{ch.channel_id}{ch.guild_id ? ` / ${ch.guild_id}` : ''}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2 py-0.5 text-xs font-medium rounded border ${modeColors[ch.mode] || ''}`}>
                  {modeLabels[ch.mode] || ch.mode}
                </span>
                <Button variant="ghost" size="sm" onClick={() => handleDelete(ch.id)} className="text-zinc-500 hover:text-red-400" data-testid={`delete-channel-${ch.id}`}>
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
