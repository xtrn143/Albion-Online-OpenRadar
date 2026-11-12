import {describe, test, expect} from 'vitest';
import {clipGuide} from './GatheringDrawing.js';

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
