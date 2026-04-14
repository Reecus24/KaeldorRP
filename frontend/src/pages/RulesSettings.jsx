import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getRules, updateRules, updateCampaign } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { toast } from 'sonner';
import { Save, Shield } from 'lucide-react';

export default function RulesSettings() {
  const { activeCampaign, refreshCampaigns } = useOutletContext();
  const [rules, setRules] = useState(null);
  const [tone, setTone] = useState('realistic');
  const [saving, setSaving] = useState(false);

  const load = () => {
    if (!activeCampaign?.id) return;
    setTone(activeCampaign.tone || 'realistic');
    getRules(activeCampaign.id).then(r => setRules(r.data)).catch(() => {});
  };

  useEffect(() => { load(); }, [activeCampaign]);

  const handleSaveTone = async () => {
    setSaving(true);
    try {
      await updateCampaign(activeCampaign.id, { tone });
      toast.success('Tone updated');
      refreshCampaigns();
    } catch (e) {
      toast.error('Failed to update tone');
    }
    setSaving(false);
  };

  const handleSaveRules = async () => {
    if (!rules?.id) { toast.error('No rules found for this campaign'); return; }
    setSaving(true);
    try {
      await updateRules(rules.id, {
        content: rules.content,
        dice_system: rules.dice_system,
        critical_enabled: rules.critical_enabled,
        hidden_rolls_enabled: rules.hidden_rolls_enabled,
        difficulty_classes: rules.difficulty_classes,
      });
      toast.success('Rules saved');
    } catch (e) {
      toast.error('Failed to save rules');
    }
    setSaving(false);
  };

  if (!activeCampaign) return <div className="p-8 text-zinc-500">Select or create a campaign first.</div>;

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="rules-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>Rules & Tone</h1>
        <p className="text-sm text-zinc-500 mt-1">{activeCampaign.name} - Configure session rules</p>
      </div>

      {/* Tone Section */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-md p-5" data-testid="tone-section">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-4 h-4 text-amber-500" />
          <h2 className="text-lg font-semibold text-zinc-200" style={{ fontFamily: 'Manrope, sans-serif' }}>Narration Tone</h2>
        </div>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Active Tone</label>
            <Select value={tone} onValueChange={setTone}>
              <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="tone-select">
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
          <Button onClick={handleSaveTone} disabled={saving} className="bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="save-tone-btn">
            <Save className="w-4 h-4 mr-1.5" /> Save
          </Button>
        </div>
        <div className="mt-3 text-xs text-zinc-500">
          {tone === 'grimdark' && 'Harsh, unforgiving, morally grey. Suffering is common. Hope is rare.'}
          {tone === 'realistic' && 'Logical cause and effect. No dramatic conveniences. Grounded in reality.'}
          {tone === 'heroic' && 'Courage is rewarded. Grand moments are possible. Stakes remain real.'}
          {tone === 'mysterious' && 'The unknown, the uncanny. Hints more than reveals. Wonder and unease.'}
        </div>
      </div>

      {/* Rules Section */}
      {rules && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-md p-5 space-y-4" data-testid="rules-section">
          <h2 className="text-lg font-semibold text-zinc-200" style={{ fontFamily: 'Manrope, sans-serif' }}>Game Rules</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Dice System</label>
              <Select value={rules.dice_system} onValueChange={v => setRules({ ...rules, dice_system: v })}>
                <SelectTrigger className="bg-zinc-950 border-zinc-800 text-zinc-100" data-testid="dice-system-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-zinc-900 border-zinc-800">
                  <SelectItem value="narrative">Narrative (lightweight)</SelectItem>
                  <SelectItem value="d20">D20 System</SelectItem>
                  <SelectItem value="custom">Custom</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Difficulty Classes</label>
              <Input value={rules.difficulty_classes} onChange={e => setRules({ ...rules, difficulty_classes: e.target.value })}
                className="bg-zinc-950 border-zinc-800 text-zinc-100 font-mono text-xs" data-testid="difficulty-classes-input" />
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Switch checked={rules.critical_enabled} onCheckedChange={v => setRules({ ...rules, critical_enabled: v })} data-testid="critical-toggle" />
              <label className="text-sm text-zinc-300">Critical Success/Failure</label>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={rules.hidden_rolls_enabled} onCheckedChange={v => setRules({ ...rules, hidden_rolls_enabled: v })} data-testid="hidden-rolls-toggle" />
              <label className="text-sm text-zinc-300">Hidden GM Rolls</label>
            </div>
          </div>

          <div>
            <label className="text-xs text-zinc-400 uppercase tracking-wider mb-1 block">Custom Rules</label>
            <Textarea value={rules.content} onChange={e => setRules({ ...rules, content: e.target.value })} rows={6}
              placeholder="Add any custom rules, house rules, or system-specific rules here..."
              className="bg-zinc-950 border-zinc-800 text-zinc-100 font-mono text-sm" data-testid="custom-rules-input" />
          </div>

          <Button onClick={handleSaveRules} disabled={saving} className="bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="save-rules-btn">
            <Save className="w-4 h-4 mr-1.5" /> Save Rules
          </Button>
        </div>
      )}
    </div>
  );
}
