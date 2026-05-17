import * as THREE from 'three';

const CANVAS_W = 256;
const CANVAS_H = 160;

export default class TabletRenderer {
  constructor() {
    this.canvas = document.createElement('canvas');
    this.canvas.width = CANVAS_W;
    this.canvas.height = CANVAS_H;
    this.ctx = this.canvas.getContext('2d');
    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.minFilter = THREE.LinearFilter;
    this._animFrame = 0;
  }

  update(robotState, tabletVisible, tabletUrl, tabletImage) {
    this._animFrame++;
    const ctx = this.ctx;

    if (tabletVisible && (tabletUrl || tabletImage)) {
      this._drawContent(ctx, tabletUrl, tabletImage);
    } else {
      this._drawState(ctx, robotState);
    }

    this.texture.needsUpdate = true;
  }

  _drawState(ctx, state) {
    ctx.fillStyle = '#1c1c1e';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    switch (state) {
      case 'speaking':
        this._drawWaveform(ctx);
        break;
      case 'thinking':
        this._drawThinking(ctx);
        break;
      case 'listening':
        this._drawListening(ctx);
        break;
      default:
        this._drawIdle(ctx);
    }
  }

  _drawIdle(ctx) {
    const cx = CANVAS_W / 2;
    const cy = CANVAS_H / 2;
    const pulse = 0.4 + Math.sin(this._animFrame * 0.03) * 0.2;
    ctx.beginPath();
    ctx.arc(cx, cy, 12, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(138, 186, 138, ${pulse})`;
    ctx.fill();
    ctx.font = '12px sans-serif';
    ctx.fillStyle = `rgba(153, 153, 153, ${pulse + 0.3})`;
    ctx.textAlign = 'center';
    ctx.fillText('IDLE', cx, cy + 30);
  }

  _drawWaveform(ctx) {
    const cx = CANVAS_W / 2;
    const cy = CANVAS_H / 2;
    const barCount = 8;
    const barWidth = 10;
    const gap = 6;
    const totalWidth = barCount * barWidth + (barCount - 1) * gap;
    const startX = cx - totalWidth / 2;

    for (let i = 0; i < barCount; i++) {
      const phase = this._animFrame * 0.15 + i * 0.8;
      const height = 15 + Math.sin(phase) * 25;
      const x = startX + i * (barWidth + gap);
      const y = cy - height / 2;
      ctx.fillStyle = '#8aba8a';
      ctx.fillRect(x, y, barWidth, height);
    }

    ctx.font = '10px sans-serif';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.fillText('SPEAKING', cx, cy + 50);
  }

  _drawThinking(ctx) {
    const cx = CANVAS_W / 2;
    const cy = CANVAS_H / 2;
    const dotCount = 3;
    const gap = 20;
    const startX = cx - (dotCount - 1) * gap / 2;

    for (let i = 0; i < dotCount; i++) {
      const phase = this._animFrame * 0.08 + i * 1.2;
      const radius = 4 + Math.sin(phase) * 2;
      const alpha = 0.4 + Math.sin(phase) * 0.4;
      ctx.beginPath();
      ctx.arc(startX + i * gap, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(229, 229, 229, ${alpha})`;
      ctx.fill();
    }

    ctx.font = '10px sans-serif';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.fillText('THINKING', cx, cy + 35);
  }

  _drawListening(ctx) {
    const cx = CANVAS_W / 2;
    const cy = CANVAS_H / 2;
    const ringCount = 3;

    for (let i = 0; i < ringCount; i++) {
      const phase = (this._animFrame * 0.04 + i * 0.5) % 1;
      const radius = 8 + phase * 30;
      const alpha = (1 - phase) * 0.6;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(138, 186, 138, ${alpha})`;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(cx, cy, 6, 0, Math.PI * 2);
    ctx.fillStyle = '#8aba8a';
    ctx.fill();

    ctx.font = '10px sans-serif';
    ctx.fillStyle = '#666';
    ctx.textAlign = 'center';
    ctx.fillText('LISTENING', cx, cy + 40);
  }

  _drawContent(ctx, url, image) {
    ctx.fillStyle = '#1c1c1e';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    if (url) {
      ctx.font = 'bold 14px sans-serif';
      ctx.fillStyle = '#e5e5e5';
      ctx.textAlign = 'center';
      ctx.fillText('Web Content', CANVAS_W / 2, 40);

      ctx.font = '10px sans-serif';
      ctx.fillStyle = '#999';
      const displayUrl = url.length > 35 ? url.substring(0, 35) + '...' : url;
      ctx.fillText(displayUrl, CANVAS_W / 2, 60);

      ctx.fillStyle = '#8aba8a';
      ctx.fillRect(CANVAS_W / 2 - 40, 80, 80, 3);
    } else if (image) {
      ctx.font = '12px sans-serif';
      ctx.fillStyle = '#999';
      ctx.textAlign = 'center';
      ctx.fillText('Image', CANVAS_W / 2, CANVAS_H / 2);
    }
  }

  dispose() {
    this.texture.dispose();
  }
}
