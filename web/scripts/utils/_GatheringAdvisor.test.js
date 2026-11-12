import {describe, test, expect, beforeEach, vi} from 'vitest';

vi.mock('./SettingsSync.js', () => ({
    default: {
        get: vi.fn((_k, d) => d),
        getBool: vi.fn((_k, d) => d ?? true),
        getNumber: vi.fn((_k, d) => d),
        getFloat: vi.fn((_k, d) => d),
        getJSON: vi.fn(() => null),
    },
}));

vi.mock('./LivingResourceFilter.js', () => ({
    shouldRenderStaticResource: vi.fn(() => true),
    shouldRenderLivingResource: vi.fn(() => true),
}));

const {buildTargets, rotateIsometric, toScreenVector} = await import('./GatheringAdvisor.js');

const PLAYER = {x: 1000, y: 1000};
const node = (id, dx, dy, overrides = {}) => ({
    id,
    posX: PLAYER.x + dx,
    posY: PLAYER.y + dy,
    tier: 4,
    charges: 0,
    size: 3,
    stringType: 'Log',
    mobileTypeId: null,
    ...overrides,
});

describe('buildTargets', () => {
    beforeEach(() => vi.clearAllMocks());

    test('就近模式按距离从近到远排序', () => {
        const targets = buildTargets({
            harvestables: [node(1, 50, 0), node(2, 10, 0), node(3, 30, 0)],
            playerPos: PLAYER,
            mode: 'nearest',
            filter: () => true,
        });

        expect(targets.map(t => t.id)).toEqual([2, 3, 1]);
    });

    test('高级模式优先高 tier 而非最近', () => {
        const targets = buildTargets({
            harvestables: [node(1, 10, 0, {tier: 2}), node(2, 40, 0, {tier: 8})],
            playerPos: PLAYER,
            mode: 'tier',
            filter: () => true,
        });

        expect(targets[0].id).toBe(2);
    });

    test('剔除已采空、超出 80 距离与未通过筛选的节点', () => {
        const targets = buildTargets({
            harvestables: [
                node(1, 10, 0, {size: 0}),
                node(2, 90, 0),
                node(3, 10, 0),
            ],
            playerPos: PLAYER,
            mode: 'nearest',
            filter: h => h.id !== 3,
        });

        expect(targets).toHaveLength(0);
    });

    test('坐标缺失时不给距离，按 tier 排序', () => {
        const targets = buildTargets({
            harvestables: [node(1, 10, 0, {tier: 2}), node(2, 10, 0, {tier: 8})],
            playerPos: {x: 0, y: 0},
            mode: 'nearest',
            filter: () => true,
        });

        expect(targets[0].id).toBe(2);
        expect(targets[0].distance).toBeNull();
        expect(targets[0].bearingDeg).toBeNull();
    });

    test('方位角在屏幕空间计算：世界正东对应画布 45 度', () => {
        const {x, y} = toScreenVector({posX: PLAYER.x + 10, posY: PLAYER.y}, PLAYER);
        expect(x).toBeGreaterThan(0);
        expect(y).toBeGreaterThan(0);

        const targets = buildTargets({
            harvestables: [node(1, 10, 0)],
            playerPos: PLAYER,
            mode: 'nearest',
            filter: () => true,
        });
        expect(targets[0].bearingDeg).toBeCloseTo(45, 0);
    });

    test('rotateIsometric 保持与雷达一致的 -45 度变换', () => {
        const rotated = rotateIsometric(10, 0);
        expect(rotated.x).toBeCloseTo(-7.85398, 4);
        expect(rotated.y).toBeCloseTo(-7.85398, 4);
    });
});
