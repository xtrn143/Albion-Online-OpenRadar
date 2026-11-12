import {PlayersDrawing} from '../drawings/PlayersDrawing.js';
import {HarvestablesDrawing} from '../drawings/HarvestablesDrawing.js';
import {MobsDrawing} from '../drawings/MobsDrawing.js';
import {ChestsDrawing} from '../drawings/ChestsDrawing.js';
import {DungeonsDrawing} from '../drawings/DungeonsDrawing.js';
import {MapDrawing} from '../drawings/MapsDrawing.js';
import {WispCageDrawing} from '../drawings/WispCageDrawing.js';
import {MistsWispDrawing} from '../drawings/MistsWispDrawing.js';
import {FishingDrawing} from '../drawings/FishingDrawing.js';
import {MistsDungeonDrawing} from '../drawings/MistsDungeonDrawing.js';

import {PlayersHandler} from '../handlers/PlayersHandler.js';
import {WispCageHandler} from '../handlers/WispCageHandler.js';
import {FishingHandler} from '../handlers/FishingHandler.js';
import {MobsHandler} from '../handlers/MobsHandler.js';
import {ChestsHandler} from '../handlers/ChestsHandler.js';
import {HarvestablesHandler} from '../handlers/HarvestablesHandler.js';
import {MistsDungeonHandler} from '../handlers/MistsDungeonHandler.js';
import {MapH} from './Map.js';
import {DungeonsHandler} from '../handlers/DungeonsHandler.js';
import {DrawingUtils} from './DrawingUtils.js';
import {CATEGORIES} from '../constants/LoggerConstants.js';
import {createRadarRenderer} from './RadarRenderer.js';
import {destroyEventQueue, getEventQueue} from './WebSocketEventQueue.js';
import pictureInPictureManager from './PictureInPictureManager.js';
import settingsSync from './SettingsSync.js';
import {GatheringAdvisor} from './GatheringAdvisor.js';
import {GatheringDrawing} from '../drawings/GatheringDrawing.js';
import * as GatheringPanel from '../core/GatheringPanel.js';

import * as WebSocketManager from '../core/WebSocketManager.js';
import * as DatabaseLoader from '../core/DatabaseLoader.js';
import * as EventRouter from '../core/EventRouter.js';
import * as PlayerListRenderer from '../core/PlayerListRenderer.js';

let isInitialized = false;
let isDestroying = false;
let radarRenderer = null;
let eventQueue = null;
let playerListIntervalId = null;
let cleanupIntervalId = null;
let gatheringIntervalId = null;
let buttonClickHandler = null;
let lastPlayerListHash = '';

let handlers = {
    harvestables: null, mobs: null, players: null, chests: null,
    dungeons: null, wispCage: null, fishing: null, mistsDungeon: null,
    gatheringAdvisor: null
};

let drawings = {
    harvestables: null, mobs: null, players: null, chests: null,
    dungeons: null, wispCage: null, mistsWisp: null, fishing: null, maps: null,
    mistsDungeon: null, gathering: null
};

let drawingUtils = null;
let map = null;

const STALE_ENTITY_MAX_AGE = 300000;

function cleanupStaleEntities() {
    const cleanedPlayers = handlers.players?.cleanupStaleEntities?.(STALE_ENTITY_MAX_AGE) || 0;
    const cleanedMobs = handlers.mobs?.cleanupStaleEntities?.(STALE_ENTITY_MAX_AGE) || 0;
    const cleanedHarvestables = handlers.harvestables?.cleanupStaleEntities?.(STALE_ENTITY_MAX_AGE) || 0;
    const cleanedFishing = handlers.fishing?.cleanupStaleEntities?.(STALE_ENTITY_MAX_AGE) || 0;

    const activePlayerIds = new Set(handlers.players?.getFilteredPlayers?.().map(p => p.id) || []);
    const cleanedRenderCache = PlayerListRenderer.cleanupStaleCache(activePlayerIds);

    if (cleanedPlayers || cleanedMobs || cleanedHarvestables || cleanedFishing || cleanedRenderCache) {
        window.logger?.debug(CATEGORIES.SYSTEM, 'StaleEntityCleanup', {
            players: cleanedPlayers,
            mobs: cleanedMobs,
            harvestables: cleanedHarvestables,
            fishing: cleanedFishing,
            renderCache: cleanedRenderCache
        });
    }
}

function initializeRadarRenderer() {
    const canvas = document.getElementById('drawCanvas');
    const context = canvas?.getContext('2d');

    if (!canvas || !context) {
        window.logger?.debug(CATEGORIES.MAP, 'NoCanvasFound', {});
        return false;
    }

    if (radarRenderer) {
        radarRenderer.stop();
    }

    radarRenderer = createRadarRenderer({
        handlers: {
            harvestablesHandler: handlers.harvestables,
            mobsHandler: handlers.mobs,
            playersHandler: handlers.players,
            chestsHandler: handlers.chests,
            dungeonsHandler: handlers.dungeons,
            wispCageHandler: handlers.wispCage,
            fishingHandler: handlers.fishing,
            mistsDungeonHandler: handlers.mistsDungeon,
            gatheringAdvisor: handlers.gatheringAdvisor
        },
        drawings: {
            mapsDrawing: drawings.maps,
            harvestablesDrawing: drawings.harvestables,
            mobsDrawing: drawings.mobs,
            playersDrawing: drawings.players,
            chestsDrawing: drawings.chests,
            dungeonsDrawing: drawings.dungeons,
            wispCageDrawing: drawings.wispCage,
            fishingDrawing: drawings.fishing,
            mistsWispDrawing: drawings.mistsWisp,
            mistsDungeonDrawing: drawings.mistsDungeon,
            gatheringDrawing: drawings.gathering
        },
        drawingUtils
    });

    radarRenderer.initialize();
    radarRenderer.setMap(map);
    window.radarRenderer = radarRenderer;
    radarRenderer.start();

    window.logger?.info(CATEGORIES.MAP, 'RadarRendererStarted', {});
    return true;
}

function clearHandlers(preserveSession = false) {
    handlers.chests.chestsList = [];
    handlers.dungeons.dungeonList = [];
    handlers.fishing.Clear();
    handlers.harvestables.Clear();
    handlers.mobs.Clear();
    handlers.players.Clear();
    handlers.wispCage.Clear();
    handlers.gatheringAdvisor?.reset?.();
    handlers.players?.setGatheringState?.(false);

    if (!preserveSession) {
        try {
            sessionStorage.removeItem('lastMapDisplayed');
        } catch (e) {
            window.logger?.warn(CATEGORIES.MAP, 'SessionStorageClearFailed', {error: e?.message});
        }
    }
}

export async function initRadar() {
    if (isInitialized) {
        window.logger?.warn(CATEGORIES.SYSTEM, 'RadarAlreadyInitialized', {});
        return;
    }

    while (isDestroying) {
        await new Promise(resolve => setTimeout(resolve, 10));
    }

    window.logger?.info(CATEGORIES.SYSTEM, 'RadarInitializing', {});

    try {
        await DatabaseLoader.load();

        drawingUtils = new DrawingUtils();
        map = new MapH(-1);

        handlers.dungeons = new DungeonsHandler();
        handlers.chests = new ChestsHandler();
        handlers.mobs = new MobsHandler();
        handlers.harvestables = new HarvestablesHandler(handlers.mobs);
        handlers.players = new PlayersHandler();
        handlers.wispCage = new WispCageHandler();
        handlers.fishing = new FishingHandler();
        handlers.mistsDungeon = new MistsDungeonHandler();
        handlers.gatheringAdvisor = new GatheringAdvisor();

        drawings.maps = new MapDrawing();
        drawings.harvestables = new HarvestablesDrawing();
        drawings.mobs = new MobsDrawing();
        drawings.players = new PlayersDrawing();
        drawings.chests = new ChestsDrawing();
        drawings.dungeons = new DungeonsDrawing();
        drawings.wispCage = new WispCageDrawing();
        drawings.mistsWisp = new MistsWispDrawing();
        drawings.fishing = new FishingDrawing();
        drawings.mistsDungeon = new MistsDungeonDrawing();
        drawings.gathering = new GatheringDrawing();

        window.harvestablesHandler = handlers.harvestables;
        window.mobsHandler = handlers.mobs;
        window.playersHandler = handlers.players;
        window.handlers = handlers;

        EventRouter.init({
            handlers: {
                playersHandler: handlers.players,
                mobsHandler: handlers.mobs,
                harvestablesHandler: handlers.harvestables,
                chestsHandler: handlers.chests,
                dungeonsHandler: handlers.dungeons,
                fishingHandler: handlers.fishing,
                wispCageHandler: handlers.wispCage,
                mistsDungeonHandler: handlers.mistsDungeon
            },
            map,
            radarRenderer: null
        });

        EventRouter.restoreMistOverrideFromSession();
        EventRouter.restoreMapFromSession();

        WebSocketManager.setMessageCallback((data) => {
            eventQueue.queueRawMessage(data);
        });
        WebSocketManager.connect();

        eventQueue = getEventQueue();
        eventQueue.setFlushCallback((messageType, params) => {
            switch (messageType) {
                case 'request':
                    EventRouter.onRequest(params);
                    break;
                case 'event':
                    EventRouter.onEvent(params);
                    break;
                case 'response':
                    EventRouter.onResponse(params, () => clearHandlers(true));
                    break;
            }
        });

        initializeRadarRenderer();
        EventRouter.setRadarRenderer(radarRenderer);

        playerListIntervalId = setInterval(() => {
            const players = handlers.players?.getFilteredPlayers?.() || [];
            const hasDeparted = players.some(p => p.leftAt);
            const timeBucket = hasDeparted ? Math.floor(Date.now() / 1000) : '';
            const hash = `${players.length}:${timeBucket}:` + players.map(p => `${p.id}:${p.currentHealth}:${p.mounted ? 1 : 0}:${p.leftAt ?? ''}`).join(',');
            if (hash !== lastPlayerListHash) {
                lastPlayerListHash = hash;
                PlayerListRenderer.update(handlers.players);
            }
        }, 1500);

        GatheringPanel.init(handlers.gatheringAdvisor);

        gatheringIntervalId = setInterval(() => {
            const advisor = handlers.gatheringAdvisor;
            if (!advisor || !handlers.harvestables) return;
            const local = handlers.players?.localPlayer;
            const playerPos = Number.isFinite(local?.posX) && Number.isFinite(local?.posY)
                ? {x: local.posX, y: local.posY}
                : {x: 0, y: 0};
            const settings = {
                mode: settingsSync.get('settingGatheringSort', 'nearest'),
                maxTargets: settingsSync.getNumber('settingGatheringMaxTargets', 5),
            };
            advisor.update(handlers.harvestables.harvestableList, playerPos, settings);
            const gameMode = settingsSync.getGatheringMode();
            handlers.players?.setGatheringState?.(gameMode !== 'roam' && advisor.isGathering);
            GatheringPanel.update(advisor);
        }, 1000);

        cleanupIntervalId = setInterval(cleanupStaleEntities, 60000);

        const buttonElement = document.getElementById('button');
        if (buttonElement) {
            buttonClickHandler = () => clearHandlers();
            buttonElement.addEventListener('click', buttonClickHandler);
        }

        isInitialized = true;
        window.logger?.info(CATEGORIES.SYSTEM, 'RadarInitialized', {});

        if (pictureInPictureManager.isSupported()) {
            pictureInPictureManager.initialize(radarRenderer.canvasManager);
            window.pipManager = pictureInPictureManager;
            document.dispatchEvent(new CustomEvent('pipManagerReady'));
            window.logger?.info(CATEGORIES.SYSTEM, 'PiPManagerInitialized', {});
        }

    } catch (error) {
        window.logger?.error(CATEGORIES.SYSTEM, 'RadarInitFailed', {error: error.message});
        if (window.toast) window.toast.error('Failed to initialize radar');
        throw error;
    }
}

export function destroyRadar() {
    if (!isInitialized) {
        window.logger?.warn(CATEGORIES.SYSTEM, 'RadarNotInitialized', {});
        return;
    }

    isDestroying = true;
    window.logger?.info(CATEGORIES.SYSTEM, 'RadarDestroying', {});

    const buttonElement = document.getElementById('button');
    if (buttonElement && buttonClickHandler) {
        buttonElement.removeEventListener('click', buttonClickHandler);
        buttonClickHandler = null;
    }

    if (playerListIntervalId) {
        clearInterval(playerListIntervalId);
        playerListIntervalId = null;
    }
    if (cleanupIntervalId) {
        clearInterval(cleanupIntervalId);
        cleanupIntervalId = null;
    }
    if (gatheringIntervalId) {
        clearInterval(gatheringIntervalId);
        gatheringIntervalId = null;
    }
    GatheringPanel.destroy();

    if (window.pipManager) {
        pictureInPictureManager.destroy();
        window.pipManager = null;
    }

    if (radarRenderer) {
        radarRenderer.stop();
        radarRenderer = null;
    }

    destroyEventQueue();
    eventQueue = null;

    WebSocketManager.disconnect();
    clearHandlers(true);

    Object.keys(handlers).forEach(k => handlers[k] = null);
    Object.keys(drawings).forEach(k => drawings[k] = null);
    drawingUtils = null;
    map = null;

    window.harvestablesHandler = null;
    window.mobsHandler = null;
    window.playersHandler = null;
    window.handlers = null;
    window.radarRenderer = null;

    PlayerListRenderer.reset();
    EventRouter.reset();
    lastPlayerListHash = '';

    isInitialized = false;
    isDestroying = false;
    window.logger?.info(CATEGORIES.SYSTEM, 'RadarDestroyed', {});
}

window.addEventListener('beforeunload', () => {
    if (isInitialized) destroyRadar();
});
