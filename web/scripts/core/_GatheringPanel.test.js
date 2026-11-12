import {describe, test, expect, vi} from 'vitest';

vi.mock('../utils/SettingsSync.js', () => ({
    default: {
        get: vi.fn((_k, d) => d),
        getBool: vi.fn((_k, d) => d ?? true),
        getNumber: vi.fn((_k, d) => d),
    },
}));

const {renderTargetRow, renderCompass} = await import('./GatheringPanel.js');

const target = {
    id: 7,
    stringType: 'Log',
    tier: 7,
    enchant: 2,
    size: 4,
    distance: 34,
    bearingDeg: 90,
};

describe('GatheringPanel render helpers', () => {
    test('行内包含层级、附魔、距离、剩余层数与资源图标', () => {
        const html = renderTargetRow(target, 7);

        expect(html).toContain('T7.2');
        expect(html).toContain('34m');
        expect(html).toContain('/images/Resources/log_7_2.webp');
        expect(html).toContain('data-target-id="7"');
    });

    test('方位箭头按连续角度旋转，不量化成 8 向', () => {
        const html = renderTargetRow({...target, bearingDeg: 37}, null);
        expect(html).toContain('rotate(37deg)');
    });

    test('迷你方位盘按距离比例放置目标点', () => {
        const svg = renderCompass([target], 7);

        expect(svg).toContain('<circle');
        expect(svg).toContain('r="3"');
    });

    test('坐标缺失时显示占位符而不是 NaN', () => {
        const html = renderTargetRow({...target, distance: null, bearingDeg: null}, null);

        expect(html).toContain('--');
        expect(html).not.toContain('NaN');
    });
});
