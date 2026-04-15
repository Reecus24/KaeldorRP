require('dotenv').config();
const { Client, GatewayIntentBits, EmbedBuilder, SlashCommandBuilder, REST, Routes, PermissionFlagsBits, ChannelType } = require('discord.js');
const axios = require('axios');

const TOKEN = process.env.DISCORD_BOT_TOKEN;
const CLIENT_ID = process.env.DISCORD_CLIENT_ID;
const GUILD_ID = process.env.DISCORD_GUILD_ID;
const API = process.env.API_URL || 'http://localhost:8001/api';

if (!TOKEN || !CLIENT_ID) { console.error('Missing DISCORD_BOT_TOKEN or DISCORD_CLIENT_ID'); process.exit(1); }

// Formatting config
const SECTION_MODE = process.env.PLAYER_SECTION_MODE || 'smart'; // label | mention | smart
const SUPPRESS_MENTIONS = process.env.SUPPRESS_MENTION_NOTIFICATIONS === 'true';

/**
 * Post-process GM text for Discord formatting.
 * - Injects player section markers (label / mention / smart)
 * - Strips internal system markers
 * - Cleans up whitespace for readability
 */
function formatGmOutput(rawText, playerActions, isSplitScene) {
  let text = rawText;
  // Strip internal markers
  text = text.replace(/\[NEUER_ORT:\s*.+?\]/g, '').replace(/\[ÄNDERUNG:\s*.+?\]/g, '').trim();

  // Determine mode for this response
  let mode = SECTION_MODE;
  if (mode === 'smart') {
    mode = isSplitScene ? 'mention' : 'label';
  }

  // If multiple players, inject section markers where the GM used **Name** headers
  if (playerActions.length > 1) {
    for (const a of playerActions) {
      const name = a.pcName || a.pc_name || '?';
      const discordId = a.discordId || a.discord_id || '';

      // Build the replacement marker
      let marker;
      if (mode === 'mention' && discordId) {
        marker = `**<@${discordId}> — ${name}**`;
      } else {
        marker = `**${name}**`;
      }

      // Replace various GM patterns for player headers:
      // "**Name**:" / "**Name**," / "**Name**\n" at start of a section
      const namePatterns = [
        new RegExp(`\\*\\*${escapeRegex(name)}\\*\\*\\s*:`, 'g'),
        new RegExp(`\\*\\*${escapeRegex(name)}\\*\\*\\s*,`, 'g'),
        new RegExp(`^\\*\\*${escapeRegex(name)}\\*\\*`, 'gm'),
        // Also match "Name:" at line start without bold
        new RegExp(`^${escapeRegex(name)}\\s*:`, 'gm'),
      ];
      for (const pat of namePatterns) {
        if (pat.test(text)) {
          text = text.replace(pat, `${marker}:`);
          break; // Only replace with first matching pattern
        }
      }
    }
  }

  // Ensure clean paragraph breaks (normalize multiple newlines)
  text = text.replace(/\n{3,}/g, '\n\n');

  return text;
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Try to connect with MessageContent intent first, fallback to without
let HAS_MESSAGE_CONTENT = true;

async function startBot() {
  try {
    const fullClient = new Client({
      intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent]
    });
    await fullClient.login(TOKEN);
    console.log('MessageContent intent available - message-driven RP active');
    return fullClient;
  } catch (err) {
    if (err.message?.includes('disallowed intents') || err.code === 4014) {
      console.log('MessageContent intent not enabled - falling back to slash commands only');
      console.log('Enable it at: https://discord.com/developers/applications -> Bot -> Privileged Gateway Intents');
      HAS_MESSAGE_CONTENT = false;
      const basicClient = new Client({
        intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages]
      });
      await basicClient.login(TOKEN);
      return basicClient;
    }
    throw err;
  }
}

let client;

// ── Character Creation State ──
const creationSessions = new Map(); // channelId -> session

// ── Slash Commands ──
const commands = [
  new SlashCommandBuilder().setName('campaign').setDescription('Neue Kampagne erstellen und Charaktererstellung starten')
    .addStringOption(o => o.setName('setting').setDescription('Setting (z.B. "zombie apokalypse", "düsteres mittelalter")').setRequired(true))
    .addUserOption(o => o.setName('spieler1').setDescription('Erster Spieler').setRequired(false))
    .addUserOption(o => o.setName('spieler2').setDescription('Zweiter Spieler').setRequired(false)),
  new SlashCommandBuilder().setName('new_campaign').setDescription('Neue leere Kampagne (Admin)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addStringOption(o => o.setName('name').setDescription('Name').setRequired(true))
    .addStringOption(o => o.setName('world').setDescription('Weltbeschreibung').setRequired(false)),
  new SlashCommandBuilder().setName('scene').setDescription('Aktuelle Szene anzeigen'),
  new SlashCommandBuilder().setName('recap').setDescription('Sitzungszusammenfassung'),
  new SlashCommandBuilder().setName('rules').setDescription('Aktive Regeln anzeigen'),
  new SlashCommandBuilder().setName('set_tone').setDescription('Erzählton ändern (Admin)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addStringOption(o => o.setName('tone').setDescription('Ton').setRequired(true)
      .addChoices({name:'Grimdark',value:'grimdark'},{name:'Realistisch',value:'realistic'},{name:'Heroisch',value:'heroic'},{name:'Mysteriös',value:'mysterious'})),
  new SlashCommandBuilder().setName('reset_session').setDescription('Sitzung zurücksetzen (Admin)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),
  new SlashCommandBuilder().setName('set_channel_mode').setDescription('Kanalmodus setzen (Admin)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addStringOption(o => o.setName('mode').setDescription('Modus').setRequired(true)
      .addChoices({name:'In-Character (IC)',value:'ic'},{name:'Out-of-Character (OOC)',value:'ooc'},{name:'Admin',value:'admin'})),
  new SlashCommandBuilder().setName('pc_create').setDescription('Spielercharakter erstellen (Admin)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addUserOption(o => o.setName('player').setDescription('Spieler').setRequired(true))
    .addStringOption(o => o.setName('name').setDescription('Charaktername').setRequired(true)),
  new SlashCommandBuilder().setName('pc_view').setDescription('Charakter anzeigen')
    .addStringOption(o => o.setName('name').setDescription('Charaktername (leer=eigener)').setRequired(false)),
  new SlashCommandBuilder().setName('pc_edit').setDescription('Charakter bearbeiten (Admin)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addStringOption(o => o.setName('name').setDescription('Charaktername').setRequired(true))
    .addStringOption(o => o.setName('field').setDescription('Feld').setRequired(true)
      .addChoices({name:'Beschreibung',value:'short_description'},{name:'Verletzungen',value:'injuries_conditions'},
        {name:'Inventar',value:'inventory'},{name:'Status',value:'status'},{name:'Ort',value:'current_location'},
        {name:'Ruf',value:'reputation'},{name:'Ziele',value:'goals'},{name:'Fähigkeiten',value:'skills'}))
    .addStringOption(o => o.setName('value').setDescription('Neuer Wert').setRequired(true)),
  new SlashCommandBuilder().setName('start_character_creation').setDescription('Charaktererstellung (neu)starten (Admin)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addUserOption(o => o.setName('spieler1').setDescription('Erster Spieler').setRequired(true))
    .addUserOption(o => o.setName('spieler2').setDescription('Zweiter Spieler').setRequired(false)),
];

// ── Scene Turn Tracker ──
// Per-channel: tracks action lifecycle (pending → resolved → consumed)
// Key: channelId -> { campaignId, pendingActions, resolvedActions, lastGmResponse, lastGmText, processing }
const sceneTurns = new Map();

function getSceneTurn(channelId) {
  if (!sceneTurns.has(channelId)) {
    sceneTurns.set(channelId, {
      campaignId: null,
      pendingActions: [],    // current turn: awaiting GM response
      resolvedActions: [],   // previous turn: already narrated (kept for 1 cycle as context)
      lastGmResponse: 0,
      lastGmText: '',        // the GM's last response text, so the prompt can say "you already said this"
      processing: false,
    });
  }
  return sceneTurns.get(channelId);
}

// ── Helpers ──
async function getActiveCampaign() {
  const { data } = await axios.get(`${API}/campaigns/active`);
  return data;
}

function embed(title, desc, color = 0xF59E0B) {
  return new EmbedBuilder().setTitle(title).setDescription(desc.slice(0, 4096)).setColor(color).setTimestamp().setFooter({ text: 'Spielleiter' });
}

function isOOC(text) {
  const t = text.trim();
  return t.startsWith('//') || /^\(\([\s\S]*\)\)$/.test(t);
}

// ── Location Channel Auto-Creation ──
async function handleLocationChange(message, campaignId, locationName) {
  try {
    const { data: campaign } = await axios.get(`${API}/campaigns/${campaignId}`);
    if (!campaign.auto_create_channels) return null;

    const guild = message.guild;
    if (!guild) return null;

    const slug = locationName.toLowerCase().replace(/[^a-zäöüß0-9\s-]/g, '').replace(/\s+/g, '-').slice(0, 80);
    const existing = guild.channels.cache.find(c => c.name === slug && c.type === ChannelType.GuildText);
    if (existing) return existing;

    // Find or create campaign category
    let category = null;
    const catName = `${campaign.name}`.slice(0, 90);
    category = guild.channels.cache.find(c => c.name === catName && c.type === ChannelType.GuildCategory);
    if (!category && campaign.auto_create_channels) {
      try {
        category = await guild.channels.create({ name: catName, type: ChannelType.GuildCategory });
      } catch (e) { console.error('Cannot create category:', e.message); }
    }

    const newChannel = await guild.channels.create({
      name: slug,
      type: ChannelType.GuildText,
      parent: category?.id || null,
      topic: `${locationName} - ${campaign.name}`
    });

    // Register as IC channel
    await axios.post(`${API}/channels`, {
      campaign_id: campaignId, guild_id: guild.id,
      channel_id: newChannel.id, channel_name: slug, mode: 'ic'
    });

    // Post scene header
    await newChannel.send({ embeds: [embed(`${locationName}`, `*Die Szene wechselt hierher...*`, 0xD97706)] });
    return newChannel;
  } catch (err) {
    console.error('Location channel creation error:', err.message);
    return null;
  }
}

// ── Character Change Tracking ──
async function trackCharacterChanges(campaignId, response) {
  // Parse GM response for character state changes marked with [ÄNDERUNG: ...]
  const changes = [];
  const changePattern = /\[ÄNDERUNG:\s*(.+?)\]/gi;
  let match;
  while ((match = changePattern.exec(response)) !== null) {
    changes.push(match[1]);
  }
  if (changes.length > 0) {
    try {
      await axios.post(`${API}/character-changes`, {
        campaign_id: campaignId,
        changes: changes,
        source: response.slice(0, 200)
      });
    } catch (e) { /* silent - non-critical */ }
  }
  return changes;
}

// ── Async Memory Processing (fire-and-forget after GM response) ──
function processMemory(campaignId, narrative) {
  // Extract structured memory events
  axios.post(`${API}/memory/extract-events`, { campaign_id: campaignId, narrative })
    .catch(e => console.error('Memory extract:', e.message));
  // Update scene memory
  axios.post(`${API}/memory/update-scene`, { campaign_id: campaignId, narrative })
    .catch(e => console.error('Scene update:', e.message));
  // Track character changes from markers
  trackCharacterChanges(campaignId, narrative);
  // Periodic auto-summarize
  axios.get(`${API}/memory/events`, { params: { campaign_id: campaignId, limit: 100 } })
    .then(res => { if (res.data.length > 0 && res.data.length % 15 === 0) return axios.post(`${API}/memory/auto-summarize`, { campaign_id: campaignId }); })
    .catch(() => {});
}

// ── Character Creation Flow ──
async function handleCreationMessage(message, session) {
  const currentPlayer = session.players[session.currentIdx];
  if (!currentPlayer || message.author.id !== currentPlayer.id) return;

  if (session.phase === 'relationship_choice') {
    // Player choosing relationship
    if (!session.data[currentPlayer.id]) session.data[currentPlayer.id] = {};
    session.relationshipChoice = message.content;
    session.phase = 'finalizing';
    await message.channel.send('*Die Verbindung wird geschmiedet...*');
    await finalizeCreation(message.channel, session);
    return;
  }

  if (session.phase !== 'creating') return;
  const q = session.questions[session.step];
  if (!q) return;

  if (!session.data[currentPlayer.id]) session.data[currentPlayer.id] = {};
  session.data[currentPlayer.id][q.field] = message.content;

  // Acknowledge
  try {
    const campaign = await getActiveCampaign();
    const { data: conf } = await axios.post(`${API}/gm/confirm-character-step`, {
      campaign_id: campaign.id, field: q.field, answer: message.content,
      accumulated: session.data[currentPlayer.id]
    });
    if (conf.confirmation) await message.channel.send(`*${conf.confirmation}*`);
  } catch (e) { /* silent */ }

  session.step++;

  if (session.step >= session.questions.length) {
    // Current player done
    await message.channel.send(`**${session.data[currentPlayer.id]?.character_name || currentPlayer.username}** ist bereit.`);
    session.currentIdx++;
    session.step = 0;

    if (session.currentIdx >= session.players.length) {
      // All players done -> relationship phase
      if (session.players.length >= 2) {
        session.phase = 'relationship';
        await generateRelationship(message.channel, session);
      } else {
        session.phase = 'finalizing';
        await finalizeCreation(message.channel, session);
      }
    } else {
      const next = session.players[session.currentIdx];
      await message.channel.send(`\n---\n**<@${next.id}>, du bist dran!**\n`);
      await new Promise(r => setTimeout(r, 1000));
      await message.channel.send(session.questions[0].prompt);
    }
  } else {
    await new Promise(r => setTimeout(r, 800));
    await message.channel.send(session.questions[session.step].prompt);
  }
}

async function generateRelationship(channel, session) {
  try {
    const campaign = await getActiveCampaign();
    const p1Data = session.data[session.players[0].id] || {};
    const p2Data = session.data[session.players[1]?.id] || {};
    const { data } = await axios.post(`${API}/gm/generate-relationship`, {
      campaign_id: campaign.id, pc1_data: p1Data, pc2_data: p2Data
    });
    await channel.send(embed('Verbindung zwischen den Charakteren', data.relationship, 0xD97706));
    await channel.send(`**<@${session.players[0].id}>**, wähle eine der Optionen oder beschreibe eure Verbindung frei:`);
    session.phase = 'relationship_choice';
    session.currentIdx = 0;
  } catch (e) {
    console.error('Relationship generation error:', e.message);
    session.phase = 'finalizing';
    await finalizeCreation(channel, session);
  }
}

async function finalizeCreation(channel, session) {
  try {
    const campaign = await getActiveCampaign();
    const createdPCs = [];
    for (const player of session.players) {
      const pcData = session.data[player.id] || {};
      const { data: pc } = await axios.post(`${API}/player-characters`, {
        campaign_id: campaign.id, discord_user_id: player.id,
        character_name: pcData.character_name || player.username,
        status: 'active', short_description: pcData.background || '',
        appearance: pcData.appearance || '', personality_traits: pcData.personality_traits || '',
        background: pcData.background || '', goals: pcData.goals || '', fears: pcData.fears || '',
        strengths: pcData.strengths || '', weaknesses: pcData.weaknesses || '',
        skills: pcData.skills || pcData.strengths || '', inventory: pcData.inventory || '',
        gm_secrets: pcData.gm_secrets || '',
        relationship_notes: session.relationshipChoice || '',
        current_location: campaign.starting_location || ''
      });
      createdPCs.push(pc);
      // Also ensure player is in allowed list
      await axios.post(`${API}/allowed-players`, {
        campaign_id: campaign.id, discord_user_id: player.id, discord_username: player.username
      }).catch(() => {});
    }

    // Post character summaries
    for (const pc of createdPCs) {
      const desc = `**Name:** ${pc.character_name}\n**Hintergrund:** ${pc.background || '-'}\n**Aussehen:** ${pc.appearance || '-'}\n**Persönlichkeit:** ${pc.personality_traits || '-'}\n**Stärken:** ${pc.strengths || '-'}\n**Schwächen:** ${pc.weaknesses || '-'}\n**Ziele:** ${pc.goals || '-'}\n**Inventar:** ${pc.inventory || '-'}`;
      await channel.send({ embeds: [embed(pc.character_name, desc, 0x10B981)] });
    }

    if (session.relationshipChoice) {
      await channel.send({ embeds: [embed('Verbindung', session.relationshipChoice, 0x8B5CF6)] });
    }

    // Generate opening scene
    await channel.send('\n*Der Spielleiter bereitet die Eröffnungsszene vor...*');
    const { data: sceneData } = await axios.post(`${API}/gm/generate-opening-scene`, { campaign_id: campaign.id });

    // Set up channel as IC
    await axios.post(`${API}/channels`, {
      campaign_id: campaign.id, guild_id: channel.guildId,
      channel_id: channel.id, channel_name: channel.name || '', mode: 'ic'
    });

    await channel.send({ embeds: [embed(`${campaign.name} - Beginn`, sceneData.scene, 0xF59E0B)] });
    await channel.send('---\n*Das Spiel beginnt. Schreibt eure Handlungen als normale Nachrichten.*');

    session.phase = 'done';
    creationSessions.delete(channel.id);
  } catch (e) {
    console.error('Finalize error:', e.message);
    await channel.send('Fehler beim Abschließen der Charaktererstellung. Bitte versuche /start_character_creation erneut.');
    creationSessions.delete(channel.id);
  }
}

// ── Slash Command Handlers ──
async function handleCampaign(interaction) {
  await interaction.deferReply();
  const setting = interaction.options.getString('setting');
  const p1 = interaction.options.getUser('spieler1');
  const p2 = interaction.options.getUser('spieler2');

  try {
    // Generate campaign via LLM
    const { data: genData } = await axios.post(`${API}/gm/generate-campaign`, { prompt: setting });
    // Create campaign in DB
    const { data: campaign } = await axios.post(`${API}/campaigns`, {
      name: genData.title || setting, world_summary: genData.world_summary || '',
      tone: genData.tone || 'realistic'
    });
    // Store extra data
    if (genData.starting_location || genData.current_threat) {
      await axios.put(`${API}/campaigns/${campaign.id}`, {
        world_summary: `${genData.world_summary || ''}\n\nBedrohung: ${genData.current_threat || ''}\nStartort: ${genData.starting_location || ''}\nFraktionen: ${(genData.factions || []).join('; ')}\nHaken: ${(genData.hooks || []).join('; ')}`
      });
      campaign.starting_location = genData.starting_location;
    }

    // Post campaign embed
    let desc = `**Welt:** ${genData.world_summary || '-'}\n**Bedrohung:** ${genData.current_threat || '-'}\n**Startort:** ${genData.starting_location || '-'}`;
    if (genData.factions?.length) desc += `\n**Fraktionen:** ${genData.factions.join(', ')}`;
    if (genData.hooks?.length) desc += `\n**Haken:** ${genData.hooks.join(', ')}`;
    await interaction.editReply({ embeds: [embed(`${genData.title || setting}`, desc, 0xF59E0B)] });

    if (genData.opening_scene) {
      await interaction.channel.send({ embeds: [embed('Prolog', genData.opening_scene, 0xD97706)] });
    }

    // Determine players
    const players = [];
    if (p1 && !p1.bot) players.push({ id: p1.id, username: p1.username });
    if (p2 && !p2.bot) players.push({ id: p2.id, username: p2.username });
    if (players.length === 0) {
      await interaction.channel.send('Keine Spieler angegeben. Verwende `/start_character_creation @spieler1 @spieler2` um die Charaktererstellung zu beginnen.');
      return;
    }

    // Add as allowed players
    for (const pl of players) {
      await axios.post(`${API}/allowed-players`, {
        campaign_id: campaign.id, discord_user_id: pl.id, discord_username: pl.username
      }).catch(() => {});
    }

    // Generate character questions
    const { data: qData } = await axios.post(`${API}/gm/generate-character-questions`, { campaign_id: campaign.id });
    const questions = qData.questions || qData;

    // Start character creation
    creationSessions.set(interaction.channelId, {
      campaignId: campaign.id, players, currentIdx: 0, step: 0,
      questions: Array.isArray(questions) ? questions : [], data: {}, phase: 'creating'
    });

    await interaction.channel.send(`\n---\n**Charaktererstellung**\nBevor das Abenteuer beginnt, erstellen wir eure Charaktere.\n\n**<@${players[0].id}>, du bist zuerst dran!**`);
    await new Promise(r => setTimeout(r, 1500));
    if (questions.length > 0) {
      await interaction.channel.send(questions[0].prompt || questions[0]);
    }
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Fehler:** ${msg}` });
  }
}

async function handleStartCharCreation(interaction) {
  await interaction.deferReply();
  const p1 = interaction.options.getUser('spieler1');
  const p2 = interaction.options.getUser('spieler2');
  const players = [];
  if (p1 && !p1.bot) players.push({ id: p1.id, username: p1.username });
  if (p2 && !p2.bot) players.push({ id: p2.id, username: p2.username });
  if (!players.length) { await interaction.editReply('Mindestens ein Spieler benötigt.'); return; }

  try {
    const campaign = await getActiveCampaign();
    for (const pl of players) {
      await axios.post(`${API}/allowed-players`, {
        campaign_id: campaign.id, discord_user_id: pl.id, discord_username: pl.username
      }).catch(() => {});
    }
    const { data: qData } = await axios.post(`${API}/gm/generate-character-questions`, { campaign_id: campaign.id });
    const questions = qData.questions || qData;

    creationSessions.set(interaction.channelId, {
      campaignId: campaign.id, players, currentIdx: 0, step: 0,
      questions: Array.isArray(questions) ? questions : [], data: {}, phase: 'creating'
    });

    await interaction.editReply(`Charaktererstellung gestartet für ${players.map(p => `<@${p.id}>`).join(' und ')}.`);
    await interaction.channel.send(`**<@${players[0].id}>, du bist zuerst dran!**`);
    if (questions.length > 0) {
      await new Promise(r => setTimeout(r, 1000));
      await interaction.channel.send(questions[0].prompt || questions[0]);
    }
  } catch (err) {
    await interaction.editReply(`**Fehler:** ${err.response?.data?.detail || err.message}`);
  }
}

async function handleScene(interaction) {
  await interaction.deferReply();
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.get(`${API}/gm/scene-summary`, { params: { campaign_id: campaign.id } });
    if (data.summary) { await interaction.editReply(data.summary); return; }
    const s = data.scene;
    let desc = `**Ort:** ${s.location}\n**Zeit:** ${s.time_of_day || '?'}\n**Spannung:** ${s.tension_level}/10\n\n${s.description}`;
    if (s.active_threats?.length) desc += `\n\n**Bedrohungen:** ${s.active_threats.join(', ')}`;
    if (s.unresolved_hooks?.length) desc += `\n**Offene Fäden:** ${s.unresolved_hooks.join(', ')}`;
    await interaction.editReply({ embeds: [embed(`Szene: ${s.location}`, desc)] });
  } catch (err) { await interaction.editReply(`**Fehler:** ${err.response?.data?.detail || err.message}`); }
}

async function handleRecap(interaction) {
  await interaction.deferReply();
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.post(`${API}/gm/generate-recap`, { campaign_id: campaign.id });
    await interaction.editReply({ embeds: [embed('Zusammenfassung', data.recap, 0xD97706)] });
  } catch (err) { await interaction.editReply(`**Fehler:** ${err.response?.data?.detail || err.message}`); }
}

async function handleRules(interaction) {
  await interaction.deferReply();
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.get(`${API}/rules`, { params: { campaign_id: campaign.id } });
    let desc = `**Würfelsystem:** ${data.dice_system}\n**Kritische Treffer:** ${data.critical_enabled ? 'Aktiv' : 'Inaktiv'}\n**Verdeckte Würfe:** ${data.hidden_rolls_enabled ? 'Aktiv' : 'Inaktiv'}\n**Schwierigkeitsgrade:** ${data.difficulty_classes}`;
    if (data.content) desc += `\n\n**Regeln:**\n${data.content}`;
    await interaction.editReply({ embeds: [embed('Aktive Regeln', desc, 0x8B5CF6)] });
  } catch (err) { await interaction.editReply(`**Fehler:** ${err.response?.data?.detail || err.message}`); }
}

async function handleSetTone(interaction) {
  const tone = interaction.options.getString('tone');
  try {
    const campaign = await getActiveCampaign();
    await axios.put(`${API}/campaigns/${campaign.id}`, { tone });
    await interaction.reply({ embeds: [embed('Ton geändert', `Erzählton auf **${tone}** gesetzt.`)] });
  } catch (err) { await interaction.reply({ content: `**Fehler:** ${err.message}`, ephemeral: true }); }
}

async function handleResetSession(interaction) {
  await interaction.deferReply({ ephemeral: true });
  try {
    const campaign = await getActiveCampaign();
    await axios.post(`${API}/gm/reset-session`, { campaign_id: campaign.id });
    await interaction.editReply('Sitzung zurückgesetzt. Szene deaktiviert, Chat-Verlauf gelöscht.');
  } catch (err) { await interaction.editReply(`**Fehler:** ${err.message}`); }
}

async function handleNewCampaign(interaction) {
  await interaction.deferReply({ ephemeral: true });
  try {
    const { data } = await axios.post(`${API}/campaigns`, {
      name: interaction.options.getString('name'),
      world_summary: interaction.options.getString('world') || ''
    });
    await interaction.editReply(`Kampagne **${data.name}** erstellt und aktiviert.`);
  } catch (err) { await interaction.editReply(`**Fehler:** ${err.message}`); }
}

async function handleSetChannelMode(interaction) {
  const mode = interaction.options.getString('mode');
  try {
    const campaign = await getActiveCampaign();
    await axios.post(`${API}/channels`, {
      campaign_id: campaign.id, guild_id: interaction.guildId,
      channel_id: interaction.channelId, channel_name: interaction.channel?.name || '', mode
    });
    const labels = { ic: 'In-Character', ooc: 'Out-of-Character', admin: 'Admin' };
    await interaction.reply({ content: `Kanal auf **${labels[mode] || mode}** gesetzt.`, ephemeral: true });
  } catch (err) { await interaction.reply({ content: `**Fehler:** ${err.message}`, ephemeral: true }); }
}

async function handlePCCreate(interaction) {
  await interaction.deferReply({ ephemeral: true });
  const player = interaction.options.getUser('player');
  const name = interaction.options.getString('name');
  try {
    const campaign = await getActiveCampaign();
    await axios.post(`${API}/player-characters`, {
      campaign_id: campaign.id, discord_user_id: player.id, character_name: name, status: 'active'
    });
    await interaction.editReply(`Charakter **${name}** für <@${player.id}> erstellt.`);
  } catch (err) { await interaction.editReply(`**Fehler:** ${err.message}`); }
}

async function handlePCView(interaction) {
  await interaction.deferReply();
  const name = interaction.options.getString('name');
  try {
    const campaign = await getActiveCampaign();
    const { data: pcs } = await axios.get(`${API}/player-characters`, { params: { campaign_id: campaign.id } });
    let pc;
    if (name) { pc = pcs.find(p => p.character_name.toLowerCase() === name.toLowerCase()); }
    else { pc = pcs.find(p => p.discord_user_id === interaction.user.id && p.status === 'active'); }
    if (!pc) { await interaction.editReply('Charakter nicht gefunden.'); return; }
    let desc = `**Status:** ${pc.status}\n**Hintergrund:** ${pc.background || '-'}\n**Aussehen:** ${pc.appearance || '-'}\n**Persönlichkeit:** ${pc.personality_traits || '-'}\n**Stärken:** ${pc.strengths || '-'} | **Schwächen:** ${pc.weaknesses || '-'}\n**Ziele:** ${pc.goals || '-'} | **Ängste:** ${pc.fears || '-'}\n**Fähigkeiten:** ${pc.skills || '-'}\n**Verletzungen:** ${pc.injuries_conditions || 'Keine'}\n**Inventar:** ${pc.inventory || '-'}\n**Fraktion:** ${pc.faction_ties || '-'}\n**Ruf:** ${pc.reputation || '-'}\n**Ort:** ${pc.current_location || '-'}`;
    await interaction.editReply({ embeds: [embed(pc.character_name, desc, 0x10B981)] });
  } catch (err) { await interaction.editReply(`**Fehler:** ${err.message}`); }
}

async function handlePCEdit(interaction) {
  await interaction.deferReply({ ephemeral: true });
  const name = interaction.options.getString('name');
  const field = interaction.options.getString('field');
  const value = interaction.options.getString('value');
  try {
    const campaign = await getActiveCampaign();
    const { data: pcs } = await axios.get(`${API}/player-characters`, { params: { campaign_id: campaign.id } });
    const pc = pcs.find(p => p.character_name.toLowerCase() === name.toLowerCase());
    if (!pc) { await interaction.editReply('Charakter nicht gefunden.'); return; }
    await axios.put(`${API}/player-characters/${pc.id}`, { [field]: value });
    await interaction.editReply(`**${name}** aktualisiert: ${field} = ${value}`);
  } catch (err) { await interaction.editReply(`**Fehler:** ${err.message}`); }
}

// ── Start Bot ──
(async () => {
  try {
    client = await startBot();

    client.once('ready', async () => {
      console.log(`Bot online als ${client.user.tag}`);
      try {
        const rest = new REST().setToken(TOKEN);
        const body = commands.map(c => c.toJSON());
        if (GUILD_ID) {
          await rest.put(Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID), { body });
          console.log(`${body.length} Guild-Befehle registriert`);
        } else {
          await rest.put(Routes.applicationCommands(CLIENT_ID), { body });
          console.log(`${body.length} globale Befehle registriert`);
        }
      } catch (err) { console.error('Befehlsregistrierung fehlgeschlagen:', err); }
    });

    client.on('interactionCreate', async interaction => {
      if (!interaction.isChatInputCommand()) return;
      if (GUILD_ID && interaction.guildId !== GUILD_ID) {
        return interaction.reply({ content: 'Bot nicht für diesen Server konfiguriert.', ephemeral: true });
      }
      const h = {
        campaign: handleCampaign, new_campaign: handleNewCampaign, scene: handleScene,
        recap: handleRecap, rules: handleRules, set_tone: handleSetTone,
        reset_session: handleResetSession, set_channel_mode: handleSetChannelMode,
        pc_create: handlePCCreate, pc_view: handlePCView, pc_edit: handlePCEdit,
        start_character_creation: handleStartCharCreation,
      };
      const handler = h[interaction.commandName];
      if (handler) {
        try { await handler(interaction); }
        catch (err) {
          console.error(`Fehler /${interaction.commandName}:`, err);
          const fn = interaction.deferred || interaction.replied ? interaction.editReply.bind(interaction) : interaction.reply.bind(interaction);
          await fn({ content: 'Ein Fehler ist aufgetreten.', ephemeral: true }).catch(() => {});
        }
      }
    });

    // Message handler - scene-turn-aware
    client.on('messageCreate', async message => {
      if (message.author.bot || !message.guild) return;
      if (GUILD_ID && message.guildId !== GUILD_ID) return;
      const content = message.content || '';
      if (!content) return;

      // Check character creation mode FIRST
      const session = creationSessions.get(message.channelId);
      if (session && session.phase !== 'done') {
        await handleCreationMessage(message, session);
        return;
      }

      // Normal IC message handling
      if (!HAS_MESSAGE_CONTENT) return;
      try {
        const campaign = await getActiveCampaign().catch(() => null);
        if (!campaign) return;
        const { data: channels } = await axios.get(`${API}/channels`, { params: { campaign_id: campaign.id } });
        const chCfg = channels.find(c => c.channel_id === message.channelId);
        if (!chCfg || chCfg.mode !== 'ic') return;
        const { data: allowed } = await axios.get(`${API}/allowed-players`, { params: { campaign_id: campaign.id } });
        if (!allowed.some(p => p.discord_user_id === message.author.id)) return;
        if (isOOC(message.content) || message.content.trim().length < 3) return;

        // ── Scene Turn Logic ──
        // Find which PCs are present in THIS channel/scene
        const { data: allPCs } = await axios.get(`${API}/player-characters/active`, { params: { campaign_id: campaign.id } });
        // Determine which allowed players have PCs (these are the expected actors)
        const scenePlayers = allowed.filter(a => allPCs.some(pc => pc.discord_user_id === a.discord_user_id));

        // Get the active PC for the message author
        const authorPC = allPCs.find(pc => pc.discord_user_id === message.author.id);
        const pcName = authorPC?.character_name || message.author.username;

        // Record this player's action for this scene/channel
        const turn = getSceneTurn(message.channelId);
        turn.campaignId = campaign.id;

        // Don't duplicate if same player posts again before GM responds
        const alreadyActed = turn.pendingActions.some(a => a.discordId === message.author.id);
        if (alreadyActed) {
          // Replace their previous action with the newer one
          turn.pendingActions = turn.pendingActions.filter(a => a.discordId !== message.author.id);
        }
        turn.pendingActions.push({
          discordId: message.author.id,
          pcName,
          message: message.content,
          timestamp: Date.now()
        });

        // Check: have ALL PCs present in this scene acted?
        // For split scenes: only PCs whose allowed-player is in this channel's scene
        // Simple heuristic: if there are N allowed players with active PCs, wait for N actions
        // But if only 1 PC exists or only 1 is configured, respond after 1
        const expectedCount = scenePlayers.length;
        const actedCount = turn.pendingActions.length;
        const allActed = actedCount >= expectedCount;

        if (!allActed) {
          // Not all PCs have acted yet — wait silently
          return;
        }

        // All PCs in this scene have acted — generate combined GM response
        if (turn.processing) return; // Prevent double-processing
        turn.processing = true;

        try {
          await message.channel.sendTyping();

          // Build combined action string from all pending actions
          const combinedActions = turn.pendingActions
            .map(a => `${a.pcName}: ${a.message}`)
            .join('\n');

          const { data: result } = await axios.post(`${API}/gm/scene-response`, {
            campaign_id: campaign.id,
            channel_id: message.channelId,
            player_actions: turn.pendingActions.map(a => ({
              discord_id: a.discordId, pc_name: a.pcName, message: a.message
            })),
            resolved_last_turn: turn.resolvedActions.map(a => ({
              pc_name: a.pcName, message: a.message
            })),
            last_gm_response: turn.lastGmText || ''
          });

          // Lifecycle: pending → resolved, old resolved → consumed (dropped)
          turn.resolvedActions = [...turn.pendingActions];
          turn.pendingActions = [];
          turn.lastGmResponse = Date.now();
          turn.lastGmText = result.response || '';
          turn.processing = false;

          if (result.response) {
            // Determine if this is a split scene (only 1 player acted)
            const isSplit = turn.resolvedActions.length <= 1 && turn.pendingActions.length <= 1;
            let text = formatGmOutput(result.response, turn.resolvedActions, isSplit);

            // Handle location markers (already stripped by formatGmOutput, check raw)
            const locMatch = result.response.match(/\[NEUER_ORT:\s*(.+?)\]/);
            if (locMatch) {
              const newCh = await handleLocationChange(message, campaign.id, locMatch[1]);
              if (newCh) {
                await message.channel.send(`*Die Szene wechselt nach **${locMatch[1]}**... Weiter in <#${newCh.id}>*`);
                if (text.length <= 2000) await newCh.send(text);
                else await newCh.send({ embeds: [embed('Spielleiter', text)] });
                processMemory(campaign.id, result.response);
                return;
              }
            }

            // Send GM response — prefer plain text for readability, embed only if too long
            if (text.length <= 2000) {
              await message.channel.send({
                content: text,
                allowedMentions: SUPPRESS_MENTIONS ? { parse: [] } : undefined
              });
            } else {
              await message.channel.send({
                embeds: [embed('Spielleiter', text)],
                allowedMentions: SUPPRESS_MENTIONS ? { parse: [] } : undefined
              });
            }

            processMemory(campaign.id, result.response);
          }
        } catch (innerErr) {
          turn.processing = false;
          if (innerErr.response?.status !== 404) console.error('Scene response error:', innerErr.message);
        }
      } catch (err) {
        if (err.response?.status !== 404) console.error('Message handler error:', err.message);
      }
    });

    client.on('error', err => console.error('Client error:', err));
  } catch (err) {
    console.error('Bot startup failed:', err);
    process.exit(1);
  }
})();

process.on('unhandledRejection', err => console.error('Unhandled:', err));
