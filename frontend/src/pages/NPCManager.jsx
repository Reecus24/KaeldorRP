import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getNPCs, createNPC, updateNPC, deleteNPC } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Plus, Trash2, Pencil, UserCircle } from 'lucide-react';

const defaultNPC = { name: '', role: '', faction: '', personality_traits: '', motivation: '', secrets: '', relationship_notes: '', trust_level: 0, status: 'alive', voice_style: '' };
const statusColors = { alive: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20', wounded: 'bg-amber-500/15 text-amber-400 border-amber-500/20', dead: 'bg-red-500/15 text-red-400 border-red-500/20', missing: 'bg-blue-500/15 text-blue-400 border-blue-500/20', unknown: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20' };

export default function NPCManager() {
  const { activeCampaign } = useOutletContext();
  const [npcs, setNpcs] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...defaultNPC });

  const load = () => {
    if (!activeCampaign?.id) return;
    getNPCs(activeCampaign.id).then(r => setNpcs(r.data)).catch(() => {});
  };

  useEffect(() => { load(); }, [activeCampaign]);

  const resetForm = () => { setForm({ ...defaultNPC }); setEditingId(null); };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('NPC name is required'); return; }
    try {
      if (editingId) {
        await updateNPC(editingId, form);
        toast.success('NPC updated');
      } else {
        await createNPC({ ...form, campaign_id: activeCampaign.id });
        toast.success('NPC created');
      }
      resetForm(); setDialogOpen(false); load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save NPC');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this NPC?')) return;
    await deleteNPC(id); toast.success('NPC deleted'); load();
  };

  const startEdit = (npc) => {
    const { id, campaign_id, created_at, updated_at, ...rest } = npc;
    setForm(rest); setEditingId(id); setDialogOpen(true);
  };

  const updateField = (key, val) => setForm(prev => ({ ...prev, [key]: val }));

  if (!activeCampaign) return <div className="p-8 text-zinc-500">Select or create a campaign first.</div>;

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="npcs-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>NPCs</h1>
          <p className="text-sm text-zinc-500 mt-1">{activeCampaign.name} - {npcs.length} character{npcs.length !== 1 ? 's' : ''}</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
          <DialogTrigger asChild>
            <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="create-npc-btn">
              <Plus className="w-4 h-4 mr-1.5" /> New NPC
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100 max-w-xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle style={{ fontFamily: 'Manrope, sans-serif' }}>{editingId ? 'Edit NPC' : 'New NPC'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 mt-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Name *</label>
                  <Input value={form.name} onChange={e => updateField('name', e.target.value)} placeholder="NPC name"
                    className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-name-input" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Role</label>
                  <Input value={form.role} onChange={e => updateField('role', e.target.value)} placeholder="e.g. Merchant, Guard"
                    className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-role-input" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Faction</label>
                  <Input value={form.faction} onChange={e => updateField('faction', e.target.value)} placeholder="Faction name"
                    className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-faction-input" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Status</label>
                  <Select value={form.status} onValueChange={v => updateField('status', v)}>
                    <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-status-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      {['alive', 'wounded', 'missing', 'dead', 'unknown'].map(s => (
                        <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Personality Traits</label>
                <Input value={form.personality_traits} onChange={e => updateField('personality_traits', e.target.value)} placeholder="e.g. Cunning, distrustful, shrewd"
                  className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-personality-input" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Motivation</label>
                <Textarea value={form.motivation} onChange={e => updateField('motivation', e.target.value)} placeholder="What drives this NPC?"
                  rows={2} className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-motivation-input" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Secrets</label>
                <Textarea value={form.secrets} onChange={e => updateField('secrets', e.target.value)} placeholder="Hidden information..."
                  rows={2} className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-secrets-input" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Relationship Notes</label>
                <Input value={form.relationship_notes} onChange={e => updateField('relationship_notes', e.target.value)} placeholder="Connections to other NPCs/factions"
                  className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-relationships-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Trust Level ({form.trust_level})</label>
                  <input type="range" min="-100" max="100" value={form.trust_level} onChange={e => updateField('trust_level', parseInt(e.target.value))}
                    className="w-full accent-amber-500" data-testid="npc-trust-slider" />
                  <div className="flex justify-between text-xs text-zinc-600"><span>Hostile</span><span>Neutral</span><span>Loyal</span></div>
                </div>
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Voice/Style</label>
                  <Input value={form.voice_style} onChange={e => updateField('voice_style', e.target.value)} placeholder="e.g. Gruff, formal"
                    className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="npc-voice-input" />
                </div>
              </div>
              <Button onClick={handleSave} className="w-full bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="save-npc-btn">
                {editingId ? 'Update' : 'Create'} NPC
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {npcs.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-md p-8 text-center text-zinc-500">
          No NPCs yet. Add characters to populate your world.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {npcs.map(npc => (
            <div key={npc.id} className="bg-zinc-900 border border-zinc-800 rounded-md p-4 hover:border-zinc-700 transition-colors" data-testid={`npc-card-${npc.id}`}>
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <UserCircle className="w-5 h-5 text-zinc-500" />
                  <h3 className="font-semibold text-zinc-100">{npc.name}</h3>
                </div>
                <div className="flex gap-0.5">
                  <Button variant="ghost" size="sm" onClick={() => startEdit(npc)} className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-100" data-testid={`edit-npc-${npc.id}`}>
                    <Pencil className="w-3.5 h-3.5" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(npc.id)} className="h-7 w-7 p-0 text-zinc-500 hover:text-red-400" data-testid={`delete-npc-${npc.id}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {npc.role && <Badge variant="outline" className="text-xs border-zinc-700 text-zinc-400">{npc.role}</Badge>}
                {npc.faction && <Badge variant="outline" className="text-xs border-zinc-700 text-zinc-400">{npc.faction}</Badge>}
                <span className={`px-1.5 py-0.5 text-xs rounded border ${statusColors[npc.status] || statusColors.unknown}`}>{npc.status}</span>
              </div>
              {npc.personality_traits && <p className="text-xs text-zinc-500 line-clamp-2">{npc.personality_traits}</p>}
              <div className="mt-2 flex items-center gap-1.5">
                <span className="text-xs text-zinc-600">Trust:</span>
                <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${npc.trust_level >= 0 ? 'bg-emerald-500' : 'bg-red-500'}`}
                    style={{ width: `${Math.abs(npc.trust_level)}%`, marginLeft: npc.trust_level < 0 ? `${100 - Math.abs(npc.trust_level)}%` : '0' }} />
                </div>
                <span className="text-xs text-zinc-500">{npc.trust_level}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
