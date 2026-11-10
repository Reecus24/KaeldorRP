import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { GameProvider, useGame } from "@/context/GameContext";
import { Spinner } from "@/components/game/primitives";
import Layout from "@/components/game/Layout";

import Login from "@/pages/Login";
import Register from "@/pages/Register";
import CharacterCreate from "@/pages/CharacterCreate";
import Dashboard from "@/pages/Dashboard";
import HomeNeeds from "@/pages/HomeNeeds";
import Skills from "@/pages/Skills";
import JobCenter from "@/pages/JobCenter";
import CurrentJob from "@/pages/CurrentJob";
import Education from "@/pages/Education";
import Shop from "@/pages/Shop";
import Inventory from "@/pages/Inventory";
import Bank from "@/pages/Bank";
import RealEstate from "@/pages/RealEstate";
import VehicleDealer from "@/pages/VehicleDealer";
import BusinessMarket from "@/pages/BusinessMarket";
import OwnedBusinesses from "@/pages/OwnedBusinesses";
import BusinessManage from "@/pages/BusinessManage";
import Underworld from "@/pages/Underworld";
import Legal from "@/pages/Legal";
import Social from "@/pages/Social";
import ContactDetail from "@/pages/ContactDetail";
import DailySummary from "@/pages/DailySummary";
import Messages from "@/pages/Messages";
import JobMarket from "@/pages/JobMarket";
import Hospital from "@/pages/Hospital";
import Jail from "@/pages/Jail";
import Leaderboard from "@/pages/Leaderboard";
import Admin from "@/pages/Admin";

function FullLoader() {
    return (
        <div className="min-h-screen bg-[#050505] flex items-center justify-center">
            <Spinner />
        </div>
    );
}

function PublicOnly({ children }) {
    const { user, ready } = useAuth();
    if (!ready) return <FullLoader />;
    if (user) return <Navigate to="/" replace />;
    return children;
}

function ProtectedGame() {
    const { user, ready } = useAuth();
    const { hasCharacter, stateError, refresh } = useGame();
    if (!ready) return <FullLoader />;
    if (!user) return <Navigate to="/login" replace />;
    if (hasCharacter === null && stateError) return (
        <div className="min-h-screen bg-[#050505] flex items-center justify-center p-6">
            <div role="alert" className="kael-panel p-8 max-w-md text-center">
                <h1 className="font-display text-xl text-white mb-3">Connection interrupted</h1>
                <p className="text-muted-foreground mb-5">{stateError}</p>
                <button onClick={refresh} className="px-5 py-3 bg-neon-cyan text-black font-bold rounded-sm">Try again</button>
            </div>
        </div>
    );
    if (hasCharacter === null) return <FullLoader />;
    if (hasCharacter === false) return <Navigate to="/create-character" replace />;
    return (
        <Layout>
            <Outlet />
        </Layout>
    );
}

function CharacterGate() {
    const { user, ready } = useAuth();
    const { hasCharacter } = useGame();
    if (!ready) return <FullLoader />;
    if (!user) return <Navigate to="/login" replace />;
    if (hasCharacter === true) return <Navigate to="/" replace />;
    return <CharacterCreate />;
}

function AdminGate() {
    const { user } = useAuth();
    if (user?.role !== "admin") return <Navigate to="/" replace />;
    return <Admin />;
}

function AppRoutes() {
    return (
        <Routes>
            <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
            <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
            <Route path="/create-character" element={<CharacterGate />} />
            <Route element={<ProtectedGame />}>
                <Route path="/" element={<Dashboard />} />
                <Route path="/home" element={<HomeNeeds />} />
                <Route path="/skills" element={<Skills />} />
                <Route path="/jobs" element={<JobCenter />} />
                <Route path="/current-job" element={<CurrentJob />} />
                <Route path="/education" element={<Education />} />
                <Route path="/shop" element={<Shop />} />
                <Route path="/inventory" element={<Inventory />} />
                <Route path="/bank" element={<Bank />} />
                <Route path="/real-estate" element={<RealEstate />} />
                <Route path="/vehicles" element={<VehicleDealer />} />
                <Route path="/business-market" element={<BusinessMarket />} />
                <Route path="/businesses" element={<OwnedBusinesses />} />
                <Route path="/businesses/:id" element={<BusinessManage />} />
                <Route path="/social" element={<Social />} />
                <Route path="/social/:cid" element={<ContactDetail />} />
                <Route path="/daily-summary" element={<DailySummary />} />
                <Route path="/messages" element={<Messages />} />
                <Route path="/job-market" element={<JobMarket />} />
                <Route path="/underworld" element={<Underworld />} />
                <Route path="/legal" element={<Legal />} />
                <Route path="/hospital" element={<Hospital />} />
                <Route path="/jail" element={<Jail />} />
                <Route path="/leaderboard" element={<Leaderboard />} />
                <Route path="/admin" element={<AdminGate />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}

export default function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <GameProvider>
                    <AppRoutes />
                    <Toaster
                        position="bottom-center"
                        theme="dark"
                        toastOptions={{
                            style: {
                                background: "#0d0d0d",
                                border: "1px solid rgba(255,255,255,0.12)",
                                color: "#fff",
                                fontFamily: "Manrope, sans-serif",
                            },
                        }}
                    />
                </GameProvider>
            </AuthProvider>
        </BrowserRouter>
    );
}
