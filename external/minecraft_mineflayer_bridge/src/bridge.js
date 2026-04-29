'use strict';

const net = require('net');
const mineflayer = require('mineflayer');

const BRIDGE_HOST = process.env.BRIDGE_HOST || '127.0.0.1';
const BRIDGE_PORT = Number(process.env.BRIDGE_PORT || 4711);
const MC_HOST = process.env.MC_HOST || 'localhost';
const MC_PORT = Number(process.env.MC_PORT || 25565);
const MC_USERNAME = process.env.MC_USERNAME || 'AgentGirl';
const MC_VERSION = process.env.MC_VERSION || '1.20.1';
const MC_AUTH = process.env.MC_AUTH || 'offline';
const BLOCK_RADIUS = Number(process.env.BLOCK_RADIUS || 3);
const ENTITY_RADIUS = Number(process.env.ENTITY_RADIUS || 16);
const MAX_PULSE_MS = Number(process.env.MAX_PULSE_MS || 500);
const DEFAULT_PULSE_MS = Number(process.env.DEFAULT_PULSE_MS || 120);

let bot = null;
let connectionState = 'starting';
let lastError = null;
const activeTimers = new Set();

function log(message, data) {
  const suffix = data === undefined ? '' : ` ${JSON.stringify(data)}`;
  console.log(`[mineflayer-bridge] ${message}${suffix}`);
}

function createBot() {
  connectionState = 'connecting';
  bot = mineflayer.createBot({
    host: MC_HOST,
    port: MC_PORT,
    username: MC_USERNAME,
    version: MC_VERSION,
    auth: MC_AUTH
  });

  bot.once('spawn', () => {
    connectionState = 'spawned';
    lastError = null;
    log('bot spawned', { host: MC_HOST, port: MC_PORT, username: MC_USERNAME, version: MC_VERSION });
  });

  bot.on('end', (reason) => {
    releaseAllControls();
    connectionState = 'ended';
    log('bot ended', { reason });
  });

  bot.on('kicked', (reason) => {
    releaseAllControls();
    connectionState = 'kicked';
    lastError = String(reason);
    log('bot kicked', { reason: lastError });
  });

  bot.on('error', (error) => {
    releaseAllControls();
    connectionState = 'error';
    lastError = error && error.message ? error.message : String(error);
    log('bot error', { error: lastError });
  });
}

function releaseAllControls() {
  for (const timer of activeTimers) {
    clearTimeout(timer);
  }
  activeTimers.clear();
  if (!bot) return;
  for (const control of ['forward', 'back', 'left', 'right', 'jump', 'sneak', 'sprint']) {
    try {
      bot.setControlState(control, false);
    } catch (_) {
      // Ignore release errors while the bot is disconnecting.
    }
  }
}

function pulse(control, durationMs) {
  if (!bot || !bot.entity) return;
  const safeDuration = clampNumber(durationMs || DEFAULT_PULSE_MS, 20, MAX_PULSE_MS);
  bot.setControlState(control, true);
  const timer = setTimeout(() => {
    activeTimers.delete(timer);
    if (bot) bot.setControlState(control, false);
  }, safeDuration);
  activeTimers.add(timer);
}

function clampNumber(value, min, max) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return min;
  return Math.max(min, Math.min(max, numeric));
}

function finiteOrNull(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function vectorSnapshot(vector) {
  return {
    x: finiteOrNull(vector && vector.x),
    y: finiteOrNull(vector && vector.y),
    z: finiteOrNull(vector && vector.z)
  };
}

function vectorArray(vector) {
  const snapshot = vectorSnapshot(vector);
  return [snapshot.x, snapshot.y, snapshot.z];
}

function vectorIsFinite(vector) {
  return Boolean(
    vector &&
    Number.isFinite(Number(vector.x)) &&
    Number.isFinite(Number(vector.y)) &&
    Number.isFinite(Number(vector.z))
  );
}

function safeDistance(a, b) {
  if (!vectorIsFinite(a) || !vectorIsFinite(b) || typeof a.distanceTo !== 'function') return null;
  const distance = a.distanceTo(b);
  return finiteOrNull(distance);
}

function degToRad(value) {
  return (Number(value) || 0) * Math.PI / 180;
}

function heldItemName() {
  if (!bot || !bot.heldItem) return 'minecraft:air';
  return normalizeItemName(bot.heldItem.name);
}

function normalizeItemName(name) {
  if (!name) return 'minecraft:air';
  return name.includes(':') ? name : `minecraft:${name}`;
}

function inventorySummary() {
  if (!bot || !bot.inventory) return [];
  const counts = new Map();
  for (const item of bot.inventory.items()) {
    const itemId = normalizeItemName(item.name);
    const current = counts.get(itemId) || { item_id: itemId, count: 0, slot: item.slot };
    current.count += item.count;
    counts.set(itemId, current);
  }
  return Array.from(counts.values());
}

function nearbyEntities() {
  if (!bot || !bot.entity || !bot.entities) return [];
  const origin = bot.entity.position;
  if (!vectorIsFinite(origin)) return [];
  return Object.values(bot.entities)
    .filter((entity) => entity && entity.position && entity.id !== bot.entity.id)
    .map((entity) => {
      const distance = safeDistance(origin, entity.position);
      return {
        entity_id: String(entity.id),
        kind: entity.name || entity.type || 'unknown',
        x: finiteOrNull(entity.position.x),
        y: finiteOrNull(entity.position.y),
        z: finiteOrNull(entity.position.z),
        distance,
        hostile: isHostile(entity)
      };
    })
    .filter((entity) => entity.distance !== null && entity.distance <= ENTITY_RADIUS)
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 24);
}

function nearbyPlayers() {
  if (!bot || !bot.players || !bot.entity) return [];
  const origin = bot.entity.position;
  if (!vectorIsFinite(origin)) return [];
  return Object.entries(bot.players)
    .map(([username, player]) => {
      const entity = player.entity;
      if (!entity || !entity.position) return null;
      const distance = safeDistance(origin, entity.position);
      if (distance === null) return null;
      return {
        username,
        entity_id: String(entity.id),
        x: finiteOrNull(entity.position.x),
        y: finiteOrNull(entity.position.y),
        z: finiteOrNull(entity.position.z),
        distance
      };
    })
    .filter((player) => player && player.username !== bot.username && player.distance <= ENTITY_RADIUS)
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 12);
}

function nearbyBlocks() {
  if (!bot || !bot.entity || !bot.blockAt) return [];
  const origin = bot.entity.position;
  if (!vectorIsFinite(origin)) return [];
  const base = origin.floored();
  const blocks = [];
  for (let dx = -BLOCK_RADIUS; dx <= BLOCK_RADIUS; dx += 1) {
    for (let dy = -1; dy <= 2; dy += 1) {
      for (let dz = -BLOCK_RADIUS; dz <= BLOCK_RADIUS; dz += 1) {
        const pos = base.offset(dx, dy, dz);
        const block = bot.blockAt(pos, false);
        if (!block || block.name === 'air') continue;
        blocks.push({
          block_id: normalizeItemName(block.name),
          x: pos.x,
          y: pos.y,
          z: pos.z,
          distance: safeDistance(origin, pos)
        });
      }
    }
  }
  return blocks
    .filter((block) => block.distance !== null)
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 96);
}

function isHostile(entity) {
  const name = String(entity.name || '').toLowerCase();
  return ['zombie', 'skeleton', 'creeper', 'spider', 'enderman', 'witch', 'slime', 'drowned'].some((item) => name.includes(item));
}

function observation(events = []) {
  const spawned = bot && bot.entity;
  const position = spawned ? bot.entity.position : { x: 0, y: 0, z: 0 };
  const velocity = spawned ? bot.entity.velocity : { x: 0, y: 0, z: 0 };
  const positionValid = vectorIsFinite(position);
  const controlState = bot && bot.controlState ? bot.controlState : {};
  return {
    tick: bot && bot.time ? bot.time.age : 0,
    time: Date.now(),
    hp: bot && typeof bot.health === 'number' ? bot.health : 0,
    hunger: bot && typeof bot.food === 'number' ? bot.food : 0,
    food: bot && typeof bot.food === 'number' ? bot.food : 0,
    armor: 0,
    air: bot && typeof bot.oxygenLevel === 'number' ? bot.oxygenLevel : 300,
    position: vectorArray(position),
    position_vector: vectorSnapshot(position),
    position_valid: positionValid,
    velocity: vectorSnapshot(velocity),
    yaw: spawned ? finiteOrNull(bot.entity.yaw) : 0,
    pitch: spawned ? finiteOrNull(bot.entity.pitch) : 0,
    on_ground: spawned ? Boolean(bot.entity.onGround) : false,
    physics_enabled: bot ? Boolean(bot.physicsEnabled) : false,
    control_state: {
      forward: Boolean(controlState.forward),
      back: Boolean(controlState.back),
      left: Boolean(controlState.left),
      right: Boolean(controlState.right),
      jump: Boolean(controlState.jump),
      sneak: Boolean(controlState.sneak),
      sprint: Boolean(controlState.sprint)
    },
    selected_slot: bot && typeof bot.quickBarSlot === 'number' ? bot.quickBarSlot : 0,
    item_in_hand: heldItemName(),
    biome: 'unknown',
    time_of_day: bot && bot.time ? bot.time.timeOfDay : 0,
    inventory: inventorySummary(),
    nearby_entities: nearbyEntities(),
    nearby_players: nearbyPlayers(),
    nearby_blocks: nearbyBlocks(),
    connection_state: connectionState,
    username: bot ? bot.username : MC_USERNAME,
    last_error: lastError,
    events
  };
}

async function applyAction(payload) {
  if (!bot || !bot.entity) {
    return observation(['action_ignored:not_spawned']);
  }

  const command = String(payload.command || inferCommand(payload) || 'noop');
  const durationMs = clampNumber(payload.duration_ms || payload.durationMs || DEFAULT_PULSE_MS, 20, MAX_PULSE_MS);
  const movementCommands = new Set(['move_forward', 'move_back', 'move_left', 'move_right', 'jump', 'sneak', 'sprint']);
  if (movementCommands.has(command) && !vectorIsFinite(bot.entity.position)) {
    return observation([`action_ignored:invalid_position:${command}`]);
  }

  switch (command) {
    case 'noop':
      break;
    case 'move_forward':
      pulse('forward', durationMs);
      break;
    case 'move_back':
      pulse('back', durationMs);
      break;
    case 'move_left':
      pulse('left', durationMs);
      break;
    case 'move_right':
      pulse('right', durationMs);
      break;
    case 'jump':
      pulse('jump', durationMs);
      break;
    case 'sneak':
      pulse('sneak', durationMs);
      break;
    case 'sprint':
      pulse('sprint', durationMs);
      pulse('forward', durationMs);
      break;
    case 'look_delta':
      await lookDelta(payload);
      break;
    case 'chat':
      if (typeof payload.chat_message === 'string' && payload.chat_message.trim()) {
        bot.chat(payload.chat_message.slice(0, 240));
      }
      break;
    case 'stop':
      releaseAllControls();
      break;
    default:
      return observation([`action_ignored:unknown_command:${command}`]);
  }

  return observation([`action:${command}`]);
}

function inferCommand(payload) {
  if (payload.forward > 0) return 'move_forward';
  if (payload.forward < 0) return 'move_back';
  if (payload.strafe < 0) return 'move_left';
  if (payload.strafe > 0) return 'move_right';
  if (payload.jump) return 'jump';
  if (payload.sneak) return 'sneak';
  if (payload.sprint) return 'sprint';
  if (payload.camera_yaw_delta || payload.camera_pitch_delta) return 'look_delta';
  return 'noop';
}

async function lookDelta(payload) {
  const yawDelta = degToRad(payload.camera_yaw_delta || payload.yaw_delta || 0);
  const pitchDelta = degToRad(payload.camera_pitch_delta || payload.pitch_delta || 0);
  const yaw = bot.entity.yaw + yawDelta;
  const pitch = clampNumber(bot.entity.pitch + pitchDelta, -Math.PI / 2, Math.PI / 2);
  await bot.look(yaw, pitch, true);
}

async function handleRequest(request) {
  const type = request.type;
  const payload = request.payload || {};
  if (type === 'ping') {
    return { message: 'ok', connection_state: connectionState, bot_spawned: Boolean(bot && bot.entity) };
  }
  if (type === 'reset') {
    releaseAllControls();
    return observation(['reset']);
  }
  if (type === 'observe') {
    return observation(['observe']);
  }
  if (type === 'action') {
    return applyAction(payload);
  }
  if (type === 'close' || type === 'stop') {
    releaseAllControls();
    return observation(['closed']);
  }
  throw new Error(`unsupported request: ${type}`);
}

function writeResponse(socket, response) {
  socket.write(`${JSON.stringify(response)}\n`);
}

function startTcpServer() {
  const server = net.createServer((socket) => {
    socket.setEncoding('utf8');
    let buffer = '';

    socket.on('data', (chunk) => {
      buffer += chunk;
      let newlineIndex = buffer.indexOf('\n');
      while (newlineIndex !== -1) {
        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);
        newlineIndex = buffer.indexOf('\n');
        if (!line) continue;
        processLine(socket, line);
      }
    });
  });

  server.listen(BRIDGE_PORT, BRIDGE_HOST, () => {
    log('tcp server listening', { host: BRIDGE_HOST, port: BRIDGE_PORT });
  });

  process.on('SIGINT', () => shutdown(server));
  process.on('SIGTERM', () => shutdown(server));
}

async function processLine(socket, line) {
  try {
    const request = JSON.parse(line);
    const payload = await handleRequest(request);
    writeResponse(socket, { ok: true, payload });
  } catch (error) {
    writeResponse(socket, { ok: false, error: error && error.message ? error.message : String(error) });
  }
}

function shutdown(server) {
  releaseAllControls();
  connectionState = 'closing';
  server.close(() => {
    if (bot) bot.end();
    process.exit(0);
  });
}

createBot();
startTcpServer();
