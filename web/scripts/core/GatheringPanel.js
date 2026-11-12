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
