import {describe, test, expect, vi, beforeEach, afterEach} from 'vitest';

vi.mock('../utils/SettingsSync.js', () => ({
    default: {
        get: vi.fn((_k, d) => d),
        getGatheringMode: vi.fn(function () {
            return this.get('settingGatheringMode', 'gather') === 'roam' ? 'roam' : 'gather';
        }),
        getBool: vi.fn((_k, d) => d ?? true),
        getNumber: vi.fn((_k, d) => d),
    },
}));

const {renderTargetRow, renderCompass, init, update, destroy, shouldShowTargets, renderModeSwitch} = await import('./GatheringPanel.js');
const settingsSync = (await import('../utils/SettingsSync.js')).default;

function setMode(mode) {
    settingsSync.get.mockImplementation((key, def) => (key === 'settingGatheringMode' ? mode : def));
}

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

function setupDom() {
    document.body.innerHTML = `
        <div id="gatheringCard">
            <span id="gatheringModeSwitch"></span>
            <span id="gatheringStateBadge" class="hidden"></span>
            <span id="gatheringNoPosition" class="hidden"></span>
            <div id="gatheringBody">
                <div id="gatheringCompass"></div>
                <div id="gatheringTargets"></div>
                <div id="gatheringEmpty" class="hidden"></div>
            </div>
        </div>`;
}

function fakeAdvisor(targets) {
    return {
        getState: () => ({targets, selectedId: null, isGathering: false, lastHarvestAt: 0, lastHarvestId: null}),
        select: vi.fn(),
    };
}

describe('GatheringPanel DOM update', () => {
    beforeEach(() => {
        settingsSync.get.mockImplementation((_k, d) => d);
        settingsSync.getBool.mockReturnValue(true);
        setupDom();
    });

    afterEach(() => {
        destroy();
        document.body.innerHTML = '';
    });

    test('隐藏时只隐藏卡片内容区，卡片头部开关仍可达', () => {
        settingsSync.getBool.mockReturnValue(false);
        const advisor = fakeAdvisor([target]);
        init(advisor);
        update(advisor);

        expect(document.getElementById('gatheringBody').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('gatheringCard').classList.contains('hidden')).toBe(false);
    });

    test('目标全部缺少本地坐标时提示 waiting for position', () => {
        const advisor = fakeAdvisor([{...target, distance: null, bearingDeg: null}]);
        init(advisor);
        update(advisor);

        expect(document.getElementById('gatheringNoPosition').classList.contains('hidden')).toBe(false);
    });

    test('空目标时显示空态文案，有目标时隐藏', () => {
        const advisor = fakeAdvisor([]);
        init(advisor);
        update(advisor);

        expect(document.getElementById('gatheringEmpty').classList.contains('hidden')).toBe(false);

        advisor.getState = () => ({targets: [target], selectedId: null, isGathering: false, lastHarvestAt: 0, lastHarvestId: null});
        update(advisor);

        expect(document.getElementById('gatheringEmpty').classList.contains('hidden')).toBe(true);
    });

    test('仅方位变化也会重渲染箭头与方位盘', () => {
        const targets = [{...target}];
        const advisor = fakeAdvisor(targets);
        init(advisor);
        update(advisor);

        targets[0] = {...targets[0], bearingDeg: 5};
        update(advisor);

        const html = document.getElementById('gatheringTargets').innerHTML;
        expect(html).toContain('rotate(5deg)');
        expect(html).not.toContain('rotate(90deg)');
    });

    test('tier/enchant 缺失时不产生 undefined 与 NaN', () => {
        const broken = {...target, tier: undefined, enchant: undefined, distance: undefined, bearingDeg: undefined};

        const html = renderTargetRow(broken, null);
        expect(html).not.toContain('undefined');
        expect(html).not.toContain('NaN');

        const svg = renderCompass([broken], null);
        expect(svg).not.toContain('NaN');
        expect((svg.match(/<circle/g) || []).length).toBe(2);
    });

    test('常规模式收起内容区但保留卡片头部，切回后恢复目标列表', () => {
        const advisor = fakeAdvisor([target]);
        init(advisor);

        setMode('roam');
        update(advisor);

        expect(document.getElementById('gatheringBody').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('gatheringCard').classList.contains('hidden')).toBe(false);

        setMode('gather');
        update(advisor);

        expect(document.getElementById('gatheringBody').classList.contains('hidden')).toBe(false);
        expect(document.getElementById('gatheringTargets').innerHTML).toContain('data-target-id="7"');
    });
});

describe('gathering mode', () => {
    test('采集模式展开目标列表', () => {
        expect(shouldShowTargets('gather')).toBe(true);
    });

    test('常规模式收起目标列表', () => {
        expect(shouldShowTargets('roam')).toBe(false);
        expect(shouldShowTargets(undefined)).toBe(true);
        expect(shouldShowTargets('invalid')).toBe(true);
    });

    test('模式切换控件包含两种模式且标出当前值', () => {
        const html = renderModeSwitch('roam');

        expect(html).toContain('value="gather"');
        expect(html).toContain('value="roam"');
        expect(html).toContain('roam" selected');
    });
});
