# 采集辅助目标队列 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在雷达页给采集玩家提供"先采哪个、往哪走、周围是否有人"的前端能力，不改协议解析与后端。

**Architecture:** 新增 `GatheringAdvisor` 负责过滤、打分、方位与采集态识别，纯函数 + 一个轻状态类；新增 `GatheringPanel` 渲染目标卡片与迷你方位盘；新增 `GatheringDrawing` 在 `uiCanvas` 上画引导线；`PlayersHandler` 接收采集态并放宽告警门槛。所有新数据来自既有 `harvestableList`、`localPlayer` 与玩家事件。

**Tech Stack:** 原生 ES Modules、Canvas 2D、DaisyUI/Tailwind 模板、Vitest（jsdom）。

**参考文档：** `docs/superpowers/specs/2026-11-12-gathering-advisor-design.md`

> 提交步骤按 skill 要求保留。如果你不希望执行时自动 `git commit`，执行阶段跳过各任务的 Commit 步骤即可。

---

## Task 1: 目标打分与屏幕空间方位

**Files:**
- Create: `web/scripts/utils/GatheringAdvisor.js`
- Test: `web/scripts/utils/_GatheringAdvisor.test.js`

- [ ] **Step 1: 写失败测试**

创建 `web/scripts/utils/_GatheringAdvisor.test.js`：

```js
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run web/scripts/utils/_GatheringAdvisor.test.js`
Expected: FAIL，报错 `Failed to resolve import "./GatheringAdvisor.js"` 或 `buildTargets is not a function`。

- [ ] **Step 3: 实现打分与方位**

创建 `web/scripts/utils/GatheringAdvisor.js`：

```js
import settingsSync from './SettingsSync.js';
import {shouldRenderLivingResource, shouldRenderStaticResource} from './LivingResourceFilter.js';

export const MAX_RANGE = 80;

export const MODES = {
    nearest: {distance: 0.60, tier: 0.20, enchant: 0.10, size: 0.10},
    tier: {distance: 0.15, tier: 0.35, enchant: 0.35, size: 0.15},
    efficiency: {distance: 0.25, tier: 0.25, enchant: 0.15, size: 0.35},
};

export function rotateIsometric(x, y) {
    const angle = -0.785398;
    return {x: x * angle - y * angle, y: x * angle + y * angle};
}

// 与 DrawingUtils.interpolateEntity 一致：X 轴取反后再做等距旋转
export function toScreenVector(nodePos, playerPos, rotate = rotateIsometric) {
    const dx = nodePos.posX - playerPos.x;
    const dy = nodePos.posY - playerPos.y;
    return rotate(-dx, dy);
}

export function hasPlayerPosition(playerPos) {
    return !!playerPos && !(playerPos.x === 0 && playerPos.y === 0);
}

export function distanceBetween(node, playerPos) {
    const dx = node.posX - playerPos.x;
    const dy = node.posY - playerPos.y;
    return Math.sqrt(dx * dx + dy * dy);
}

function isPureStatic(harvestable) {
    const typeId = harvestable.mobileTypeId;
    return typeId === null || typeId === undefined || typeId === -1 || typeId === 65535;
}

function passesFilter(harvestable) {
    const entity = {
        name: harvestable.stringType,
        tier: harvestable.tier,
        enchantmentLevel: harvestable.charges,
    };
    const getSetting = key => settingsSync.getJSON(key);
    return isPureStatic(harvestable)
        ? shouldRenderStaticResource(entity, getSetting)
        : shouldRenderLivingResource(entity, getSetting);
}

export function buildTargets({
    harvestables,
    playerPos,
    mode = 'nearest',
    maxTargets = 5,
    rotate = rotateIsometric,
    filter = passesFilter,
}) {
    const weights = MODES[mode] || MODES.nearest;
    const hasPos = hasPlayerPosition(playerPos);
    const candidates = [];
    let maxSize = 1;

    for (const harvestable of harvestables || []) {
        if (!harvestable || harvestable.size <= 0) continue;
        if (!filter(harvestable)) continue;

        let distance = null;
        let bearingDeg = null;
        if (hasPos) {
            distance = distanceBetween(harvestable, playerPos);
            if (distance > MAX_RANGE) continue;
            const vector = toScreenVector(harvestable, playerPos, rotate);
            bearingDeg = Math.atan2(vector.y, vector.x) * 180 / Math.PI;
        }

        if (harvestable.size > maxSize) maxSize = harvestable.size;
        candidates.push({harvestable, distance, bearingDeg});
    }

    return candidates
        .map(({harvestable, distance, bearingDeg}) => {
            const proximity = distance === null ? 0 : 1 - distance / MAX_RANGE;
            const score = weights.distance * proximity
                + weights.tier * ((harvestable.tier || 0) / 8)
                + weights.enchant * ((harvestable.charges || 0) / 4)
                + weights.size * (harvestable.size / maxSize);

            return {
                id: harvestable.id,
                posX: harvestable.posX,
                posY: harvestable.posY,
                stringType: harvestable.stringType,
                tier: harvestable.tier,
                enchant: harvestable.charges,
                size: harvestable.size,
                isLiving: !isPureStatic(harvestable),
                distance,
                bearingDeg,
                score,
            };
        })
        .sort((a, b) => b.score - a.score)
        .slice(0, maxTargets);
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run web/scripts/utils/_GatheringAdvisor.test.js`
Expected: PASS，6 个测试全绿。

- [ ] **Step 5: Commit**

```bash
git add web/scripts/utils/GatheringAdvisor.js web/scripts/utils/_GatheringAdvisor.test.js
git commit -m "feat: add gathering target scoring and screen-space bearings"
```

---

## Task 2: 采集识别

**Files:**
- Modify: `web/scripts/utils/GatheringAdvisor.js`（追加函数）
- Test: `web/scripts/utils/_GatheringAdvisor.test.js`（追加测试）

- [ ] **Step 1: 追加失败测试**

在 `_GatheringAdvisor.test.js` 末尾追加：

```js
const {detectHarvestedNode} = await import('./GatheringAdvisor.js');

describe('detectHarvestedNode', () => {
    test('识别层数下降的节点', () => {
        const previous = new Map([[1, {size: 3}], [2, {size: 2}]]);
        const result = detectHarvestedNode(
            previous,
            [node(1, 0, 10, {size: 3}), node(2, 0, 30, {size: 1})],
            PLAYER,
        );

        expect(result.harvestedId).toBe(2);
        expect(result.nextSizes.get(1).size).toBe(3);
    });

    test('多个节点同时下降时取离玩家最近的', () => {
        const previous = new Map([[1, {size: 3}], [2, {size: 3}]]);
        const result = detectHarvestedNode(
            previous,
            [node(1, 0, 40, {size: 2}), node(2, 0, 5, {size: 2})],
            PLAYER,
        );

        expect(result.harvestedId).toBe(2);
    });

    test('没有变化时返回 null', () => {
        const previous = new Map([[1, {size: 3}]]);
        const result = detectHarvestedNode(previous, [node(1, 0, 10, {size: 3})], PLAYER);

        expect(result.harvestedId).toBeNull();
    });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run web/scripts/utils/_GatheringAdvisor.test.js`
Expected: FAIL，`detectHarvestedNode is not a function`。

- [ ] **Step 3: 实现识别函数**

在 `GatheringAdvisor.js` 末尾追加：

```js
export function detectHarvestedNode(previousSizes, harvestables, playerPos) {
    const nextSizes = new Map();
    const changed = [];

    for (const harvestable of harvestables || []) {
        if (!harvestable || typeof harvestable.size !== 'number') continue;
        nextSizes.set(harvestable.id, {
            size: harvestable.size,
            posX: harvestable.posX,
            posY: harvestable.posY,
        });

        const previous = previousSizes instanceof Map
            ? previousSizes.get(harvestable.id)
            : previousSizes?.[harvestable.id];
        const previousSize = previous && typeof previous === 'object' ? previous.size : previous;

        if (typeof previousSize === 'number' && harvestable.size < previousSize) {
            changed.push(harvestable);
        }
    }

    if (changed.length === 0) {
        return {harvestedId: null, nextSizes};
    }

    if (hasPlayerPosition(playerPos) && changed.length > 1) {
        changed.sort((a, b) => distanceBetween(a, playerPos) - distanceBetween(b, playerPos));
    }

    return {harvestedId: changed[0].id, nextSizes};
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run web/scripts/utils/_GatheringAdvisor.test.js`
Expected: PASS，9 个测试全绿。

- [ ] **Step 5: Commit**

```bash
git add web/scripts/utils/GatheringAdvisor.js web/scripts/utils/_GatheringAdvisor.test.js
git commit -m "feat: detect harvested resource nodes from size changes"
```

---

## Task 3: GatheringAdvisor 状态类

**Files:**
- Modify: `web/scripts/utils/GatheringAdvisor.js`（追加类）
- Test: `web/scripts/utils/_GatheringAdvisor.test.js`（追加测试）

- [ ] **Step 1: 追加失败测试**

```js
const {GatheringAdvisor} = await import('./GatheringAdvisor.js');

describe('GatheringAdvisor', () => {
    test('更新后产出目标并自动选中第一名', () => {
        const advisor = new GatheringAdvisor();
        advisor.update([node(1, 10, 0), node(2, 30, 0)], PLAYER, {mode: 'nearest'});

        expect(advisor.targets.map(t => t.id)).toEqual([1, 2]);
        expect(advisor.getSelectedTarget().id).toBe(1);
    });

    test('层数下降进入采集态，空闲超时后退出', () => {
        let now = 1000;
        const advisor = new GatheringAdvisor({now: () => now, idleMs: 8000});
        const player = {x: 1000, y: 1000};

        advisor.update([node(1, 0, 10, {size: 3})], player, {mode: 'nearest'});
        expect(advisor.isGathering).toBe(false);

        advisor.update([node(1, 0, 10, {size: 2})], player, {mode: 'nearest'});
        expect(advisor.isGathering).toBe(true);

        now += 9000;
        advisor.update([node(1, 0, 10, {size: 2})], player, {mode: 'nearest'});
        expect(advisor.isGathering).toBe(false);
    });

    test('选中的目标离开列表后回落到第一名', () => {
        const advisor = new GatheringAdvisor();
        advisor.update([node(1, 10, 0), node(2, 30, 0)], PLAYER, {mode: 'nearest'});
        advisor.select(2);
        expect(advisor.getSelectedTarget().id).toBe(2);

        advisor.update([node(1, 10, 0)], PLAYER, {mode: 'nearest'});
        expect(advisor.getSelectedTarget().id).toBe(1);
    });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run web/scripts/utils/_GatheringAdvisor.test.js`
Expected: FAIL，`GatheringAdvisor is not a constructor`。

- [ ] **Step 3: 实现状态类**

在 `GatheringAdvisor.js` 末尾追加：

```js
export class GatheringAdvisor {
    constructor({rotate = rotateIsometric, now = () => Date.now(), idleMs = 8000} = {}) {
        this.rotate = rotate;
        this.now = now;
        this.idleMs = idleMs;
        this.targets = [];
        this.selectedId = null;
        this.isGathering = false;
        this.lastHarvestAt = 0;
        this.lastHarvestId = null;
        this.previousSizes = new Map();
    }

    update(harvestables, playerPos, {mode = 'nearest', maxTargets = 5} = {}) {
        this.targets = buildTargets({
            harvestables,
            playerPos,
            mode,
            maxTargets,
            rotate: this.rotate,
        });

        const {harvestedId, nextSizes} = detectHarvestedNode(this.previousSizes, harvestables, playerPos);
        this.previousSizes = nextSizes;

        const now = this.now();
        if (harvestedId !== null) {
            this.lastHarvestId = harvestedId;
            this.lastHarvestAt = now;
            this.isGathering = true;
        } else if (this.isGathering && now - this.lastHarvestAt > this.idleMs) {
            this.isGathering = false;
        }

        if (this.selectedId === null || !this.targets.some(t => t.id === this.selectedId)) {
            this.selectedId = this.targets.length > 0 ? this.targets[0].id : null;
        }

        return this.targets;
    }

    select(id) {
        this.selectedId = id;
    }

    getSelectedTarget() {
        return this.targets.find(target => target.id === this.selectedId) || null;
    }

    getState() {
        return {
            targets: this.targets,
            selectedId: this.selectedId,
            isGathering: this.isGathering,
            lastHarvestAt: this.lastHarvestAt,
        };
    }
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run web/scripts/utils/_GatheringAdvisor.test.js`
Expected: PASS，12 个测试全绿。

- [ ] **Step 5: Commit**

```bash
git add web/scripts/utils/GatheringAdvisor.js web/scripts/utils/_GatheringAdvisor.test.js
git commit -m "feat: add gathering advisor state and harvesting session tracking"
```

---

## Task 4: 采集模式告警门槛

**Files:**
- Modify: `web/scripts/handlers/PlayersHandler.js:83-90`（构造函数）
- Modify: `web/scripts/handlers/PlayersHandler.js:130-135`（isPlayerThreat）
- Test: `web/scripts/handlers/_PlayersHandler.test.js`

- [ ] **Step 1: 写失败测试**

在 `_PlayersHandler.test.js` 的 `describe('PlayersHandler')` 内追加：

```js
describe('gathering alert escalation', () => {
    test('采集模式下黄区被动玩家也告警', () => {
        settingsSync.getBool.mockImplementation((key, d) =>
            key === 'settingGatherAlertMode' ? true : (d ?? true));
        handler.setGatheringState(true);

        expect(handler.isPlayerThreat(0, 'yellow')).toBe(true);
    });

    test('未开启采集模式时黄区被动玩家不告警', () => {
        settingsSync.getBool.mockImplementation((key, d) =>
            key === 'settingGatherAlertMode' ? false : (d ?? true));
        handler.setGatheringState(true);

        expect(handler.isPlayerThreat(0, 'yellow')).toBe(false);
    });

    test('采集模式下安全区仍不告警', () => {
        settingsSync.getBool.mockReturnValue(true);
        handler.setGatheringState(true);

        expect(handler.isPlayerThreat(0, 'safe')).toBe(false);
    });

    test('采集模式下红区被动玩家告警', () => {
        settingsSync.getBool.mockReturnValue(true);
        handler.setGatheringState(true);

        expect(handler.isPlayerThreat(0, 'red')).toBe(true);
    });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run web/scripts/handlers/_PlayersHandler.test.js -t "gathering alert escalation"`
Expected: FAIL，`handler.setGatheringState is not a function`。

- [ ] **Step 3: 实现采集态与告警扩展**

在 `PlayersHandler` 构造函数中追加一行：

```js
        this.gathering = {isGathering: false};
```

在 `isPlayerThreat` 上方新增方法：

```js
    setGatheringState(isGathering) {
        this.gathering.isGathering = !!isGathering;
    }
```

把 `isPlayerThreat` 替换为：

```js
    isPlayerThreat(faction, pvpType, gathering = this.gathering?.isGathering) {
        if (pvpType === 'safe') return false;
        if (gathering && settingsSync.getBool('settingGatherAlertMode', false)) return true;
        if (pvpType === 'black') return true;
        if (pvpType === 'red' || pvpType === 'yellow') return faction === 255;
        return faction === 255;
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run web/scripts/handlers/_PlayersHandler.test.js -t "gathering alert escalation"`
Expected: PASS，4 个测试全绿。

Run: `npx vitest run web/scripts/handlers/_PlayersHandler.test.js`
Expected: PASS，既有测试全部保持通过。

- [ ] **Step 5: Commit**

```bash
git add web/scripts/handlers/PlayersHandler.js web/scripts/handlers/_PlayersHandler.test.js
git commit -m "feat: escalate player alerts while gathering"
```

---

## Task 5: 玩家离开记录

**Files:**
- Modify: `web/scripts/handlers/PlayersHandler.js:24-26`（Player 构造）
- Modify: `web/scripts/handlers/PlayersHandler.js:258-260`（removePlayer）
- Modify: `web/scripts/handlers/PlayersHandler.js:393-411`（getFilteredPlayers 保留期）
- Modify: `web/scripts/handlers/PlayersHandler.js:433-436`（getThreatPlayers）
- Modify: `web/scripts/core/PlayerListRenderer.js:51-52`（离开文案）
- Modify: `web/scripts/core/PlayerListRenderer.js:162-175`（增量更新时间文案）
- Test: `web/scripts/handlers/_PlayersHandler.test.js:606-615`（替换既有测试）

- [ ] **Step 1: 替换并新增测试**

把 `lifecycle` 里的 `synthetic: removePlayer removes the target entity` 整个测试替换为：

```js
        // removePlayer 改为标记 leftAt，保留短时间用于展示“已离开”
        test('synthetic: removePlayer marks leftAt and keeps the entity', () => {
            handler.handleNewPlayerEvent(1, {1: 'A', 8: '', 53: 0, 51: null, 40: [], 43: []});
            handler.handleNewPlayerEvent(2, {1: 'B', 8: '', 53: 0, 51: null, 40: [], 43: []});

            handler.removePlayer(1);

            const left = handler.playersList.find(p => p.id === 1);
            expect(left).toBeTruthy();
            expect(left.leftAt).toBeGreaterThan(0);
            expect(handler.getSize()).toBe(2);
        });

        test('synthetic: 已离开玩家不再出现在威胁列表', () => {
            zonesDatabase.getPvpType.mockReturnValue('black');
            handler.handleNewPlayerEvent(1, {1: 'A', 8: '', 53: 0, 51: null, 40: [], 43: []});

            handler.removePlayer(1);

            expect(handler.getThreatPlayers()).toHaveLength(0);
        });

        test('synthetic: 超过 30 秒的离开记录不再出现在筛选列表', () => {
            handler.handleNewPlayerEvent(1, {1: 'A', 8: '', 53: 0, 51: null, 40: [], 43: []});
            handler.removePlayer(1);
            handler.playersList[0].leftAt = Date.now() - 31000;

            expect(handler.getFilteredPlayers()).toHaveLength(0);
        });
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run web/scripts/handlers/_PlayersHandler.test.js -t "leftAt"`
Expected: FAIL，`left.leftAt` 为 undefined 且列表长度断言失败。

- [ ] **Step 3: 实现离开标记**

`Player` 构造函数中 `detectedAt` 之后追加：

```js
        this.leftAt = null;
```

替换 `removePlayer`：

```js
    removePlayer(id) {
        const player = this.playersList.find(target => target.id === id);
        if (!player) return;
        player.leftAt = Date.now();
    }
```

同一玩家再次出现时要清掉离开标记。在 `handleNewPlayerEvent` 的 upsert 分支（第 186-197 行，`existingPlayer.touch();` 之前）插入：

```js
            existingPlayer.leftAt = null;
```

`getFilteredPlayers` 的过滤回调开头追加离开保留期判断。原回调形如 `return this.playersList.filter(player => { ... })`，改为：

```js
        const now = Date.now();
        return this.playersList.filter(player => {
            if (player.leftAt) {
                return (now - player.leftAt) < 30000;
            }
            // 以下保持原有逻辑不变
```

替换 `getThreatPlayers`：

```js
    getThreatPlayers() {
        const pvpType = zonesDatabase.getPvpType(window.currentMapId);
        return this.playersList.filter(p => !p.leftAt && this.isPlayerThreat(p.faction, pvpType));
    }
```

`cleanupStaleEntities` 的过滤回调改为：

```js
        this.playersList = this.playersList.filter(player => {
            if (player.leftAt) {
                return (now - player.leftAt) < 30000;
            }
            return (now - player.lastUpdateTime) < maxAgeMs;
        });
```

- [ ] **Step 4: 运行 PlayersHandler 测试确认通过**

Run: `npx vitest run web/scripts/handlers/_PlayersHandler.test.js`
Expected: PASS，含新增 3 个测试。

- [ ] **Step 5: 玩家卡片显示离开时间**

`PlayerListRenderer.js` 第 52 行替换为：

```js
    const timeStr = player.leftAt ? `left ${formatElapsedTime(player.leftAt)}` : formatElapsedTime(player.detectedAt);
```

`updateSectionPlayers` 中更新 `data-time` 的分支替换为：

```js
            const timeEl = existingCard.querySelector('[data-time]');
            if (timeEl) {
                timeEl.textContent = player.leftAt
                    ? `left ${formatElapsedTime(player.leftAt)}`
                    : formatElapsedTime(player.detectedAt);
            }
            if (player.leftAt) {
                existingCard.classList.add('opacity-50');
            }
```

- [ ] **Step 6: Commit**

```bash
git add web/scripts/handlers/PlayersHandler.js web/scripts/core/PlayerListRenderer.js web/scripts/handlers/_PlayersHandler.test.js
git commit -m "feat: keep departed players briefly with left timestamps"
```

---

## Task 6: 雷达页目标卡片与迷你方位盘

**Files:**
- Create: `web/scripts/core/GatheringPanel.js`
- Test: `web/scripts/core/_GatheringPanel.test.js`
- Modify: `internal/templates/pages/radar.gohtml:72`（插入卡片）
- Modify: `internal/templates/pages/radar.gohtml:187-194`（绑定设置）

- [ ] **Step 1: 写失败测试**

创建 `web/scripts/core/_GatheringPanel.test.js`：

```js
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run web/scripts/core/_GatheringPanel.test.js`
Expected: FAIL，无法解析 `./GatheringPanel.js`。

- [ ] **Step 3: 实现面板模块**

创建 `web/scripts/core/GatheringPanel.js`：

```js
import settingsSync from '../utils/SettingsSync.js';

const ICON_TYPES = {
    log: 'log', wood: 'log', logs: 'log',
    rock: 'rock', fiber: 'fiber', hide: 'hide', ore: 'ore',
};

let elements = null;
let advisorRef = null;
let clickHandler = null;
let hoverHandler = null;
let lastHash = '';

export function renderTargetRow(target, selectedId) {
    const type = ICON_TYPES[(target.stringType || '').toLowerCase()] || 'rock';
    const icon = `/images/Resources/${type}_${target.tier}_${target.enchant}.webp`;
    const distance = target.distance === null ? '--' : `${Math.round(target.distance)}m`;
    const arrow = target.bearingDeg === null
        ? '<span class="text-xs text-base-content/40">--</span>'
        : `<i class="inline-block text-xs text-base-content/60" style="transform: rotate(${Math.round(target.bearingDeg)}deg)">➜</i>`;
    const active = target.id === selectedId
        ? 'bg-primary/10 border-primary/40'
        : 'border-transparent hover:bg-base-300/60';
    const dimmed = target.size <= 0 ? 'opacity-40' : '';

    return `<div class="flex items-center gap-3 px-3 py-2 rounded-lg border ${active} ${dimmed} cursor-pointer transition-colors" data-target-id="${target.id}">
        <img src="${icon}" alt="" class="w-6 h-6 object-contain" loading="lazy">
        <span class="font-mono text-xs text-base-content/70">T${target.tier}.${target.enchant}</span>
        <span class="text-sm text-base-content/80 flex-1 truncate">${target.stringType || '?'}</span>
        <span class="flex items-center gap-1">${arrow}<span class="text-xs text-base-content/60">${distance}</span></span>
        <span class="font-mono text-xs text-base-content/50">${target.size}</span>
    </div>`;
}

export function renderCompass(targets, selectedId) {
    const center = 34;
    const radius = 30;
    const dots = (targets || []).map(target => {
        if (target.distance === null || target.bearingDeg === null) return '';
        const radians = target.bearingDeg * Math.PI / 180;
        const ratio = Math.min(1, target.distance / 80);
        const cx = (center + Math.cos(radians) * ratio * radius).toFixed(1);
        const cy = (center + Math.sin(radians) * ratio * radius).toFixed(1);
        const active = target.id === selectedId;
        return `<circle cx="${cx}" cy="${cy}" r="${active ? 3 : 2}" fill="currentColor" opacity="${active ? 1 : 0.45}"/>`;
    }).join('');

    return `<svg viewBox="0 0 68 68" width="68" height="68" class="text-base-content/60" aria-hidden="true">
        <circle cx="34" cy="34" r="30" fill="none" stroke="currentColor" stroke-opacity="0.2"/>
        <circle cx="34" cy="34" r="2.5" fill="currentColor"/>
        ${dots}
    </svg>`;
}

export function init(advisor) {
    advisorRef = advisor;
    elements = {
        card: document.getElementById('gatheringCard'),
        list: document.getElementById('gatheringTargets'),
        empty: document.getElementById('gatheringEmpty'),
        badge: document.getElementById('gatheringStateBadge'),
        compass: document.getElementById('gatheringCompass'),
    };
    if (!elements.list) return;

    const selectFromEvent = event => {
        const row = event.target.closest('[data-target-id]');
        if (!row || !advisorRef) return;
        advisorRef.select(Number(row.dataset.targetId));
    };
    clickHandler = selectFromEvent;
    hoverHandler = selectFromEvent;
    elements.list.addEventListener('click', clickHandler);
    elements.list.addEventListener('mouseover', hoverHandler);
    lastHash = '';
}

export function update(advisor) {
    if (!elements?.list || !advisor) return;
    const visible = settingsSync.getBool('settingShowGatheringTargets', true);
    elements.card?.classList.toggle('hidden', !visible);
    if (!visible) return;

    const state = advisor.getState();
    const hash = `${state.selectedId}:${state.isGathering}:`
        + state.targets.map(t => `${t.id}:${t.size}:${t.distance === null ? '-' : Math.round(t.distance)}`).join(',');
    if (hash === lastHash) return;
    lastHash = hash;

    elements.list.innerHTML = state.targets.map(t => renderTargetRow(t, state.selectedId)).join('');
    elements.empty?.classList.toggle('hidden', state.targets.length > 0);
    elements.badge?.classList.toggle('hidden', !state.isGathering);
    if (elements.compass) {
        elements.compass.innerHTML = renderCompass(state.targets, state.selectedId);
    }
}

export function destroy() {
    if (elements?.list) {
        if (clickHandler) elements.list.removeEventListener('click', clickHandler);
        if (hoverHandler) elements.list.removeEventListener('mouseover', hoverHandler);
    }
    elements = null;
    advisorRef = null;
    clickHandler = null;
    hoverHandler = null;
    lastHash = '';
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run web/scripts/core/_GatheringPanel.test.js`
Expected: PASS，4 个测试全绿。

- [ ] **Step 5: 插入模板卡片**

在 `internal/templates/pages/radar.gohtml` 第 73 行 `<!-- Detected Players Section -->` 之前插入：

```html
    <!-- Gathering Targets Section -->
    <div id="gatheringCard" class="card bg-base-200">
        <div class="card-body">
            <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <h3 class="text-xl font-semibold text-base-content flex items-center gap-2">
                    Gathering Targets
                    <span id="gatheringStateBadge" class="badge badge-primary badge-sm hidden">采集中</span>
                    <label class="flex items-center gap-1.5 cursor-pointer" title="Show gathering targets on radar">
                        <input type="checkbox" id="settingShowGatheringTargets" class="checkbox checkbox-primary checkbox-xs">
                        <span class="text-xs text-base-content/60 font-normal">Show</span>
                    </label>
                </h3>
                <div class="flex items-center gap-2">
                    <select id="settingGatheringSort" class="select select-sm select-bordered">
                        <option value="nearest">就近优先</option>
                        <option value="tier">高级优先</option>
                        <option value="efficiency">效率优先</option>
                    </select>
                    <input type="number" id="settingGatheringMaxTargets" class="input input-sm input-bordered w-16" min="1" max="10" title="Max targets">
                </div>
            </div>
            <div class="flex items-center gap-4 mt-2">
                <div id="gatheringCompass" class="shrink-0"></div>
                <div id="gatheringTargets" class="flex-1 grid gap-1"></div>
            </div>
            <div id="gatheringEmpty" class="hidden py-4 text-center text-sm text-base-content/40">No resources in range</div>
        </div>
    </div>
```

- [ ] **Step 6: 绑定设置项**

在 `radar.gohtml` 脚本中，`['settingResourceCount', ...]` 绑定块（第 187-194 行）之后追加：

```js
    const showTargetsEl = document.getElementById('settingShowGatheringTargets');
    if (showTargetsEl) {
        showTargetsEl.checked = settingsSync.getBool('settingShowGatheringTargets', true);
        addListener(showTargetsEl, 'change', () => settingsSync.setBool('settingShowGatheringTargets', showTargetsEl.checked));
    }

    const gatheringModeEl = document.getElementById('settingGatheringSort');
    if (gatheringModeEl) {
        gatheringModeEl.value = settingsSync.get('settingGatheringSort', 'nearest');
        addListener(gatheringModeEl, 'change', () => settingsSync.set('settingGatheringSort', gatheringModeEl.value));
    }

    const maxTargetsEl = document.getElementById('settingGatheringMaxTargets');
    if (maxTargetsEl) {
        maxTargetsEl.value = settingsSync.getNumber('settingGatheringMaxTargets', 5);
        addListener(maxTargetsEl, 'change', () => {
            const value = Math.max(1, Math.min(10, Number(maxTargetsEl.value) || 5));
            maxTargetsEl.value = value;
            settingsSync.setNumber('settingGatheringMaxTargets', value);
        });
    }
```

- [ ] **Step 7: Commit**

```bash
git add web/scripts/core/GatheringPanel.js web/scripts/core/_GatheringPanel.test.js internal/templates/pages/radar.gohtml
git commit -m "feat: add gathering targets card with compass and settings"
```

---

## Task 7: 画布引导线与接线

**Files:**
- Create: `web/scripts/drawings/GatheringDrawing.js`
- Test: `web/scripts/drawings/_GatheringDrawing.test.js`
- Modify: `web/scripts/utils/RadarRenderer.js:315-326`（renderUI）
- Modify: `web/scripts/utils/Utils.js:77-123`（renderer 依赖）
- Modify: `web/scripts/utils/Utils.js:161-180`（创建实例）
- Modify: `web/scripts/utils/Utils.js:227-235`（刷新与面板）
- Modify: `web/scripts/utils/Utils.js:260-318`（销毁清理）

- [ ] **Step 1: 写失败测试**

创建 `web/scripts/drawings/_GatheringDrawing.test.js`：

```js
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run web/scripts/drawings/_GatheringDrawing.test.js`
Expected: FAIL，无法解析 `./GatheringDrawing.js`。

- [ ] **Step 3: 实现绘制模块**

创建 `web/scripts/drawings/GatheringDrawing.js`：

```js
const GUIDE_COLOR = 'rgba(15, 220, 120, 0.9)';

export function clipGuide(center, point, maxLength) {
    const dx = point.x - center.x;
    const dy = point.y - center.y;
    const length = Math.hypot(dx, dy);

    if (length === 0) {
        return {x: center.x, y: center.y, clipped: false, unitX: 0, unitY: 0};
    }
    if (length <= maxLength) {
        return {x: point.x, y: point.y, clipped: false, unitX: dx / length, unitY: dy / length};
    }

    const unitX = dx / length;
    const unitY = dy / length;
    return {
        x: center.x + unitX * maxLength,
        y: center.y + unitY * maxLength,
        clipped: true,
        unitX,
        unitY,
    };
}

export class GatheringDrawing {
    draw(ctx, advisor, drawingUtils, lpX, lpY) {
        if (!ctx || !advisor || !drawingUtils) return;
        const target = advisor.getSelectedTarget();
        if (!target) return;

        const canvasCenter = drawingUtils.getCanvasCenter();
        const center = {x: canvasCenter, y: canvasCenter};
        const projected = drawingUtils.transformPoint(-(target.posX - lpX), target.posY - lpY);
        const maxLength = canvasCenter - 8;
        const end = clipGuide(center, projected, maxLength);

        ctx.save();

        if (advisor.isGathering) {
            ctx.strokeStyle = 'rgba(15, 220, 120, 0.45)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(center.x, center.y, 14, 0, Math.PI * 2);
            ctx.stroke();
        }

        ctx.strokeStyle = GUIDE_COLOR;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(center.x, center.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
        ctx.setLineDash([]);

        if (end.clipped) {
            const tipX = center.x + end.unitX * (maxLength + 10);
            const tipY = center.y + end.unitY * (maxLength + 10);
            ctx.beginPath();
            ctx.moveTo(tipX, tipY);
            ctx.lineTo(tipX - end.unitX * 12 - end.unitY * 6, tipY - end.unitY * 12 + end.unitX * 6);
            ctx.lineTo(tipX - end.unitX * 12 + end.unitY * 6, tipY - end.unitY * 12 - end.unitX * 6);
            ctx.closePath();
            ctx.fillStyle = GUIDE_COLOR;
            ctx.fill();
        } else {
            const pulse = 10 + Math.sin(Date.now() / 200) * 3;
            ctx.beginPath();
            ctx.arc(end.x, end.y, pulse, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(15, 220, 120, 0.7)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        ctx.restore();
    }
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run web/scripts/drawings/_GatheringDrawing.test.js`
Expected: PASS，3 个测试全绿。

- [ ] **Step 5: 接入 RadarRenderer**

在 `RadarRenderer.renderUI()` 的 `this.renderDistanceRings(ctx);` 之后插入：

```js
        this.renderGatheringGuide(ctx);
```

在 `renderUI` 方法之后新增：

```js
    /**
     * Draw the gathering guide line for the selected target.
     */
    renderGatheringGuide(ctx) {
        const advisor = this.handlers.gatheringAdvisor;
        if (!advisor || !settingsSync.getBool('settingShowGatheringTargets', true)) return;
        this.drawings.gatheringDrawing?.draw(ctx, advisor, this.drawingUtils, this.lpX, this.lpY);
    }
```

- [ ] **Step 6: 接入 Utils**

文件顶部 import 区追加（`Utils.js` 目前没有引入 `settingsSync`，必须一并加上）：

```js
import settingsSync from './SettingsSync.js';
import {GatheringAdvisor} from './GatheringAdvisor.js';
import {GatheringDrawing} from '../drawings/GatheringDrawing.js';
import * as GatheringPanel from '../core/GatheringPanel.js';
```

模块级变量区追加：

```js
let gatheringIntervalId = null;
```

`initializeRadarRenderer` 的 `handlers` 对象追加：

```js
            gatheringAdvisor: handlers.gatheringAdvisor,
```

`drawings` 对象追加：

```js
            gatheringDrawing: drawings.gathering,
```

`initializeRadar()` 中 `handlers.mistsDungeon = new MistsDungeonHandler();` 之后追加：

```js
        handlers.gatheringAdvisor = new GatheringAdvisor();
```

`drawings.mistsDungeon = new MistsDungeonDrawing();` 之后追加：

```js
        drawings.gathering = new GatheringDrawing();
```

在 `playerListIntervalId` 赋值语句之后追加：

```js
        GatheringPanel.init(handlers.gatheringAdvisor);

        gatheringIntervalId = setInterval(() => {
            const advisor = handlers.gatheringAdvisor;
            if (!advisor || !handlers.harvestables) return;
            const player = handlers.players.localPlayer;
            const playerPos = {x: player.posX, y: player.posY};
            const settings = {
                mode: settingsSync.get('settingGatheringSort', 'nearest'),
                maxTargets: settingsSync.getNumber('settingGatheringMaxTargets', 5),
            };
            advisor.update(handlers.harvestables.harvestableList, playerPos, settings);
            handlers.players.setGatheringState(advisor.isGathering);
            GatheringPanel.update(advisor);
        }, 1000);
```

`destroyRadar()` 中清理 `cleanupIntervalId` 之后追加：

```js
    if (gatheringIntervalId) {
        clearInterval(gatheringIntervalId);
        gatheringIntervalId = null;
    }
    GatheringPanel.destroy();
```

`destroyRadar()` 中 `lastPlayerListHash = '';` 之前追加：

```js
    handlers.gatheringAdvisor = null;
    drawings.gathering = null;
```

- [ ] **Step 7: 运行全部单测**

Run: `npx vitest run`
Expected: PASS。若出现与本计划无关的既有失败，记录失败用例名并在后续任务中确认不是本次改动引入。

- [ ] **Step 8: Commit**

```bash
git add web/scripts/drawings/GatheringDrawing.js web/scripts/drawings/_GatheringDrawing.test.js web/scripts/utils/RadarRenderer.js web/scripts/utils/Utils.js
git commit -m "feat: draw gathering guide line on radar canvas"
```

---

## Task 8: 玩法模式与资源筛选入口

**Files:**
- Create: `web/scripts/drawings/_HarvestablesDrawing.test.js`
- Test: `web/scripts/core/_GatheringPanel.test.js`（追加）
- Modify: `web/scripts/drawings/HarvestablesDrawing.js:18-20`（invalidate 入口）
- Modify: `web/scripts/core/GatheringPanel.js`（模式切换与收起）
- Modify: `internal/templates/pages/radar.gohtml`（模式控件与筛选按钮）
- Modify: `web/scripts/utils/RadarRenderer.js`（引导线模式守卫）

- [ ] **Step 1: 写失败测试**

在 `web/scripts/core/_GatheringPanel.test.js` 追加：

```js
const {renderModeSwitch, shouldShowTargets} = await import('./GatheringPanel.js');

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
```

创建 `web/scripts/drawings/_HarvestablesDrawing.test.js`：

```js
import {describe, test, expect, vi} from 'vitest';

vi.mock('../utils/SettingsSync.js', () => ({
    default: {
        get: vi.fn((_k, d) => d),
        getBool: vi.fn((_k, d) => d ?? true),
        getNumber: vi.fn((_k, d) => d),
        getJSON: vi.fn(() => null),
    },
}));

const {shouldDrawResourceLayer} = await import('./HarvestablesDrawing.js');

describe('shouldDrawResourceLayer', () => {
    test('采集模式绘制资源图层', () => {
        expect(shouldDrawResourceLayer('gather')).toBe(true);
        expect(shouldDrawResourceLayer(undefined)).toBe(true);
    });

    test('常规模式跳过资源图层', () => {
        expect(shouldDrawResourceLayer('roam')).toBe(false);
    });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `npx vitest run web/scripts/core/_GatheringPanel.test.js web/scripts/drawings/_HarvestablesDrawing.test.js`
Expected: FAIL，`shouldShowTargets` / `renderModeSwitch` / `shouldDrawResourceLayer` 未导出。

- [ ] **Step 3: 实现模式判定**

`GatheringPanel.js` 顶部追加导出：

```js
export function shouldShowTargets(mode) {
    return mode !== 'roam';
}

export function renderModeSwitch(mode) {
    const current = shouldShowTargets(mode) ? 'gather' : 'roam';
    return `<label class="flex items-center gap-2">
        <span class="text-xs text-base-content/60">模式</span>
        <select id="settingGatheringMode" class="select select-sm select-bordered">
            <option value="gather"${current === 'gather' ? ' selected' : ''}>采集模式</option>
            <option value="roam"${current === 'roam' ? ' selected' : ''}>常规模式</option>
        </select>
    </label>`;
}
```

`HarvestablesDrawing.js` 顶部（import 之后）追加：

```js
export function shouldDrawResourceLayer(mode) {
    return mode !== 'roam';
}
```

在 `HarvestablesDrawing` 的 `invalidate(ctx, harvestables)` 方法第一行插入：

```js
        if (!shouldDrawResourceLayer(settingsSync.get('settingGatheringMode', 'gather'))) return;
```

`RadarRenderer` 每帧会调用 `canvasManager.clearDynamicLayers()`（第 187 行），所以提前返回不会留下上一帧的资源点位。

- [ ] **Step 4: 运行测试确认通过**

Run: `npx vitest run web/scripts/core/_GatheringPanel.test.js web/scripts/drawings/_HarvestablesDrawing.test.js`
Expected: PASS。

- [ ] **Step 5: 卡片头部加入模式切换与筛选入口**

在 `radar.gohtml` 的目标卡片头部，把排序下拉所在的 `div` 替换为：

```html
                <div class="flex items-center gap-2 flex-wrap">
                    <span id="gatheringModeSwitch"></span>
                    <select id="settingGatheringSort" class="select select-sm select-bordered">
                        <option value="nearest">就近优先</option>
                        <option value="tier">高级优先</option>
                        <option value="efficiency">效率优先</option>
                    </select>
                    <input type="number" id="settingGatheringMaxTargets" class="input input-sm input-bordered w-16" min="1" max="10" title="Max targets">
                    <a href="/resources" target="_blank" rel="noopener" class="btn btn-sm btn-ghost">采集筛选</a>
                </div>
```

在 `radar.gohtml` 脚本中，`settingGatheringSort` 绑定之后追加：

```js
    const modeSwitchEl = document.getElementById('gatheringModeSwitch');
    if (modeSwitchEl) {
        const mode = settingsSync.get('settingGatheringMode', 'gather');
        modeSwitchEl.innerHTML = renderModeSwitch(mode);
        const modeSelect = modeSwitchEl.querySelector('#settingGatheringMode');
        addListener(modeSelect, 'change', () => settingsSync.set('settingGatheringMode', modeSelect.value));
    }
```

该脚本顶部需要能访问 `renderModeSwitch`。在脚本的 import 区追加：

```js
    const {renderModeSwitch} = await import('/scripts/core/GatheringPanel.js');
```

- [ ] **Step 6: 常规模式收起列表与引导线**

`GatheringPanel.update` 开头改为：

```js
export function update(advisor) {
    if (!elements?.list || !advisor) return;

    const mode = settingsSync.get('settingGatheringMode', 'gather');
    if (elements.modeSwitch) {
        const current = shouldShowTargets(mode) ? 'gather' : 'roam';
        const select = elements.modeSwitch.querySelector('#settingGatheringMode');
        if (select && select.value !== current) select.value = current;
    }

    const showTargets = shouldShowTargets(mode) && settingsSync.getBool('settingShowGatheringTargets', true);
    elements.list.classList.toggle('hidden', !showTargets);
    elements.compass?.classList.toggle('hidden', !showTargets);
    elements.empty?.classList.toggle('hidden', !showTargets || advisor.targets.length > 0);
    elements.badge?.classList.toggle('hidden', !showTargets || !advisor.isGathering);
    if (!showTargets) return;

    const state = advisor.getState();
```

删除原先 `const visible = settingsSync.getBool(...)` 与 `elements.card?.classList.toggle('hidden', !visible)` 两行，卡片头部始终可见，保证模式开关可达。

`GatheringPanel.init` 的 `elements` 增加一项：

```js
        modeSwitch: document.getElementById('gatheringModeSwitch'),
```

- [ ] **Step 7: 引导线跟随模式**

`RadarRenderer.renderGatheringGuide` 的守卫改为：

```js
        const mode = settingsSync.get('settingGatheringMode', 'gather');
        if (mode === 'roam') return;
        if (!advisor || !settingsSync.getBool('settingShowGatheringTargets', true)) return;
```

- [ ] **Step 8: 运行全部单测**

Run: `npx vitest run`
Expected: PASS。

- [ ] **Step 9: Commit**

```bash
git add web/scripts/drawings/HarvestablesDrawing.js web/scripts/drawings/_HarvestablesDrawing.test.js web/scripts/core/GatheringPanel.js web/scripts/core/_GatheringPanel.test.js internal/templates/pages/radar.gohtml web/scripts/utils/RadarRenderer.js
git commit -m "feat: add gather/roam mode and resource filter entry"
```

---

## Task 9: 手动验收

**Files:** 无改动。

- [ ] **Step 1: 启动应用**

按项目 README 的启动方式运行（`go run .` 或对应 Make 目标），打开雷达页。

- [ ] **Step 2: 逐项验证**

- [ ] 目标卡片显示前 5 个节点，含 `T7.2`、方位箭头、距离、剩余层数。
- [ ] 第一名目标在雷达上出现虚线与脉冲圈；悬停其他行时引导线切换。
- [ ] 目标超出缩放可见范围时，虚线止于圆边界并出现箭头。
- [ ] 切换"就近 / 高级 / 效率"排序后列表顺序变化。
- [ ] 采集节点后标题出现"采集中"，停止采集约 8 秒后消失。
- [ ] 开启 `settingGatherAlertMode` 并在红区采集时，任意玩家出现会触发提示；关闭后恢复原规则。
- [ ] 玩家离开后卡片显示 `left Xs ago` 并在 30 秒内移除。
- [ ] 切换到"常规模式"后资源点位、目标列表、方位盘、引导线全部消失，玩家与地下城仍正常显示。
- [ ] 常规模式下卡片头部仍然可见，可直接切回"采集模式"且资源点位在下一帧恢复。
- [ ] 刷新页面后玩法模式保持上次选择。
- [ ] 点击"采集筛选"在新标签页打开 `/resources`，雷达页不跳转。
- [ ] 在 `/resources` 只勾选 Fiber（棉）与 T5/T6 后回到雷达页，目标列表只剩棉的 T5/T6 节点，且雷达显示一致。
- [ ] 切换到其他页面再返回，无重复定时器、无重复卡片。

- [ ] **Step 3: 记录结果**

把验证结果写入本计划对应勾选项；若有失败项，回到对应任务修复，不要跳过。

---

## 验收对照（Spec 覆盖检查）

| Spec 章节 | 对应任务 |
|---|---|
| 4.1 过滤 / 4.2 打分 / 4.3 输出 | Task 1 |
| 5.1 屏幕空间方位、迷你方位盘 | Task 1（方位）、Task 6（方位盘） |
| 5.2 引导线与视野外箭头 | Task 7 |
| 6 采集态识别 | Task 2、Task 3 |
| 7 采集模式告警、离开状态 | Task 4、Task 5 |
| 8 设置项 | Task 6（排序、目标数）、Task 8（玩法模式） |
| 8.1 玩法模式 | Task 8 |
| 8.2 资源筛选入口 | Task 8（`/resources` 跳转） |
| 9 刷新与性能 | Task 6（hash 跳重绘）、Task 7（1s 定时器） |
| 10 边界处理 | Task 1（坐标缺失）、Task 3（选中回落）、Task 5（保留期）、Task 7（销毁清理）、Task 8（模式切换） |
| 11 测试 | 各任务单测 + Task 9 |
