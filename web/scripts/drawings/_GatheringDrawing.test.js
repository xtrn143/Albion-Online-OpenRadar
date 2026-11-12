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
    test('缺少本地坐标时不绘制引导线', () => {
        const ctx = {
            save: vi.fn(),
            restore: vi.fn(),
            beginPath: vi.fn(),
            moveTo: vi.fn(),
            lineTo: vi.fn(),
            stroke: vi.fn(),
            setLineDash: vi.fn(),
            arc: vi.fn(),
            fill: vi.fn(),
            closePath: vi.fn(),
        };
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
});
