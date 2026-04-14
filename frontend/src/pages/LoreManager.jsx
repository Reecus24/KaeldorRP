import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getLore, createLore, updateLore, deleteLore } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Plus, Trash2, Pencil, BookOpen, MapPin, Shield, Package, Calendar } from 'lucide-react';

const categoryIcons = { location: MapPin, faction: Shield, item: Package, event: Calendar, custom: BookOpen };
const defaultForm = { category: 'custom', title: '', content: '', tags: '' };

export default function LoreManager() {
  const { activeCampaign } = useOutletContext();
  const [entries, setEntries] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...defaultForm });
  const [filter, setFilter] = useState('all');

  const load = () => {
    if (!activeCampaign?.id) return;
    getLore(activeCampaign.id).then(r => setEntries(r.data)).catch(() => {});
  };

  useEffect(() => { load(); }, [activeCampaign]);

  const resetForm = () => { setForm({ ...defaultForm }); setEditingId(null); };

  const handleSave = async () => {
    if (!form.title.trim()) { toast.error('Title is required'); return; }
    const payload = { ...form, tags: form.tags.split(',').map(t => t.trim()).filter(Boolean) };
    try {
      if (editingId) {
        await updateLore(editingId, payload);
        toast.success('Lore updated');
      } else {
        await createLore({ ...payload, campaign_id: activeCampaign.id });
        toast.success('Lore entry created');
      }
      resetForm(); setDialogOpen(false); load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this lore entry?')) return;
    await deleteLore(id); toast.success('Deleted'); load();
  };

  const startEdit = (entry) => {
    setForm({ category: entry.category, title: entry.title, content: entry.content, tags: (entry.tags || []).join(', ') });
    setEditingId(entry.id); setDialogOpen(true);
  };

  const filtered = filter === 'all' ? entries : entries.filter(e => e.category === filter);

  if (!activeCampaign) return <div className="p-8 text-zinc-500">Select or create a campaign first.</div>;

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="lore-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>Lore</h1>
          <p className="text-sm text-zinc-500 mt-1">{activeCampaign.name} - {entries.length} entries</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
          <DialogTrigger asChild>
            <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="create-lore-btn">
              <Plus className="w-4 h-4 mr-1.5" /> New Entry
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100 max-w-lg">
            <DialogHeader>
              <DialogTitle style={{ fontFamily: 'Manrope, sans-serif' }}>{editingId ? 'Edit Lore' : 'New Lore Entry'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 mt-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Title *</label>
                  <Input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Entry title"
                    className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="lore-title-input" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Category</label>
                  <Select value={form.category} onValueChange={v => setForm({ ...form, category: v })}>
                    <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="lore-category-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      {['location', 'faction', 'item', 'event', 'custom'].map(c => (
                        <SelectItem key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Content</label>
                <Textarea value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} placeholder="Lore details..."
                  rows={6} className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="lore-content-input" />
              </div>
              <div>
                <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Tags (comma-separated)</label>
                <Input value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} placeholder="e.g. magic, history, ruins"
                  className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="lore-tags-input" />
              </div>
              <Button onClick={handleSave} className="w-full bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="save-lore-btn">
                {editingId ? 'Update' : 'Create'} Entry
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap" data-testid="lore-filters">
        {['all', 'location', 'faction', 'item', 'event', 'custom'].map(cat => (
          <button key={cat} onClick={() => setFilter(cat)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${filter === cat ? 'bg-amber-500/15 text-amber-500 border border-amber-500/20' : 'bg-zinc-900 text-zinc-500 border border-zinc-800 hover:text-zinc-300'}`}
            data-testid={`filter-${cat}`}>
            {cat === 'all' ? 'All' : cat.charAt(0).toUpperCase() + cat.slice(1)}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-md p-8 text-center text-zinc-500">
          {entries.length === 0 ? 'No lore entries yet. Build your world.' : 'No entries match this filter.'}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {filtered.map(entry => {
            const Icon = categoryIcons[entry.category] || BookOpen;
            return (
              <div key={entry.id} className="bg-zinc-900 border border-zinc-800 rounded-md p-4 hover:border-zinc-700 transition-colors" data-testid={`lore-card-${entry.id}`}>
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Icon className="w-4 h-4 text-amber-500/70" />
                    <h3 className="font-semibold text-zinc-100 text-sm">{entry.title}</h3>
                  </div>
                  <div className="flex gap-0.5">
                    <Button variant="ghost" size="sm" onClick={() => startEdit(entry)} className="h-7 w-7 p-0 text-zinc-500 hover:text-zinc-100" data-testid={`edit-lore-${entry.id}`}>
                      <Pencil className="w-3.5 h-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleDelete(entry.id)} className="h-7 w-7 p-0 text-zinc-500 hover:text-red-400" data-testid={`delete-lore-${entry.id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
                <Badge variant="outline" className="text-xs border-zinc-700 text-zinc-400 mb-2">{entry.category}</Badge>
                <p className="text-xs text-zinc-500 line-clamp-3 mb-2">{entry.content}</p>
                {entry.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {entry.tags.map(tag => (
                      <span key={tag} className="px-1.5 py-0.5 text-xs bg-zinc-800 text-zinc-500 rounded">{tag}</span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
