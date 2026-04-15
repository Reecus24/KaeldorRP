import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { getPlayerCharacters, getInventar, getTransactions, getProperties } from '@/lib/api';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ArrowUpRight, ArrowDownRight, Wallet, TrendingUp, TrendingDown, Building, AlertTriangle, Briefcase, RefreshCw } from 'lucide-react';

const typeLabels = {
  lohn: 'Lohn', miete: 'Miete', ausgabe: 'Ausgabe', einnahme: 'Einnahme',
  handel: 'Handel', bestechung: 'Bestechung', schuld: 'Schuld', tilgung: 'Tilgung',
};

const typeColors = {
  lohn: 'text-emerald-400', miete: 'text-red-400', ausgabe: 'text-red-400',
  einnahme: 'text-emerald-400', handel: 'text-amber-400', bestechung: 'text-orange-400',
  schuld: 'text-red-500', tilgung: 'text-blue-400',
};

function isIncome(type) {
  return ['einnahme', 'lohn', 'handel', 'tilgung'].includes(type);
}

function StatCard({ icon: Icon, label, value, sub, color = 'text-zinc-100' }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4" data-testid={`stat-${label.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${color}`} />
        <span className="text-xs text-zinc-500 uppercase tracking-wider">{label}</span>
      </div>
      <div className={`text-xl font-bold ${color}`} style={{ fontFamily: 'Manrope, sans-serif' }}>{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function FinanceDashboard() {
  const { activeCampaign } = useOutletContext();
  const [pcs, setPCs] = useState([]);
  const [selectedPcId, setSelectedPcId] = useState('');
  const [inventar, setInventar] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!activeCampaign?.id) return;
    getPlayerCharacters(activeCampaign.id).then(r => {
      const active = r.data.filter(p => p.status === 'active');
      setPCs(active);
      if (active.length > 0 && !selectedPcId) setSelectedPcId(active[0].id);
    }).catch(() => {});
  }, [activeCampaign]);

  const loadFinances = async () => {
    if (!selectedPcId || !activeCampaign?.id) return;
    setLoading(true);
    try {
      const [invRes, txRes, propRes] = await Promise.all([
        getInventar(selectedPcId).catch(() => ({ data: null })),
        getTransactions(activeCampaign.id, selectedPcId, 200).catch(() => ({ data: [] })),
        getProperties(activeCampaign.id, selectedPcId).catch(() => ({ data: [] })),
      ]);
      setInventar(invRes.data);
      setTransactions(txRes.data || []);
      setProperties(propRes.data || []);
    } catch (e) { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { loadFinances(); }, [selectedPcId, activeCampaign]);

  if (!activeCampaign) return <div className="p-8 text-zinc-500">Select or create a campaign first.</div>;

  const fin = inventar?.finances || {};
  const balance = fin.balance ?? 0;
  const currency = fin.currency || '';

  // Calculate recurring income & expenses from transactions
  const recentTx = transactions.slice(0, 50);
  const incomeEntries = recentTx.filter(t => isIncome(t.transaction_type));
  const expenseEntries = recentTx.filter(t => !isIncome(t.transaction_type));
  const totalRecentIncome = incomeEntries.reduce((s, t) => s + (t.amount || 0), 0);
  const totalRecentExpenses = expenseEntries.reduce((s, t) => s + (t.amount || 0), 0);

  // Group by day for daily view
  const byDay = {};
  for (const tx of transactions) {
    const day = tx.day || '?';
    if (!byDay[day]) byDay[day] = [];
    byDay[day].push(tx);
  }
  const sortedDays = Object.keys(byDay).sort((a, b) => (Number(b) || 0) - (Number(a) || 0));

  // Recurring costs from finance record
  const recurringCosts = fin.recurring_costs || '';
  const debts = fin.debts || '';

  // Properties with costs
  const propertyRent = properties.reduce((s, p) => s + (p.rent_cost || 0), 0);

  // Profession from selected PC
  const selectedPC = pcs.find(p => p.id === selectedPcId);

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in" data-testid="finance-dashboard">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-100" style={{ fontFamily: 'Manrope, sans-serif' }}>Finanzen</h1>
          <p className="text-sm text-zinc-500 mt-1">{activeCampaign.name} — Tag {activeCampaign.current_day || 1}</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedPcId} onValueChange={setSelectedPcId}>
            <SelectTrigger className="w-56 bg-zinc-900 border-zinc-800 text-zinc-100" data-testid="pc-selector">
              <SelectValue placeholder="Charakter wählen..." />
            </SelectTrigger>
            <SelectContent className="bg-zinc-900 border-zinc-800">
              {pcs.map(pc => (
                <SelectItem key={pc.id} value={pc.id}>{pc.character_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <button onClick={loadFinances} className="p-2 rounded-md border border-zinc-800 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100 transition-colors" data-testid="refresh-finances-btn">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {!selectedPcId ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-md p-8 text-center text-zinc-500">
          Kein aktiver Charakter vorhanden.
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="finance-summary">
            <StatCard icon={Wallet} label="Guthaben" value={`${balance} ${currency}`} color={balance >= 0 ? 'text-emerald-400' : 'text-red-400'} />
            <StatCard icon={TrendingUp} label="Einnahmen (letzte)" value={`+${totalRecentIncome} ${currency}`} sub={incomeEntries.length > 0 ? `${incomeEntries.length} Buchungen` : 'Keine'} color="text-emerald-400" />
            <StatCard icon={TrendingDown} label="Ausgaben (letzte)" value={`-${totalRecentExpenses} ${currency}`} sub={expenseEntries.length > 0 ? `${expenseEntries.length} Buchungen` : 'Keine'} color="text-red-400" />
            <StatCard icon={Building} label="Mietkosten" value={propertyRent > 0 ? `-${propertyRent}/Tag` : 'Keine'} sub={properties.length > 0 ? `${properties.length} Objekt${properties.length > 1 ? 'e' : ''}` : ''} color="text-orange-400" />
          </div>

          <Tabs defaultValue="overview" className="space-y-4">
            <TabsList className="bg-zinc-900 border border-zinc-800">
              <TabsTrigger value="overview" className="data-[state=active]:bg-zinc-700 text-xs" data-testid="tab-overview">Übersicht</TabsTrigger>
              <TabsTrigger value="log" className="data-[state=active]:bg-zinc-700 text-xs" data-testid="tab-log">Transaktionslog</TabsTrigger>
              <TabsTrigger value="daily" className="data-[state=active]:bg-zinc-700 text-xs" data-testid="tab-daily">Tagesansicht</TabsTrigger>
            </TabsList>

            {/* OVERVIEW TAB */}
            <TabsContent value="overview" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Recurring Income */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5" data-testid="recurring-income">
                  <div className="flex items-center gap-2 mb-3">
                    <Briefcase className="w-4 h-4 text-emerald-400" />
                    <h3 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Wiederkehrende Einnahmen</h3>
                  </div>
                  {selectedPC?.background ? (
                    <div className="text-sm text-zinc-400 mb-2">
                      <span className="text-zinc-500">Beruf:</span>{' '}
                      <span className="text-zinc-200">{selectedPC.background.slice(0, 120)}</span>
                    </div>
                  ) : null}
                  {incomeEntries.length > 0 ? (
                    <div className="space-y-1.5">
                      {[...new Set(incomeEntries.map(t => t.description))].map(desc => {
                        const matching = incomeEntries.filter(t => t.description === desc);
                        const avg = matching.reduce((s, t) => s + t.amount, 0) / matching.length;
                        return (
                          <div key={desc} className="flex items-center justify-between text-sm">
                            <span className="text-zinc-300">{desc}</span>
                            <span className="text-emerald-400 font-mono">+{avg} {currency}/Tag</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-600">Keine Einnahmen erfasst.</p>
                  )}
                </div>

                {/* Recurring Expenses */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5" data-testid="recurring-expenses">
                  <div className="flex items-center gap-2 mb-3">
                    <TrendingDown className="w-4 h-4 text-red-400" />
                    <h3 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Wiederkehrende Ausgaben</h3>
                  </div>
                  <div className="space-y-1.5">
                    {properties.map(p => (
                      <div key={p.id} className="flex items-center justify-between text-sm">
                        <span className="text-zinc-300">Miete: {p.name} <Badge variant="outline" className="ml-1 text-[10px] border-zinc-700 text-zinc-500">{p.property_type}</Badge></span>
                        <span className="text-red-400 font-mono">-{p.rent_cost} {p.rent_currency || currency}/Tag</span>
                      </div>
                    ))}
                    {recurringCosts && recurringCosts.split(/[,;]/).filter(Boolean).map((cost, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span className="text-zinc-300">{cost.trim()}</span>
                        <span className="text-red-400 font-mono">täglich</span>
                      </div>
                    ))}
                    {properties.length === 0 && !recurringCosts && (
                      <p className="text-xs text-zinc-600">Keine laufenden Kosten.</p>
                    )}
                  </div>
                </div>

                {/* Debts */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5" data-testid="debts-section">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    <h3 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Schulden & Verpflichtungen</h3>
                  </div>
                  {debts ? (
                    <div className="space-y-1.5">
                      {debts.split(/[,;]/).filter(Boolean).map((d, i) => (
                        <div key={i} className="text-sm text-red-300 bg-red-500/5 border border-red-500/10 rounded px-3 py-1.5">{d.trim()}</div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-600">Keine offenen Schulden.</p>
                  )}
                </div>

                {/* Properties */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-5" data-testid="properties-section">
                  <div className="flex items-center gap-2 mb-3">
                    <Building className="w-4 h-4 text-blue-400" />
                    <h3 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">Besitz & Mietobjekte</h3>
                  </div>
                  {properties.length > 0 ? (
                    <div className="space-y-2">
                      {properties.map(p => (
                        <div key={p.id} className="bg-zinc-950 border border-zinc-800 rounded px-3 py-2">
                          <div className="flex items-center justify-between">
                            <span className="text-sm text-zinc-200 font-medium">{p.name}</span>
                            <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-400">{p.status}</Badge>
                          </div>
                          <div className="text-xs text-zinc-500 mt-0.5">
                            {p.property_type} {p.location ? `in ${p.location}` : ''} {p.rent_cost ? `— ${p.rent_cost} ${p.rent_currency || currency}/Tag` : ''}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-600">Kein Besitz registriert.</p>
                  )}
                </div>
              </div>
            </TabsContent>

            {/* TRANSACTION LOG TAB */}
            <TabsContent value="log">
              <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden" data-testid="transaction-log">
                <Table>
                  <TableHeader>
                    <TableRow className="border-zinc-800 hover:bg-transparent">
                      <TableHead className="text-zinc-500 text-xs w-16">Tag</TableHead>
                      <TableHead className="text-zinc-500 text-xs w-24">Typ</TableHead>
                      <TableHead className="text-zinc-500 text-xs">Beschreibung</TableHead>
                      <TableHead className="text-zinc-500 text-xs w-20">Quelle</TableHead>
                      <TableHead className="text-zinc-500 text-xs text-right w-28">Betrag</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.length === 0 ? (
                      <TableRow className="border-zinc-800">
                        <TableCell colSpan={5} className="text-center text-zinc-600 py-8">Keine Transaktionen vorhanden.</TableCell>
                      </TableRow>
                    ) : transactions.map(tx => {
                      const inc = isIncome(tx.transaction_type);
                      return (
                        <TableRow key={tx.id} className="border-zinc-800 hover:bg-zinc-800/50" data-testid={`tx-row-${tx.id}`}>
                          <TableCell className="text-zinc-400 font-mono text-xs">{tx.day || '—'}</TableCell>
                          <TableCell>
                            <span className={`text-xs font-medium ${typeColors[tx.transaction_type] || 'text-zinc-400'}`}>
                              {typeLabels[tx.transaction_type] || tx.transaction_type}
                            </span>
                          </TableCell>
                          <TableCell className="text-sm text-zinc-300">
                            {tx.description || '—'}
                            {tx.counterparty && <span className="text-zinc-500 ml-1">({tx.counterparty})</span>}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-500">
                              {tx.source === 'tagwechsel' ? 'TW' : tx.source || '—'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            <span className={`flex items-center justify-end gap-1 ${inc ? 'text-emerald-400' : 'text-red-400'}`}>
                              {inc ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                              {inc ? '+' : '-'}{tx.amount} {tx.currency || currency}
                            </span>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </TabsContent>

            {/* DAILY VIEW TAB */}
            <TabsContent value="daily" className="space-y-3">
              {sortedDays.length === 0 ? (
                <div className="bg-zinc-900 border border-zinc-800 rounded-md p-8 text-center text-zinc-600">Keine Tageseinträge.</div>
              ) : sortedDays.map(day => {
                const dayTx = byDay[day];
                const dayIncome = dayTx.filter(t => isIncome(t.transaction_type)).reduce((s, t) => s + t.amount, 0);
                const dayExpense = dayTx.filter(t => !isIncome(t.transaction_type)).reduce((s, t) => s + t.amount, 0);
                const dayNet = dayIncome - dayExpense;
                return (
                  <div key={day} className="bg-zinc-900 border border-zinc-800 rounded-lg p-4" data-testid={`day-${day}`}>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-bold text-zinc-200" style={{ fontFamily: 'Manrope, sans-serif' }}>Tag {day}</h3>
                      <div className="flex items-center gap-4 text-xs font-mono">
                        <span className="text-emerald-400">+{dayIncome}</span>
                        <span className="text-red-400">-{dayExpense}</span>
                        <span className={dayNet >= 0 ? 'text-emerald-400' : 'text-red-400'}>= {dayNet >= 0 ? '+' : ''}{dayNet} {currency}</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      {dayTx.map(tx => {
                        const inc = isIncome(tx.transaction_type);
                        return (
                          <div key={tx.id} className="flex items-center justify-between text-sm py-0.5">
                            <div className="flex items-center gap-2">
                              {inc ? <ArrowUpRight className="w-3 h-3 text-emerald-400" /> : <ArrowDownRight className="w-3 h-3 text-red-400" />}
                              <span className={`text-xs ${typeColors[tx.transaction_type] || 'text-zinc-400'}`}>
                                {typeLabels[tx.transaction_type] || tx.transaction_type}
                              </span>
                              <span className="text-zinc-300">{tx.description}</span>
                            </div>
                            <span className={`font-mono ${inc ? 'text-emerald-400' : 'text-red-400'}`}>
                              {inc ? '+' : '-'}{tx.amount} {tx.currency || currency}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
