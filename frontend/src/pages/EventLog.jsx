import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getEvents, getRecaps, gmGenerateRecap } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { ScrollText, RefreshCw, BookOpen, Loader2 } from 'lucide-react';

export default function EventLog() {
  const { activeCampaign } = useOutletContext();
  const [events, setEvents] = useState([]);
  const [recaps, setRecaps] = useState([]);
  const [generating, setGenerating] = useState(false);

  const loadEvents = () => {
    if (!activeCampaign?.id) return;
    getEvents(activeCampaign.id, 100).then(r => setEvents(r.data)).catch(() => {});
  };

  const loadRecaps = () => {
    if (!activeCampaign?.id) return;
    getRecaps(activeCampaign.id).then(r => setRecaps(r.data)).catch(() => {});
  };

  useEffect(() => { loadEvents(); loadRecaps(); }, [activeCampaign]);

  const handleGenerateRecap = async () => {
    setGenerating(true);
    try {
      const { data } = await gmGenerateRecap({ campaign_id: activeCampaign.id });
      toast.success('Recap generated');
      loadRecaps();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to generate recap');
    }
    setGenerating(false);
  };

  if (!activeCampaign) return <div className="p-8 text-zinc-500">Select or create a campaign first.</div>;

  const eventTypeColors = {
    action: 'text-amber-500',
    consequence: 'text-red-400',
    roll: 'text-blue-400',
    npc_interaction: 'text-emerald-400',
    scene_change: 'text-violet-400',
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="logs-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>Event Log</h1>
        <p className="text-sm text-zinc-500 mt-1">{activeCampaign.name} - Session history</p>
      </div>

      <Tabs defaultValue="journal" className="space-y-4">
        <TabsList className="bg-zinc-900 border border-zinc-800">
          <TabsTrigger value="journal" className="data-[state=active]:bg-zinc-800 data-[state=active]:text-amber-500" data-testid="tab-journal">
            <ScrollText className="w-4 h-4 mr-1.5" /> Journal
          </TabsTrigger>
          <TabsTrigger value="recaps" className="data-[state=active]:bg-zinc-800 data-[state=active]:text-amber-500" data-testid="tab-recaps">
            <BookOpen className="w-4 h-4 mr-1.5" /> Recaps
          </TabsTrigger>
        </TabsList>

        <TabsContent value="journal">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-zinc-500">{events.length} events recorded</span>
            <Button variant="outline" size="sm" onClick={loadEvents} className="border-zinc-700 text-zinc-400 hover:text-zinc-100" data-testid="refresh-events-btn">
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Refresh
            </Button>
          </div>
          <div className="gm-log-viewer" style={{ maxHeight: '32rem' }} data-testid="event-log-viewer">
            {events.length === 0 ? (
              <span className="text-zinc-600">No events. Start a session in Discord to see activity here.</span>
            ) : (
              events.map((ev, i) => (
                <div key={ev.id || i} className="mb-1.5 pb-1.5 border-b border-zinc-900/50 last:border-0">
                  <span className={`font-medium ${eventTypeColors[ev.event_type] || 'text-zinc-400'}`}>[{ev.event_type}]</span>{' '}
                  <span className="text-zinc-300">{ev.summary}</span>
                  {ev.timestamp && (
                    <span className="text-zinc-600 ml-2">{new Date(ev.timestamp).toLocaleString()}</span>
                  )}
                  {ev.details && (
                    <div className="text-zinc-500 mt-0.5 pl-4 text-xs leading-relaxed">{ev.details.slice(0, 200)}{ev.details.length > 200 ? '...' : ''}</div>
                  )}
                </div>
              ))
            )}
          </div>
        </TabsContent>

        <TabsContent value="recaps">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs text-zinc-500">{recaps.length} recaps</span>
            <Button size="sm" onClick={handleGenerateRecap} disabled={generating} className="bg-amber-500 hover:bg-amber-600 text-black font-medium" data-testid="generate-recap-btn">
              {generating ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
              Generate Recap
            </Button>
          </div>
          {recaps.length === 0 ? (
            <div className="bg-zinc-900 border border-zinc-800 rounded-md p-8 text-center text-zinc-500">
              No recaps yet. Generate one after playing a session.
            </div>
          ) : (
            <div className="space-y-3">
              {recaps.map(recap => (
                <div key={recap.id} className="bg-zinc-900 border border-zinc-800 rounded-md p-4" data-testid={`recap-card-${recap.id}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-zinc-500">{new Date(recap.created_at).toLocaleString()}</span>
                  </div>
                  <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">{recap.summary}</p>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
