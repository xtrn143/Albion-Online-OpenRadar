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
