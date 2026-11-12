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
    // (0,0) 是"尚未收到本地坐标"的哨兵值，不是合法位置
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
        if (!harvestable) continue;
        const size = Number(harvestable.size);
        if (!Number.isFinite(size) || size <= 0) continue;
        if (!filter(harvestable)) continue;

        let distance = null;
        let bearingDeg = null;
        const hasCoords = hasPos
            && Number.isFinite(harvestable.posX)
            && Number.isFinite(harvestable.posY);
        if (hasCoords) {
            distance = distanceBetween(harvestable, playerPos);
            if (distance > MAX_RANGE) continue;
            const vector = toScreenVector(harvestable, playerPos, rotate);
            // bearingDeg 以画布 +X 为 0 度、Y 轴向下、顺时针增大（不是罗盘以正北为 0 度）
            bearingDeg = Math.atan2(vector.y, vector.x) * 180 / Math.PI;
        }

        if (size > maxSize) maxSize = size;
        candidates.push({harvestable, size, distance, bearingDeg});
    }

    return candidates
        .map(({harvestable, size, distance, bearingDeg}) => {
            const proximity = distance === null ? 0 : 1 - distance / MAX_RANGE;
            const score = weights.distance * proximity
                + weights.tier * ((harvestable.tier || 0) / 8)
                + weights.enchant * ((harvestable.charges || 0) / 4)
                + weights.size * (size / maxSize);

            return {
                id: harvestable.id,
                posX: harvestable.posX,
                posY: harvestable.posY,
                stringType: harvestable.stringType,
                tier: harvestable.tier,
                enchant: harvestable.charges,
                size,
                isLiving: !isPureStatic(harvestable),
                distance,
                bearingDeg,
                score,
            };
        })
        .sort((a, b) => {
            if (a.score !== b.score) return b.score - a.score;
            if (a.distance === null && b.distance === null) return a.id - b.id;
            if (a.distance === null) return 1;
            if (b.distance === null) return -1;
            if (a.distance !== b.distance) return a.distance - b.distance;
            return a.id - b.id;
        })
        .slice(0, maxTargets);
}
