import { useEffect, useState } from 'react';
import "@/App.css";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import Sidebar from "@/components/Sidebar";
import Dashboard from "@/pages/Dashboard";
import CampaignManager from "@/pages/CampaignManager";
import NPCManager from "@/pages/NPCManager";
import PlayerCharacters from "@/pages/PlayerCharacters";
import LoreManager from "@/pages/LoreManager";
import RulesSettings from "@/pages/RulesSettings";
import ChannelConfig from "@/pages/ChannelConfig";
import EventLog from "@/pages/EventLog";
import { getActiveCampaign, getCampaigns } from "@/lib/api";
import { Toaster } from "@/components/ui/sonner";

function Layout({ activeCampaign, campaigns, setActiveCampaign, refreshCampaigns }) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#09090B]">
      <Sidebar />
      <main className="flex-1 overflow-y-auto" data-testid="main-content">
        <Outlet context={{ activeCampaign, campaigns, setActiveCampaign, refreshCampaigns }} />
      </main>
      <Toaster position="bottom-right" theme="dark" />
    </div>
  );
}

function App() {
  const [activeCampaign, setActiveCampaign] = useState(null);
  const [campaigns, setCampaigns] = useState([]);

  const refreshCampaigns = async () => {
    try {
      const [activeRes, allRes] = await Promise.all([
        getActiveCampaign().catch(() => null),
        getCampaigns()
      ]);
      setCampaigns(allRes.data);
      if (activeRes?.data) {
        setActiveCampaign(activeRes.data);
      } else if (allRes.data.length > 0) {
        setActiveCampaign(allRes.data[0]);
      }
    } catch (e) {
      console.error('Failed to load campaigns:', e);
    }
  };

  useEffect(() => { refreshCampaigns(); }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout activeCampaign={activeCampaign} campaigns={campaigns} setActiveCampaign={setActiveCampaign} refreshCampaigns={refreshCampaigns} />}>
          <Route index element={<Dashboard />} />
          <Route path="/campaigns" element={<CampaignManager />} />
          <Route path="/characters" element={<PlayerCharacters />} />
          <Route path="/npcs" element={<NPCManager />} />
          <Route path="/lore" element={<LoreManager />} />
          <Route path="/rules" element={<RulesSettings />} />
          <Route path="/channels" element={<ChannelConfig />} />
          <Route path="/logs" element={<EventLog />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
