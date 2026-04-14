require('dotenv').config();
const { Client, GatewayIntentBits, EmbedBuilder, SlashCommandBuilder, REST, Routes, PermissionFlagsBits } = require('discord.js');
const axios = require('axios');

const TOKEN = process.env.DISCORD_BOT_TOKEN;
const CLIENT_ID = process.env.DISCORD_CLIENT_ID;
const GUILD_ID = process.env.DISCORD_GUILD_ID;
const API = process.env.API_URL || 'http://localhost:8001/api';

if (!TOKEN || !CLIENT_ID) {
  console.error('Missing DISCORD_BOT_TOKEN or DISCORD_CLIENT_ID in .env');
  process.exit(1);
}

const client = new Client({ intents: [GatewayIntentBits.Guilds] });

// ── Slash Command Definitions ──

const commands = [
  new SlashCommandBuilder()
    .setName('gm')
    .setDescription('Narrate a scene outcome as Game Master')
    .addStringOption(o => o.setName('action').setDescription('Your action or the situation to narrate').setRequired(true)),

  new SlashCommandBuilder()
    .setName('npc')
    .setDescription('Speak or act as a named NPC')
    .addStringOption(o => o.setName('name').setDescription('NPC name').setRequired(true))
    .addStringOption(o => o.setName('dialogue').setDescription('What you say or do toward the NPC').setRequired(true)),

  new SlashCommandBuilder()
    .setName('roll')
    .setDescription('Roll dice (e.g. 1d20, 2d6+3)')
    .addStringOption(o => o.setName('dice').setDescription('Dice expression').setRequired(true))
    .addStringOption(o => o.setName('context').setDescription('Optional context for the roll').setRequired(false)),

  new SlashCommandBuilder()
    .setName('check')
    .setDescription('Resolve a skill or situation check')
    .addStringOption(o => o.setName('difficulty').setDescription('Difficulty level').setRequired(true)
      .addChoices(
        { name: 'Easy', value: 'easy' },
        { name: 'Medium', value: 'medium' },
        { name: 'Hard', value: 'hard' },
        { name: 'Extreme', value: 'extreme' }
      ))
    .addStringOption(o => o.setName('context').setDescription('What are you attempting?').setRequired(true)),

  new SlashCommandBuilder()
    .setName('scene')
    .setDescription('Show current scene summary'),

  new SlashCommandBuilder()
    .setName('recap')
    .setDescription('Summarize what happened in the session so far'),

  new SlashCommandBuilder()
    .setName('journal')
    .setDescription('Show the campaign event history'),

  new SlashCommandBuilder()
    .setName('rules')
    .setDescription('Show the active RP rules'),

  new SlashCommandBuilder()
    .setName('set_tone')
    .setDescription('Change narration style')
    .addStringOption(o => o.setName('tone').setDescription('Narration tone').setRequired(true)
      .addChoices(
        { name: 'Grimdark', value: 'grimdark' },
        { name: 'Realistic', value: 'realistic' },
        { name: 'Heroic', value: 'heroic' },
        { name: 'Mysterious', value: 'mysterious' }
      )),

  new SlashCommandBuilder()
    .setName('reset_session')
    .setDescription('Reset current session (admin only)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

  new SlashCommandBuilder()
    .setName('new_campaign')
    .setDescription('Create a new campaign (admin only)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addStringOption(o => o.setName('name').setDescription('Campaign name').setRequired(true))
    .addStringOption(o => o.setName('world').setDescription('Brief world description').setRequired(false)),

  new SlashCommandBuilder()
    .setName('set_channel_mode')
    .setDescription('Set channel mode (admin only)')
    .setDefaultMemberPermissions(PermissionFlagsBits.Administrator)
    .addStringOption(o => o.setName('mode').setDescription('Channel mode').setRequired(true)
      .addChoices(
        { name: 'In-Character (IC)', value: 'ic' },
        { name: 'Out-of-Character (OOC)', value: 'ooc' },
        { name: 'Admin', value: 'admin' }
      )),
];

// ── Helpers ──

async function getActiveCampaign() {
  const { data } = await axios.get(`${API}/campaigns/active`);
  return data;
}

function gmEmbed(title, description, color = 0xF59E0B) {
  return new EmbedBuilder()
    .setTitle(title)
    .setDescription(description.slice(0, 4096))
    .setColor(color)
    .setTimestamp()
    .setFooter({ text: 'Game Master' });
}

function truncate(str, len = 4096) {
  return str && str.length > len ? str.slice(0, len - 3) + '...' : str;
}

// ── Command Handlers ──

async function handleGM(interaction) {
  await interaction.deferReply();
  const action = interaction.options.getString('action');
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.post(`${API}/gm/narrate`, {
      campaign_id: campaign.id,
      action,
      channel_id: interaction.channelId
    });
    const embed = gmEmbed('Game Master', data.narration);
    await interaction.editReply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleNPC(interaction) {
  await interaction.deferReply();
  const name = interaction.options.getString('name');
  const dialogue = interaction.options.getString('dialogue');
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.post(`${API}/gm/npc-speak`, {
      campaign_id: campaign.id,
      npc_name: name,
      dialogue_or_intent: dialogue
    });
    const embed = gmEmbed(data.npc_name, data.response, 0x8B5CF6);
    await interaction.editReply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleRoll(interaction) {
  const dice = interaction.options.getString('dice');
  const context = interaction.options.getString('context') || '';
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.post(`${API}/gm/roll`, {
      campaign_id: campaign.id,
      dice_expression: dice,
      context
    });
    let desc = data.formatted;
    if (context) desc += `\n*Context: ${context}*`;
    const color = data.result.is_critical ? 0x10B981 : data.result.is_fumble ? 0xEF4444 : 0x3B82F6;
    const embed = gmEmbed('Dice Roll', desc, color);
    await interaction.reply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.reply({ content: `**Error:** ${msg}`, ephemeral: true });
  }
}

async function handleCheck(interaction) {
  await interaction.deferReply();
  const difficulty = interaction.options.getString('difficulty');
  const context = interaction.options.getString('context');
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.post(`${API}/gm/check`, {
      campaign_id: campaign.id,
      difficulty,
      context
    });
    const status = data.passed ? 'PASSED' : 'FAILED';
    const color = data.is_critical ? 0x10B981 : data.is_fumble ? 0xEF4444 : data.passed ? 0x10B981 : 0xEF4444;
    let desc = `**${context}**\n${data.roll}\nDC: ${data.dc} | Result: **${status}**`;
    if (data.is_critical) desc += ' (CRITICAL!)';
    if (data.is_fumble) desc += ' (FUMBLE!)';
    desc += `\n\n${data.narrative}`;
    const embed = gmEmbed('Skill Check', desc, color);
    await interaction.editReply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleScene(interaction) {
  await interaction.deferReply();
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.get(`${API}/gm/scene-summary`, { params: { campaign_id: campaign.id } });
    if (data.summary) {
      await interaction.editReply({ content: data.summary });
      return;
    }
    const s = data.scene;
    let desc = `**Location:** ${s.location}\n**Time:** ${s.time_of_day || 'Unknown'}\n**Tension:** ${'|'.repeat(s.tension_level)}${'  '.repeat(10 - s.tension_level)} (${s.tension_level}/10)\n\n${s.description}`;
    if (s.active_threats?.length) desc += `\n\n**Active Threats:** ${s.active_threats.join(', ')}`;
    if (s.important_npcs?.length) desc += `\n**Present NPCs:** ${s.important_npcs.join(', ')}`;
    if (s.unresolved_hooks?.length) desc += `\n**Unresolved Hooks:** ${s.unresolved_hooks.join(', ')}`;
    const embed = gmEmbed(`Scene: ${s.location}`, truncate(desc), 0xF59E0B);
    await interaction.editReply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleRecap(interaction) {
  await interaction.deferReply();
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.post(`${API}/gm/generate-recap`, { campaign_id: campaign.id });
    const embed = gmEmbed('Session Recap', data.recap, 0xD97706);
    await interaction.editReply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleJournal(interaction) {
  await interaction.deferReply();
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.get(`${API}/events`, { params: { campaign_id: campaign.id, limit: 20 } });
    if (!data.length) {
      await interaction.editReply({ content: 'No events recorded yet.' });
      return;
    }
    let desc = '';
    for (const ev of data.slice(0, 20)) {
      const ts = ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '';
      desc += `\`${ev.event_type}\` ${ev.summary}${ts ? ` *(${ts})*` : ''}\n`;
    }
    const embed = gmEmbed('Campaign Journal', truncate(desc), 0x6366F1);
    await interaction.editReply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleRules(interaction) {
  await interaction.deferReply();
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.get(`${API}/rules`, { params: { campaign_id: campaign.id } });
    let desc = `**Dice System:** ${data.dice_system}\n**Critical Hits:** ${data.critical_enabled ? 'Enabled' : 'Disabled'}\n**Hidden Rolls:** ${data.hidden_rolls_enabled ? 'Enabled' : 'Disabled'}\n**Difficulty Classes:** ${data.difficulty_classes}`;
    if (data.content) desc += `\n\n**Custom Rules:**\n${data.content}`;
    const embed = gmEmbed('Active Rules', desc, 0x8B5CF6);
    await interaction.editReply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleSetTone(interaction) {
  const tone = interaction.options.getString('tone');
  try {
    const campaign = await getActiveCampaign();
    await axios.put(`${API}/campaigns/${campaign.id}`, { tone });
    const embed = gmEmbed('Tone Changed', `Narration tone set to **${tone}**. The world shifts accordingly...`, 0xF59E0B);
    await interaction.reply({ embeds: [embed] });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.reply({ content: `**Error:** ${msg}`, ephemeral: true });
  }
}

async function handleResetSession(interaction) {
  await interaction.deferReply({ ephemeral: true });
  try {
    const campaign = await getActiveCampaign();
    const { data } = await axios.post(`${API}/gm/reset-session`, { campaign_id: campaign.id });
    await interaction.editReply({ content: `Session reset. ${data.message}` });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleNewCampaign(interaction) {
  await interaction.deferReply({ ephemeral: true });
  const name = interaction.options.getString('name');
  const world = interaction.options.getString('world') || '';
  try {
    const { data } = await axios.post(`${API}/campaigns`, { name, world_summary: world });
    await interaction.editReply({ content: `Campaign **${data.name}** created and set as active.` });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.editReply({ content: `**Error:** ${msg}` });
  }
}

async function handleSetChannelMode(interaction) {
  const mode = interaction.options.getString('mode');
  try {
    const campaign = await getActiveCampaign();
    await axios.post(`${API}/channels`, {
      campaign_id: campaign.id,
      guild_id: interaction.guildId,
      channel_id: interaction.channelId,
      channel_name: interaction.channel?.name || '',
      mode
    });
    const labels = { ic: 'In-Character', ooc: 'Out-of-Character', admin: 'Admin' };
    await interaction.reply({ content: `This channel is now set to **${labels[mode] || mode}** mode.`, ephemeral: true });
  } catch (err) {
    const msg = err.response?.data?.detail || err.message;
    await interaction.reply({ content: `**Error:** ${msg}`, ephemeral: true });
  }
}

// ── Event Handlers ──

client.once('ready', async () => {
  console.log(`Bot online as ${client.user.tag}`);
  try {
    const rest = new REST().setToken(TOKEN);
    const body = commands.map(c => c.toJSON());
    if (GUILD_ID) {
      await rest.put(Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID), { body });
      console.log(`Registered ${body.length} guild commands for ${GUILD_ID}`);
    } else {
      await rest.put(Routes.applicationCommands(CLIENT_ID), { body });
      console.log(`Registered ${body.length} global commands`);
    }
  } catch (err) {
    console.error('Failed to register commands:', err);
  }
});

client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;

  // Guild whitelist check
  if (GUILD_ID && interaction.guildId !== GUILD_ID) {
    return interaction.reply({ content: 'This bot is not configured for this server.', ephemeral: true });
  }

  const handlers = {
    gm: handleGM,
    npc: handleNPC,
    roll: handleRoll,
    check: handleCheck,
    scene: handleScene,
    recap: handleRecap,
    journal: handleJournal,
    rules: handleRules,
    set_tone: handleSetTone,
    reset_session: handleResetSession,
    new_campaign: handleNewCampaign,
    set_channel_mode: handleSetChannelMode,
  };

  const handler = handlers[interaction.commandName];
  if (handler) {
    try {
      await handler(interaction);
    } catch (err) {
      console.error(`Error in /${interaction.commandName}:`, err);
      const reply = interaction.deferred || interaction.replied
        ? interaction.editReply.bind(interaction)
        : interaction.reply.bind(interaction);
      await reply({ content: 'An unexpected error occurred.', ephemeral: true }).catch(() => {});
    }
  }
});

client.on('error', err => console.error('Discord client error:', err));
process.on('unhandledRejection', err => console.error('Unhandled rejection:', err));

client.login(TOKEN);
