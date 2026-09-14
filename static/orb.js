/**
 * AANYA — Alexa / Bixby Fluid Morphing Voice Orb Visualizer
 * High-performance HTML5 Canvas fluid animation with multi-octave harmonic deformers.
 */

class VoiceOrbVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    
    // States: 'standby' | 'listening' | 'thinking' | 'speaking' | 'executing'
    this.state = 'standby';
    this.phase = 0;
    this.audioAmplitude = 0;
    this.targetAmplitude = 0;
    this.rotation = 0;

    // Palette per state — soft pastel gradients
    this.colorSchemes = {
      standby: {
        core: ['#b8a4f8', '#e8a4c8', '#a4d8f0'],
        glow: 'rgba(184, 164, 248, 0.35)',
        ring: 'rgba(164, 216, 240, 0.5)'
      },
      listening: {
        core: ['#a890f5', '#86efac', '#6ee7b7'],
        glow: 'rgba(134, 239, 172, 0.45)',
        ring: 'rgba(168, 144, 245, 0.65)'
      },
      thinking: {
        core: ['#f4a8c4', '#fbcfe8', '#c4b5fd'],
        glow: 'rgba(244, 168, 196, 0.45)',
        ring: 'rgba(196, 181, 253, 0.65)'
      },
      speaking: {
        core: ['#93c5fd', '#a78bfa', '#c4b5fd'],
        glow: 'rgba(147, 197, 253, 0.45)',
        ring: 'rgba(167, 139, 250, 0.65)'
      },
      executing: {
        core: ['#fcd34d', '#fdba74', '#fca5a5'],
        glow: 'rgba(253, 186, 116, 0.45)',
        ring: 'rgba(252, 211, 77, 0.65)'
      }
    };

    // Reduced motion check
    this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    this.init();
  }

  init() {
    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width || 250;
    this.height = rect.height || 250;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.ctx.scale(dpr, dpr);
  }

  setState(newState) {
    if (this.colorSchemes[newState]) {
      this.state = newState;
    }
  }

  setAmplitude(amp) {
    this.targetAmplitude = Math.max(0, Math.min(1, amp));
  }

  animate() {
    // Smooth amplitude interpolation
    this.audioAmplitude += (this.targetAmplitude - this.audioAmplitude) * 0.15;

    // Phase progression speed depends on state
    let speed = 0.03;
    if (this.state === 'thinking') speed = 0.07;
    if (this.state === 'speaking') speed = 0.05 + this.audioAmplitude * 0.04;
    if (this.state === 'listening') speed = 0.04 + this.audioAmplitude * 0.05;

    if (!this.reducedMotion) {
      this.phase += speed;
      this.rotation += (this.state === 'thinking' ? 0.05 : 0.01);
    }

    this.draw();
    requestAnimationFrame(this.animate);
  }

  draw() {
    const { ctx, width, height } = this;
    ctx.clearRect(0, 0, width, height);

    const cx = width / 2;
    const cy = height / 2;
    const scheme = this.colorSchemes[this.state] || this.colorSchemes.standby;

    // Dynamic base radius
    let baseRadius = Math.min(width, height) * 0.28;
    if (this.state === 'listening') {
      baseRadius += 10 + this.audioAmplitude * 20;
    } else if (this.state === 'speaking') {
      baseRadius += 8 + this.audioAmplitude * 18;
    } else if (this.state === 'thinking') {
      baseRadius += Math.sin(this.phase * 2) * 5;
    } else {
      // Standby gentle breathe
      baseRadius += Math.sin(this.phase) * 3;
    }

    // 1. Diffuse Ambient Outer Aura
    const outerGrad = ctx.createRadialGradient(cx, cy, baseRadius * 0.4, cx, cy, baseRadius * 1.8);
    outerGrad.addColorStop(0, scheme.glow);
    outerGrad.addColorStop(0.6, scheme.glow.replace(/[\d\.]+\)$/, '0.15)'));
    outerGrad.addColorStop(1, 'rgba(0,0,0,0)');

    ctx.save();
    ctx.fillStyle = outerGrad;
    ctx.beginPath();
    ctx.arc(cx, cy, baseRadius * 1.8, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // 2. Alexa / Bixby Rotating Light Ring
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(this.rotation);
    ctx.beginPath();
    ctx.arc(0, 0, baseRadius * 1.18, 0, Math.PI * 2);
    ctx.lineWidth = 3;
    const ringGrad = ctx.createLinearGradient(-baseRadius, -baseRadius, baseRadius, baseRadius);
    ringGrad.addColorStop(0, scheme.core[0]);
    ringGrad.addColorStop(0.5, 'transparent');
    ringGrad.addColorStop(1, scheme.core[1]);
    ctx.strokeStyle = ringGrad;
    ctx.stroke();
    ctx.restore();

    // 3. Fluid Morphing Organic Core
    ctx.save();
    ctx.translate(cx, cy);

    const points = 64;
    ctx.beginPath();
    for (let i = 0; i <= points; i++) {
      const angle = (i / points) * Math.PI * 2;
      
      // Multi-octave harmonic wave deformation
      let deform = 0;
      if (!this.reducedMotion) {
        const harmonic1 = Math.sin(angle * 3 + this.phase * 1.2) * 4;
        const harmonic2 = Math.cos(angle * 5 - this.phase * 1.8) * 3;
        const harmonic3 = Math.sin(angle * 2 + this.phase * 0.8) * (this.audioAmplitude * 15);
        deform = harmonic1 + harmonic2 + harmonic3;
      }

      const r = baseRadius + deform;
      const x = Math.cos(angle) * r;
      const y = Math.sin(angle) * r;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.closePath();

    // Fluid Internal Color Gradient
    const coreGrad = ctx.createRadialGradient(-baseRadius * 0.25, -baseRadius * 0.25, baseRadius * 0.1, 0, 0, baseRadius * 1.2);
    coreGrad.addColorStop(0, scheme.core[0]);
    coreGrad.addColorStop(0.5, scheme.core[1]);
    coreGrad.addColorStop(1, scheme.core[2]);

    ctx.fillStyle = coreGrad;
    ctx.fill();

    // Soft core glow edge
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.restore();

    // 4. Subtle Inner Specular Light
    const specGrad = ctx.createRadialGradient(cx - baseRadius * 0.35, cy - baseRadius * 0.35, 0, cx, cy, baseRadius * 0.7);
    specGrad.addColorStop(0, 'rgba(255, 255, 255, 0.75)');
    specGrad.addColorStop(0.3, 'rgba(255, 255, 255, 0.25)');
    specGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');

    ctx.save();
    ctx.fillStyle = specGrad;
    ctx.beginPath();
    ctx.arc(cx - baseRadius * 0.25, cy - baseRadius * 0.25, baseRadius * 0.65, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

// Export instance
window.VoiceOrbVisualizer = VoiceOrbVisualizer;
