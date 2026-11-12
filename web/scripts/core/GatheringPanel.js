import settingsSync from '../utils/SettingsSync.js';
import {MAX_RANGE} from '../utils/GatheringAdvisor.js';

const ICON_TYPES = {
    log: 'log', wood: 'log', logs: 'log',
    rock: 'rock', fiber: 'fiber', hide: 'hide', ore: 'ore',
};

const COMPASS_SIZE = 68;
const COMPASS_CENTER = 34;
const COMPASS_RADIUS = 30;

let elements = null;
let advisorRef = null;
let clickHandler = null;
let hoverHandler = null;
let modeSelectRef = null;
let modeChangeHandler = null;
let lastHash = '';

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

export function renderTargetRow(target, selectedId) {
    const tier = Number.isFinite(target.tier) ? target.tier : 0;
    const enchant = Number.isFinite(target.enchant) ? target.enchant : 0;
    const type = ICON_TYPES[(target.stringType || '').toLowerCase()] || 'rock';
    const icon = `/images/Resources/${type}_${tier}_${enchant}.webp`;
    const distance = Number.isFinite(target.distance) ? `${Math.round(target.distance)}m` : '--';
    const arrow = Number.isFinite(target.bearingDeg)
        ? `<i class="inline-block text-xs text-base-content/60" style="transform: rotate(${Math.round(target.bearingDeg)}deg)">➜</i>`
        : '<span class="text-xs text-base-content/40">--</span>';
    const active = target.id === selectedId
        ? 'bg-primary/10 border-primary/40'
        : 'border-transparent hover:bg-base-300/60';
    const dimmed = target.size <= 0 ? 'opacity-40' : '';

    return `<div class="flex items-center gap-3 px-3 py-2 rounded-lg border ${active} ${dimmed} cursor-pointer transition-colors" data-target-id="${target.id}">
        <img src="${icon}" alt="" class="w-6 h-6 object-contain" loading="lazy">
        <span class="font-mono text-xs text-base-content/70">T${tier}.${enchant}</span>
        <span class="text-sm text-base-content/80 flex-1 truncate">${target.stringType || '?'}</span>
        <span class="flex items-center gap-1">${arrow}<span class="text-xs text-base-content/60">${distance}</span></span>
        <span class="font-mono text-xs text-base-content/50">${target.size}</span>
    </div>`;
}

export function renderCompass(targets, selectedId) {
    const dots = (targets || []).map(target => {
        if (!Number.isFinite(target.distance) || !Number.isFinite(target.bearingDeg)) return '';
        const radians = target.bearingDeg * Math.PI / 180;
        const ratio = Math.min(1, target.distance / MAX_RANGE);
        const cx = (COMPASS_CENTER + Math.cos(radians) * ratio * COMPASS_RADIUS).toFixed(1);
        const cy = (COMPASS_CENTER + Math.sin(radians) * ratio * COMPASS_RADIUS).toFixed(1);
        const active = target.id === selectedId;
        return `<circle cx="${cx}" cy="${cy}" r="${active ? 3 : 2}" fill="currentColor" opacity="${active ? 1 : 0.45}"/>`;
    }).join('');

    return `<svg viewBox="0 0 ${COMPASS_SIZE} ${COMPASS_SIZE}" width="${COMPASS_SIZE}" height="${COMPASS_SIZE}" class="text-base-content/60" aria-hidden="true">
        <circle cx="${COMPASS_CENTER}" cy="${COMPASS_CENTER}" r="${COMPASS_RADIUS}" fill="none" stroke="currentColor" stroke-opacity="0.2"/>
        <circle cx="${COMPASS_CENTER}" cy="${COMPASS_CENTER}" r="2.5" fill="currentColor"/>
        ${dots}
    </svg>`;
}

export function init(advisor) {
    destroy();
    advisorRef = advisor;
    elements = {
        card: document.getElementById('gatheringCard'),
        list: document.getElementById('gatheringTargets'),
        empty: document.getElementById('gatheringEmpty'),
        badge: document.getElementById('gatheringStateBadge'),
        noPosition: document.getElementById('gatheringNoPosition'),
        compass: document.getElementById('gatheringCompass'),
        modeSwitch: document.getElementById('gatheringModeSwitch'),
    };
    if (!elements.list) return;

    if (elements.modeSwitch) {
        elements.modeSwitch.innerHTML = renderModeSwitch(settingsSync.get('settingGatheringMode', 'gather'));
        modeSelectRef = elements.modeSwitch.querySelector('#settingGatheringMode');
        if (modeSelectRef) {
            modeChangeHandler = () => settingsSync.set('settingGatheringMode', modeSelectRef.value);
            modeSelectRef.addEventListener('change', modeChangeHandler);
        }
    }

    const selectFromEvent = event => {
        const row = event.target.closest('[data-target-id]');
        if (!row || !advisorRef) return;
        const id = Number(row.dataset.targetId);
        if (advisorRef.getState().selectedId === id) return;
        advisorRef.select(id);
    };
    clickHandler = selectFromEvent;
    hoverHandler = selectFromEvent;
    elements.list.addEventListener('click', clickHandler);
    elements.list.addEventListener('mouseover', hoverHandler);
    lastHash = '';
}

export function update(advisor) {
    if (!elements?.list || !advisor) return;

    const mode = settingsSync.get('settingGatheringMode', 'gather');
    if (elements.modeSwitch) {
        const current = shouldShowTargets(mode) ? 'gather' : 'roam';
        const select = elements.modeSwitch.querySelector('#settingGatheringMode');
        if (select && select.value !== current) select.value = current;
    }

    const state = advisor.getState();
    const showTargets = shouldShowTargets(mode) && settingsSync.getBool('settingShowGatheringTargets', true);
    const waitingForPosition = showTargets && state.targets.length > 0
        && state.targets.every(t => t.distance === null);

    elements.list.classList.toggle('hidden', !showTargets);
    elements.compass?.classList.toggle('hidden', !showTargets);
    elements.empty?.classList.toggle('hidden', !showTargets || state.targets.length > 0);
    elements.badge?.classList.toggle('hidden', !showTargets || !state.isGathering);
    elements.noPosition?.classList.toggle('hidden', !waitingForPosition);
    if (!showTargets) {
        lastHash = '';
        return;
    }

    const hash = `${state.selectedId}:${state.isGathering}:`
        + state.targets.map(t => `${t.id}:${t.size}:${t.distance === null ? '-' : Math.round(t.distance)}:${t.bearingDeg === null ? '-' : Math.round(t.bearingDeg)}`).join(',');
    if (hash === lastHash) return;
    lastHash = hash;

    elements.list.innerHTML = state.targets.map(t => renderTargetRow(t, state.selectedId)).join('');
    if (elements.compass) {
        elements.compass.innerHTML = renderCompass(state.targets, state.selectedId);
    }
}

export function destroy() {
    if (elements?.list) {
        if (clickHandler) elements.list.removeEventListener('click', clickHandler);
        if (hoverHandler) elements.list.removeEventListener('mouseover', hoverHandler);
    }
    if (modeSelectRef && modeChangeHandler) {
        modeSelectRef.removeEventListener('change', modeChangeHandler);
    }
    elements = null;
    advisorRef = null;
    clickHandler = null;
    hoverHandler = null;
    modeSelectRef = null;
    modeChangeHandler = null;
    lastHash = '';
}
