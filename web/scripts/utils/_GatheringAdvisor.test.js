import {describe, test, expect, beforeEach, vi} from 'vitest';
import {shouldRenderStaticResource, shouldRenderLivingResource} from './LivingResourceFilter.js';

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
    beforeEach(() => {
        vi.clearAllMocks();
        shouldRenderStaticResource.mockReturnValue(true);
        shouldRenderLivingResource.mockReturnValue(true);
    });

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

    test('maxTargets 截断返回结果且保持排序', () => {
        const harvestables = [
            node(1, 60, 0),
            node(2, 10, 0),
            node(3, 50, 0),
            node(4, 20, 0),
            node(5, 40, 0),
            node(6, 30, 0),
        ];

        const defaultLimit = buildTargets({
            harvestables,
            playerPos: PLAYER,
            mode: 'nearest',
            filter: () => true,
        });
        expect(defaultLimit).toHaveLength(5);
        expect(defaultLimit.map(t => t.id)).toEqual([2, 4, 6, 5, 3]);

        const customLimit = buildTargets({
            harvestables,
            playerPos: PLAYER,
            mode: 'nearest',
            maxTargets: 2,
            filter: () => true,
        });
        expect(customLimit).toHaveLength(2);
        expect(customLimit.map(t => t.id)).toEqual([2, 4]);
    });

    test('距离等于 80 保留，超过 80 剔除', () => {
        const atRange = buildTargets({
            harvestables: [node(1, 80, 0)],
            playerPos: PLAYER,
            filter: () => true,
        });
        expect(atRange).toHaveLength(1);

        const beyondRange = buildTargets({
            harvestables: [node(1, 80.1, 0)],
            playerPos: PLAYER,
            filter: () => true,
        });
        expect(beyondRange).toHaveLength(0);
    });

    test('空输入返回空数组', () => {
        expect(buildTargets({harvestables: [], playerPos: PLAYER})).toEqual([]);
        expect(buildTargets({harvestables: undefined, playerPos: PLAYER})).toEqual([]);
    });

    test('非法 mode 回退到 nearest 权重', () => {
        const harvestables = [node(1, 50, 0, {tier: 6}), node(2, 10, 0), node(3, 30, 0)];

        const nearest = buildTargets({
            harvestables,
            playerPos: PLAYER,
            mode: 'nearest',
            filter: () => true,
        });
        const fallback = buildTargets({
            harvestables,
            playerPos: PLAYER,
            mode: 'nope',
            filter: () => true,
        });

        expect(fallback.map(t => t.id)).toEqual(nearest.map(t => t.id));
        expect(fallback.map(t => t.score)).toEqual(nearest.map(t => t.score));
    });

    test('并列分数时按距离更近者在前，再按 id 升序', () => {
        const byDistance = buildTargets({
            harvestables: [node(1, 30, 0), node(2, 10, 0)],
            playerPos: PLAYER,
            mode: 'nearest',
            filter: () => true,
        });
        expect(byDistance.map(t => t.id)).toEqual([2, 1]);

        const tied = buildTargets({
            harvestables: [node(9, 10, 0), node(4, 10, 0)],
            playerPos: PLAYER,
            mode: 'nearest',
            filter: () => true,
        });
        expect(tied[0].score).toBe(tied[1].score);
        expect(tied.map(t => t.id)).toEqual([4, 9]);

        const noCoords = buildTargets({
            harvestables: [node(9, 10, 0), node(4, 10, 0)],
            playerPos: {x: 0, y: 0},
            mode: 'nearest',
            filter: () => true,
        });
        expect(noCoords.map(t => t.id)).toEqual([4, 9]);
    });

    test('默认过滤链对静态资源调用 shouldRenderStaticResource', () => {
        const targets = buildTargets({
            harvestables: [node(1, 10, 0, {tier: 4, charges: 2, stringType: 'Log'})],
            playerPos: PLAYER,
        });

        expect(targets).toHaveLength(1);
        expect(shouldRenderStaticResource).toHaveBeenCalledTimes(1);
        expect(shouldRenderStaticResource.mock.calls[0][0]).toEqual(
            expect.objectContaining({name: 'Log', tier: 4, enchantmentLevel: 2})
        );
        expect(shouldRenderLivingResource).not.toHaveBeenCalled();
    });

    test('活体资源走 shouldRenderLivingResource', () => {
        buildTargets({
            harvestables: [node(1, 10, 0, {mobileTypeId: 5})],
            playerPos: PLAYER,
        });

        expect(shouldRenderLivingResource).toHaveBeenCalledTimes(1);
        expect(shouldRenderStaticResource).not.toHaveBeenCalled();
    });
});
