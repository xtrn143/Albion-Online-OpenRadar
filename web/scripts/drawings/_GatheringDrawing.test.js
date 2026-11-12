import {describe, test, expect, vi} from 'vitest';
import {clipGuide, GatheringDrawing} from './GatheringDrawing.js';

describe('clipGuide', () => {
    test('目标在视野内时不裁剪', () => {
        const result = clipGuide({x: 100, y: 100}, {x: 160, y: 100}, 250);

        expect(result.clipped).toBe(false);
        expect(result.x).toBe(160);
    });

    test('目标超出视野时裁剪到圆边界', () => {
        const result = clipGuide({x: 100, y: 100}, {x: 500, y: 100}, 242);

        expect(result.clipped).toBe(true);
        expect(result.x).toBeCloseTo(342, 3);
        expect(result.y).toBeCloseTo(100, 3);
    });

    test('目标与玩家重合时不产生 NaN', () => {
        const result = clipGuide({x: 100, y: 100}, {x: 100, y: 100}, 242);

        expect(result.clipped).toBe(false);
        expect(Number.isNaN(result.x)).toBe(false);
        expect(Number.isNaN(result.y)).toBe(false);
    });
});

describe('GatheringDrawing.draw', () => {
    function createFakeCtx(width = 500) {
        const lineToCalls = [];
        const arcCalls = [];
        return {
            canvas: {width},
            lineToCalls,
            arcCalls,
            save: vi.fn(),
            restore: vi.fn(),
            beginPath: vi.fn(),
            closePath: vi.fn(),
            stroke: vi.fn(),
            fill: vi.fn(),
            setLineDash: vi.fn(),
            moveTo: vi.fn(),
            lineTo: vi.fn((x, y) => { lineToCalls.push({x, y}); }),
            arc: vi.fn((x, y, r) => { arcCalls.push({x, y, r}); }),
        };
    }

    test('缺少本地坐标时不绘制引导线', () => {
        const ctx = createFakeCtx();
        const advisor = {
            isGathering: false,
            getSelectedTarget: () => ({distance: null, bearingDeg: null, posX: 1, posY: 1}),
        };
        const drawingUtils = {
            getCanvasCenter: () => 250,
            transformPoint: (x, y) => ({x, y}),
        };

        new GatheringDrawing().draw(ctx, advisor, drawingUtils, 0, 0);

        expect(ctx.save).not.toHaveBeenCalled();
    });

    test('越界目标的所有折点都在画布内', () => {
        const ctx = createFakeCtx(500);
        const advisor = {
            isGathering: false,
            getSelectedTarget: () => ({distance: 40, bearingDeg: 0, posX: 1000, posY: 1}),
        };
        const drawingUtils = {
            getCanvasCenter: () => 250,
            transformPoint: () => ({x: 5000, y: 250}),
        };

        new GatheringDrawing().draw(ctx, advisor, drawingUtils, 0, 0);

        expect(ctx.lineToCalls.length).toBeGreaterThan(0);
        for (const {x, y} of ctx.lineToCalls) {
            expect(x).toBeGreaterThanOrEqual(0);
            expect(x).toBeLessThanOrEqual(500);
            expect(y).toBeGreaterThanOrEqual(0);
            expect(y).toBeLessThanOrEqual(500);
        }
    });

    test('采集态多绘制一个圆环', () => {
        const makeAdvisor = isGathering => ({
            isGathering,
            getSelectedTarget: () => ({distance: 10, bearingDeg: 0, posX: 110, posY: 0}),
        });
        const drawingUtils = {
            getCanvasCenter: () => 250,
            transformPoint: () => ({x: 300, y: 250}),
        };

        const gatheringCtx = createFakeCtx(500);
        new GatheringDrawing().draw(gatheringCtx, makeAdvisor(true), drawingUtils, 0, 0);
        const idleCtx = createFakeCtx(500);
        new GatheringDrawing().draw(idleCtx, makeAdvisor(false), drawingUtils, 0, 0);

        expect(gatheringCtx.arcCalls.length).toBeGreaterThanOrEqual(2);
        expect(gatheringCtx.arcCalls.length).toBe(idleCtx.arcCalls.length + 1);
    });
});
