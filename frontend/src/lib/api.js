import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

// Campaigns
export const getCampaigns = () => api.get('/campaigns');
export const getActiveCampaign = () => api.get('/campaigns/active');
export const createCampaign = (data) => api.post('/campaigns', data);
export const updateCampaign = (id, data) => api.put(`/campaigns/${id}`, data);
export const deleteCampaign = (id) => api.delete(`/campaigns/${id}`);

// NPCs
export const getNPCs = (campaignId) => api.get('/npcs', { params: { campaign_id: campaignId } });
export const createNPC = (data) => api.post('/npcs', data);
export const updateNPC = (id, data) => api.put(`/npcs/${id}`, data);
export const deleteNPC = (id) => api.delete(`/npcs/${id}`);

// Lore
export const getLore = (campaignId) => api.get('/lore', { params: { campaign_id: campaignId } });
export const createLore = (data) => api.post('/lore', data);
export const updateLore = (id, data) => api.put(`/lore/${id}`, data);
export const deleteLore = (id) => api.delete(`/lore/${id}`);

// Scenes
export const getActiveScene = (campaignId) => api.get('/scenes/active', { params: { campaign_id: campaignId } });
export const getScenes = (campaignId) => api.get('/scenes', { params: { campaign_id: campaignId } });
export const createScene = (data) => api.post('/scenes', data);
export const updateScene = (id, data) => api.put(`/scenes/${id}`, data);

// Events
export const getEvents = (campaignId, limit = 50) => api.get('/events', { params: { campaign_id: campaignId, limit } });
export const createEvent = (data) => api.post('/events', data);

// Recaps
export const getRecaps = (campaignId) => api.get('/recaps', { params: { campaign_id: campaignId } });

// Rules
export const getRules = (campaignId) => api.get('/rules', { params: { campaign_id: campaignId } });
export const updateRules = (id, data) => api.put(`/rules/${id}`, data);
export const createRules = (data) => api.post('/rules', data);

// Channels
export const getChannels = (campaignId) => api.get('/channels', { params: { campaign_id: campaignId } });
export const createChannel = (data) => api.post('/channels', data);
export const updateChannel = (id, data) => api.put(`/channels/${id}`, data);
export const deleteChannel = (id) => api.delete(`/channels/${id}`);

// Quests
export const getQuests = (campaignId) => api.get('/quests', { params: { campaign_id: campaignId } });
export const createQuest = (data) => api.post('/quests', data);
export const updateQuest = (id, data) => api.put(`/quests/${id}`, data);
export const deleteQuest = (id) => api.delete(`/quests/${id}`);

// GM
export const gmNarrate = (data) => api.post('/gm/narrate', data);
export const gmNpcSpeak = (data) => api.post('/gm/npc-speak', data);
export const gmRoll = (data) => api.post('/gm/roll', data);
export const gmCheck = (data) => api.post('/gm/check', data);
export const gmSceneSummary = (campaignId) => api.get('/gm/scene-summary', { params: { campaign_id: campaignId } });
export const gmGenerateRecap = (data) => api.post('/gm/generate-recap', data);
export const gmResetSession = (data) => api.post('/gm/reset-session', data);

// Export/Import
export const exportCampaign = (campaignId) => api.get(`/export/${campaignId}`);
export const importCampaign = (data) => api.post('/import', data);

// Bot Status
export const getBotStatus = () => api.get('/bot/status');

// Player Characters
export const getPlayerCharacters = (campaignId) => api.get('/player-characters', { params: { campaign_id: campaignId } });
export const createPlayerCharacter = (data) => api.post('/player-characters', data);
export const updatePlayerCharacter = (id, data) => api.put(`/player-characters/${id}`, data);
export const deletePlayerCharacter = (id) => api.delete(`/player-characters/${id}`);

// Sandbox: Inventory, Finances, Transactions, Properties
export const getInventar = (pcId) => api.get(`/sandbox/inventar/${pcId}`);
export const getFinances = (campaignId, pcId) => api.get('/finances', { params: { campaign_id: campaignId, pc_id: pcId } });
export const getTransactions = (campaignId, pcId, limit = 100) => api.get('/transactions', { params: { campaign_id: campaignId, pc_id: pcId, limit } });
export const getProperties = (campaignId, pcId) => api.get('/properties', { params: { campaign_id: campaignId, owner_pc_id: pcId } });
// Allowed Players
export const getAllowedPlayers = (campaignId) => api.get('/allowed-players', { params: { campaign_id: campaignId } });
export const addAllowedPlayer = (data) => api.post('/allowed-players', data);
export const removeAllowedPlayer = (id) => api.delete(`/allowed-players/${id}`);

export default api;
