import {describe, test, expect, beforeEach, vi} from 'vitest';
import {loadFixture, normalizeParams} from '../__fixtures__/loader.js';
import {loadRealItemsDatabase} from '../__fixtures__/realDatabases.js';

vi.mock('../utils/SettingsSync.js', () => ({
    default: {
        getBool: vi.fn(() => true),
        getNumber: vi.fn((_k, d) => d),
        getJSON: vi.fn(() => null),
    },
}));

vi.mock('../data/ZonesDatabase.js', () => ({
    default: {
        getPvpType: vi.fn(() => 'safe'),
    },
}));

const {PlayersHandler} = await import('../handlers/PlayersHandler.js');

// pcap-derived: the equipment fixture from the 2026-07-24 capture
// synthetic: the spawn parameters that seed the player before the equipment message

describe('player equipment resolves to the correct items', () => {
    let handler;

    beforeEach(() => {
        window.logger = {debug: vi.fn(), info: vi.fn(), warn: vi.fn(), error: vi.fn()};
        window.currentMapId = 'safe-zone-01';
        window.itemsDatabase = loadRealItemsDatabase();
        window.settingsSync = {getBool: () => true};
        handler = new PlayersHandler();
    });

    // @verified 2026-09-03: the head, armor and shoes slots of a real player resolve to armour, not weapons.
    // Same T4.1 set as the 2026-08-02 capture, now carried by its Dragonfire ids.
    test('pcap-derived equipment resolves to the gear set the player wore', async () => {
        const fx = await loadFixture('players', 'equipment');
        const msg = fx.messages[0];
        const id = msg.parameters['0'];

        handler.handleNewPlayerEvent(id, {1: 'Geared', 8: '', 53: 0, 51: null, 40: [], 43: []});
        handler.updateItems(id, normalizeParams(msg.parameters));

        const player = handler.playersList[0];
        const resolved = player.equipments.map(itemId => window.itemsDatabase.getItemById(itemId)?.name ?? null);

        expect(resolved[2]).toBe('T4_HEAD_LEATHER_SET2@1');
        expect(resolved[3]).toBe('T4_ARMOR_LEATHER_SET1@1');
        expect(resolved[4]).toBe('T4_SHOES_PLATE_SET3@1');
        expect(resolved[7]).toBe('T4_MOUNT_HORSE');
    });

    // @verified 2026-08-02: each combat slot carries its own item power, so a wrong mapping cannot hide inside the average.
    test('pcap-derived equipment yields an item power from the combat slots', async () => {
        const fx = await loadFixture('players', 'equipment');
        const msg = fx.messages[0];
        const id = msg.parameters['0'];

        handler.handleNewPlayerEvent(id, {1: 'Geared', 8: '', 53: 0, 51: null, 40: [], 43: []});
        handler.updateItems(id, normalizeParams(msg.parameters));

        const equipment = handler.playersList[0].equipments;
        const itemPower = index => window.itemsDatabase.getItemById(equipment[index])?.itempower ?? null;

        expect(itemPower(0)).toBe(800);
        expect(itemPower(1)).toBe(800);
        expect(itemPower(2)).toBe(800);
        expect(itemPower(3)).toBe(800);
        expect(itemPower(4)).toBe(800);

        const ip = handler.playersList[0].getAverageItemPower();
        expect(ip).toBe(800);
    });

    // @verified 2026-08-02: the rendered markup carries the icon path of the head slot item.
    test('rendered markup points at the head slot icon', async () => {
        const renderer = await import('./PlayerListRenderer.js');
        const fx = await loadFixture('players', 'equipment');
        const msg = fx.messages[0];
        const id = msg.parameters['0'];

        handler.handleNewPlayerEvent(id, {1: 'Geared', 8: '', 53: 0, 51: null, 40: [], 43: []});
        handler.updateItems(id, normalizeParams(msg.parameters));

        document.body.innerHTML = '<div id="playersList"><div id="playersPassive"><div id="passiveList"></div></div></div>';
        renderer.reset();
        renderer.update(handler);
        await new Promise(resolve => requestAnimationFrame(resolve));

        expect(document.body.innerHTML).toContain('/images/Items/T4_HEAD_LEATHER_SET2.webp');
    });

    // @verified 2026-11-12: 玩家回流后复用同一张卡片，opacity-50 必须被移除，否则"已离开"样式会残留。
    test('departed card loses opacity-50 when the same player returns', async () => {
        const renderer = await import('./PlayerListRenderer.js');
        const id = 4242;

        handler.handleNewPlayerEvent(id, {1: 'Returner', 8: '', 53: 0, 51: null, 40: [], 43: []});
        handler.removePlayer(id);

        document.body.innerHTML = '<div id="playersList"><div id="playersPassive"><div id="passiveList"></div></div></div>';
        renderer.reset();
        renderer.update(handler);
        await new Promise(resolve => requestAnimationFrame(resolve));

        const card = document.querySelector(`[data-player-id="${id}"]`);
        expect(card.classList.contains('opacity-50')).toBe(true);

        handler.playersList[0].leftAt = null;
        renderer.update(handler);
        await new Promise(resolve => requestAnimationFrame(resolve));

        expect(card.classList.contains('opacity-50')).toBe(false);
    });
});
