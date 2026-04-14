import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getCampaigns, createCampaign, updateCampaign, deleteCampaign, exportCampaign, importCampaign } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { Plus, Trash2, Download, Upload, Star, Pencil } from 'lucide-react';

export default function CampaignManager() {
  const { campaigns, refreshCampaigns, activeCampaign } = useOutletContext();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ name: '', world_summary: '', tone: 'realistic' });

  const resetForm = () => { setForm({ name: '', world_summary: '', tone: 'realistic' }); setEditingId(null); };

  const handleSave = async () => {
    if (!form.name.trim()) { toast.error('Campaign name is required'); return; }
    try {
      if (editingId) {
        await updateCampaign(editingId, form);
        toast.success('Campaign updated');
      } else {
        await createCampaign(form);
        toast.success('Campaign created');
      }
      resetForm();
      setDialogOpen(false);
      refreshCampaigns();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this campaign and all related data?')) return;
    try {
      await deleteCampaign(id);
      toast.success('Campaign deleted');
      refreshCampaigns();
    } catch (e) {
      toast.error('Failed to delete');
    }
  };

  const handleSetActive = async (id) => {
    try {
      await updateCampaign(id, { is_active: true });
      toast.success('Campaign activated');
      refreshCampaigns();
    } catch (e) {
      toast.error('Failed to activate');
    }
  };

  const handleExport = async (id) => {
    try {
      const { data } = await exportCampaign(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `campaign-${id}.json`; a.click();
      URL.revokeObjectURL(url);
      toast.success('Campaign exported');
    } catch (e) {
      toast.error('Export failed');
    }
  };

  const handleImport = async () => {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.json';
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const text = await file.text();
      try {
        const data = JSON.parse(text);
        await importCampaign(data);
        toast.success('Campaign imported');
        refreshCampaigns();
      } catch (err) {
        toast.error('Import failed: invalid JSON');
      }
    };
    input.click();
  };

  const startEdit = (c) => {
    setForm({ name: c.name, world_summary: c.world_summary || '', tone: c.tone || 'realistic' });
    setEditingId(c.id);
    setDialogOpen(true);
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="campaigns-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>Campaigns</h1>
          <p className="text-sm text-zinc-500 mt-1">Manage your campaign worlds</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleImport} className="border-zinc-700 text-zinc-300 hover:text-zinc-100" data-testid="import-campaign-btn">
            <Upload className="w-4 h-4 mr-1.5" /> Import
          </Button>
          <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
            <DialogTrigger asChild>
              <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="create-campaign-btn">
                <Plus className="w-4 h-4 mr-1.5" /> New Campaign
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-zinc-900 border-zinc-800 text-zinc-100">
              <DialogHeader>
                <DialogTitle className="text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>
                  {editingId ? 'Edit Campaign' : 'New Campaign'}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4 mt-2">
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Name</label>
                  <Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Campaign name"
                    className="bg-zinc-950 border-zinc-800 text-zinc-100 placeholder:text-zinc-600 focus:ring-amber-500/50" data-testid="campaign-name-input" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">World Summary</label>
                  <Textarea value={form.world_summary} onChange={e => setForm({ ...form, world_summary: e.target.value })} placeholder="Describe the world..."
                    rows={4} className="bg-zinc-950 border-zinc-800 text-zinc-100 placeholder:text-zinc-600 focus:ring-amber-500/50" data-testid="campaign-world-input" />
                </div>
                <div>
                  <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Tone</label>
                  <Select value={form.tone} onValueChange={v => setForm({ ...form, tone: v })}>
                    <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="campaign-tone-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-800">
                      <SelectItem value="realistic">Realistic</SelectItem>
                      <SelectItem value="grimdark">Grimdark</SelectItem>
                      <SelectItem value="heroic">Heroic</SelectItem>
                      <SelectItem value="mysterious">Mysterious</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button onClick={handleSave} className="w-full bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="save-campaign-btn">
                  {editingId ? 'Update' : 'Create'} Campaign
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {campaigns.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-md p-8 text-center">
          <p className="text-zinc-500">No campaigns yet. Create your first campaign to begin.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {campaigns.map(c => (
            <div key={c.id} className={`bg-zinc-900 border rounded-md p-4 transition-colors ${c.is_active ? 'border-amber-500/40' : 'border-zinc-800 hover:border-zinc-700'}`} data-testid={`campaign-card-${c.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-zinc-100 truncate" style={{ fontFamily: 'Manrope, sans-serif' }}>{c.name}</h3>
                    {c.is_active && (
                      <span className="px-2 py-0.5 text-xs font-medium bg-amber-500/15 text-amber-500 rounded border border-amber-500/20">ACTIVE</span>
                    )}
                    <span className="px-2 py-0.5 text-xs bg-zinc-800 text-zinc-400 rounded">{c.tone}</span>
                  </div>
                  <p className="text-sm text-zinc-500 mt-1 line-clamp-2">{c.world_summary || 'No world description'}</p>
                  <p className="text-xs text-zinc-600 mt-2">Created: {new Date(c.created_at).toLocaleDateString()}</p>
                </div>
                <div className="flex items-center gap-1 ml-4 shrink-0">
                  {!c.is_active && (
                    <Button variant="ghost" size="sm" onClick={() => handleSetActive(c.id)} className="text-zinc-400 hover:text-amber-500" data-testid={`activate-campaign-${c.id}`}>
                      <Star className="w-4 h-4" />
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => startEdit(c)} className="text-zinc-400 hover:text-zinc-100" data-testid={`edit-campaign-${c.id}`}>
                    <Pencil className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleExport(c.id)} className="text-zinc-400 hover:text-blue-400" data-testid={`export-campaign-${c.id}`}>
                    <Download className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => handleDelete(c.id)} className="text-zinc-400 hover:text-red-400" data-testid={`delete-campaign-${c.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
