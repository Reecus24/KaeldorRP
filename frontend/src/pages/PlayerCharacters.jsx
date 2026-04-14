import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getPlayerCharacters, createPlayerCharacter, updatePlayerCharacter, deletePlayerCharacter } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { Plus, Trash2, Pencil, User, Heart, Skull, Eye, EyeOff } from 'lucide-react';

const statusColors = { active: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20', inactive: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/20', missing: 'bg-blue-500/15 text-blue-400 border-blue-500/20', dead: 'bg-red-500/15 text-red-400 border-red-500/20', retired: 'bg-amber-500/15 text-amber-400 border-amber-500/20' };
const defaultPC = { discord_user_id: '', character_name: '', status: 'active', short_description: '', appearance: '', personality_traits: '', background: '', goals: '', fears: '', strengths: '', weaknesses: '', skills: '', injuries_conditions: '', inventory: '', faction_ties: '', relationship_notes: '', gm_secrets: '', public_knowledge: '', private_knowledge: '', current_location: '', reputation: '', obligations_notes: '' };

export default function PlayerCharacters() {
  const { activeCampaign } = useOutletContext();
  const [pcs, setPCs] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...defaultPC });
  const [showSecrets, setShowSecrets] = useState(false);

  const load = () => {
    if (!activeCampaign?.id) return;
    getPlayerCharacters(activeCampaign.id).then(r => setPCs(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, [activeCampaign]);

  const resetForm = () => { setForm({ ...defaultPC }); setEditingId(null); };
  const u = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    if (!form.character_name.trim()) { toast.error('Character name required'); return; }
    try {
      if (editingId) { await updatePlayerCharacter(editingId, form); toast.success('Updated'); }
      else { await createPlayerCharacter({ ...form, campaign_id: activeCampaign.id }); toast.success('Created'); }
      resetForm(); setDialogOpen(false); load();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this character?')) return;
    await deletePlayerCharacter(id); toast.success('Deleted'); load();
  };

  const startEdit = (pc) => {
    const { id, campaign_id, created_at, updated_at, ...rest } = pc;
    setForm(rest); setEditingId(id); setDialogOpen(true);
  };

  if (!activeCampaign) return <div className="p-8 text-zinc-500">Select or create a campaign first.</div>;

  const Field = ({ label, field, textarea, rows = 2 }) => (
    <div>
      <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">{label}</label>
      {textarea ? (
        <Textarea value={form[field]} onChange={e => u(field, e.target.value)} rows={rows} className="bg-zinc-950 border-zinc-800 text-zinc-100 text-sm" data-testid={`pc-${field}-input`} />
      ) : (
        <Input value={form[field]} onChange={e => u(field, e.target.value)} className="bg-zinc-950 border-zinc-800 text-zinc-100 text-sm" data-testid={`pc-${field}-input`} />
      )}
    </div>
  );

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="player-characters-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>Player Characters</h1>
          <p className="text-sm text-zinc-500 mt-1">{activeCampaign.name} - {pcs.length} character{pcs.length !== 1 ? 's' : ''}</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
          <DialogTrigger asChild>
            <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="create-pc-btn">
              <Plus className="w-4 h-4 mr-1.5" /> New Character
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100 max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle style={{ fontFamily: 'Manrope, sans-serif' }}>{editingId ? 'Edit Character' : 'New Character'}</DialogTitle>
            </DialogHeader>
            <Tabs defaultValue="basics" className="mt-2">
              <TabsList className="bg-zinc-800 border border-zinc-700">
                <TabsTrigger value="basics" className="data-[state=active]:bg-zinc-700 text-xs">Basics</TabsTrigger>
                <TabsTrigger value="personality" className="data-[state=active]:bg-zinc-700 text-xs">Personality</TabsTrigger>
                <TabsTrigger value="world" className="data-[state=active]:bg-zinc-700 text-xs">World</TabsTrigger>
                <TabsTrigger value="gm" className="data-[state=active]:bg-zinc-700 text-xs">GM Only</TabsTrigger>
              </TabsList>
              <TabsContent value="basics" className="space-y-3 mt-3">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Character Name *" field="character_name" />
                  <Field label="Discord User ID" field="discord_user_id" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Status</label>
                    <Select value={form.status} onValueChange={v => u('status', v)}>
                      <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="pc-status-select"><SelectValue /></SelectTrigger>
                      <SelectContent className="bg-zinc-900 border-zinc-800">
                        {['active','inactive','missing','dead','retired'].map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <Field label="Current Location" field="current_location" />
                </div>
                <Field label="Short Description" field="short_description" textarea />
                <Field label="Appearance" field="appearance" textarea />
                <Field label="Background" field="background" textarea rows={3} />
              </TabsContent>
              <TabsContent value="personality" className="space-y-3 mt-3">
                <Field label="Personality Traits" field="personality_traits" textarea />
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Strengths" field="strengths" textarea />
                  <Field label="Weaknesses" field="weaknesses" textarea />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Goals" field="goals" textarea />
                  <Field label="Fears" field="fears" textarea />
                </div>
                <Field label="Skills / Competencies" field="skills" textarea />
              </TabsContent>
              <TabsContent value="world" className="space-y-3 mt-3">
                <Field label="Inventory" field="inventory" textarea rows={3} />
                <Field label="Injuries / Conditions" field="injuries_conditions" textarea />
                <Field label="Faction Ties" field="faction_ties" textarea />
                <Field label="Reputation / Standing" field="reputation" textarea />
                <Field label="Relationship Notes" field="relationship_notes" textarea />
                <Field label="Obligations / Debts / Enemies" field="obligations_notes" textarea />
              </TabsContent>
              <TabsContent value="gm" className="space-y-3 mt-3">
                <Field label="GM Secrets (hidden from players)" field="gm_secrets" textarea rows={3} />
                <Field label="Public Knowledge" field="public_knowledge" textarea />
                <Field label="Private Knowledge" field="private_knowledge" textarea />
              </TabsContent>
            </Tabs>
            <Button onClick={handleSave} className="w-full bg-amber-500 hover:bg-amber-600 text-black font-medium mt-3" data-testid="save-pc-btn">
              {editingId ? 'Update' : 'Create'} Character
            </Button>
          </DialogContent>
        </Dialog>
      </div>

      {pcs.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-md p-8 text-center text-zinc-500">
          No player characters yet. Create characters via the dashboard or use /campaign in Discord for guided creation.
        </div>
      ) : (
        <div className="grid gap-4">
          {pcs.map(pc => (
            <div key={pc.id} className="bg-zinc-900 border border-zinc-800 rounded-md p-5 hover:border-zinc-700 transition-colors" data-testid={`pc-card-${pc.id}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <User className="w-5 h-5 text-amber-500" />
                  <div>
                    <h3 className="font-semibold text-zinc-100 text-lg" style={{ fontFamily: 'Manrope, sans-serif' }}>{pc.character_name}</h3>
                    <p className="text-xs text-zinc-600 font-mono">{pc.discord_user_id || 'No Discord ID'}</p>
                  </div>
                  <span className={`px-2 py-0.5 text-xs rounded border ${statusColors[pc.status] || statusColors.active}`}>{pc.status}</span>
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" onClick={() => startEdit(pc)} className="text-zinc-500 hover:text-zinc-100" data-testid={`edit-pc-${pc.id}`}><Pencil className="w-4 h-4" /></Button>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(pc.id)} className="text-zinc-500 hover:text-red-400" data-testid={`delete-pc-${pc.id}`}><Trash2 className="w-4 h-4" /></Button>
                </div>
              </div>
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
                {pc.background && <div><span className="text-zinc-500">Background:</span> <span className="text-zinc-300">{pc.background}</span></div>}
                {pc.personality_traits && <div><span className="text-zinc-500">Personality:</span> <span className="text-zinc-300">{pc.personality_traits}</span></div>}
                {pc.strengths && <div><span className="text-zinc-500">Strengths:</span> <span className="text-zinc-300">{pc.strengths}</span></div>}
                {pc.weaknesses && <div><span className="text-zinc-500">Weaknesses:</span> <span className="text-zinc-300">{pc.weaknesses}</span></div>}
                {pc.inventory && <div><span className="text-zinc-500">Inventory:</span> <span className="text-zinc-300">{pc.inventory}</span></div>}
                {pc.injuries_conditions && <div><span className="text-zinc-500 text-red-400">Injuries:</span> <span className="text-red-300">{pc.injuries_conditions}</span></div>}
                {pc.current_location && <div><span className="text-zinc-500">Location:</span> <span className="text-zinc-300">{pc.current_location}</span></div>}
                {pc.reputation && <div><span className="text-zinc-500">Reputation:</span> <span className="text-zinc-300">{pc.reputation}</span></div>}
                {pc.goals && <div><span className="text-zinc-500">Goals:</span> <span className="text-zinc-300">{pc.goals}</span></div>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
