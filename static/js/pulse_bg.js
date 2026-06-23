/* ═══════════════════════════════════════════════════════════
   EVENT PULSE — INTERACTIVE BACKGROUND  ("Living Pulse")
   Place at: static/js/pulse_bg.js
   Load in base.html AFTER gsap, BEFORE main.js
   Renders into the existing <canvas id="aurora-canvas">.
   ─────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  if (typeof gsap === 'undefined') return;
  const canvas = document.getElementById('aurora-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const TAU    = Math.PI * 2;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const rand   = gsap.utils.random;

  /* ── Palette (brand) ──────────────────────── */
  const PRIMARY   = [75, 107, 241];
  const SECONDARY = [124, 58, 237];
  const PINK      = [236, 72, 153];
  const BG        = '#0A0A0F';

  /* ── Tunables ─────────────────────────────── */
  const isMobile  = window.innerWidth < 768;
  const STAR_N    = isMobile ? 42 : 92;
  const LINK_DIST = 132;        // particle-to-particle link range
  const CURSOR_D  = 190;        // cursor pull range for links
  const DRAW_LINKS = !isMobile; // skip O(n²) links on phones

  /* ── Viewport / DPR ───────────────────────── */
  let vw, vh, DPR, vignette;
  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    vw  = window.innerWidth;
    vh  = window.innerHeight;
    canvas.width  = Math.round(vw * DPR);
    canvas.height = Math.round(vh * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    vignette = ctx.createRadialGradient(vw * 0.5, vh * 0.42, vh * 0.25, vw * 0.5, vh * 0.5, vh * 0.95);
    vignette.addColorStop(0, 'rgba(10,10,15,0)');
    vignette.addColorStop(1, 'rgba(10,10,15,0.62)');
  }

  /* ── Glow orbs (irregular placement, GSAP-tweened) ── */
  const orbDefs = [
    { fx: 0.10, fy: 0.16, r: 300, c: PRIMARY,   depth: 0.6 },
    { fx: 0.86, fy: 0.24, r: 250, c: SECONDARY, depth: 1.1 },
    { fx: 0.71, fy: 0.82, r: 320, c: SECONDARY, depth: 0.8 },
    { fx: 0.21, fy: 0.77, r: 232, c: PINK,      depth: 1.3 },
    { fx: 0.49, fy: 0.43, r: 210, c: PRIMARY,   depth: 0.4 },
  ];
  const orbs = orbDefs.map((d) => {
    const g = ctx.createRadialGradient(0, 0, 0, 0, 0, d.r);
    g.addColorStop(0,   `rgba(${d.c[0]},${d.c[1]},${d.c[2]},0.55)`);
    g.addColorStop(0.5, `rgba(${d.c[0]},${d.c[1]},${d.c[2]},0.14)`);
    g.addColorStop(1,   `rgba(${d.c[0]},${d.c[1]},${d.c[2]},0)`);
    return { ...d, grad: g, ox: 0, oy: 0, scale: 1, glow: 0.9 };
  });

  /* ── Particles ────────────────────────────── */
  let particles = [];
  function seedParticles() {
    particles = Array.from({ length: STAR_N }, () => {
      const bvx = rand(-0.12, 0.12), bvy = rand(-0.12, 0.12);
      return {
        x: rand(0, vw), y: rand(0, vh),
        vx: bvx, vy: bvy, bvx, bvy,
        r: rand(0.4, 2.0), tw: rand(0, TAU),
      };
    });
  }

  /* ── Ripples ──────────────────────────────── */
  const ripples = [];
  function ping(x, y, o) {
    o = o || {};
    const rp = {
      x, y, r: 0,
      alpha: o.alpha != null ? o.alpha : 0.45,
      width: o.width || 1.2,
      c: o.color || PRIMARY,
    };
    const max = o.max || Math.max(vw, vh) * 0.5;
    const dur = o.dur || 5.5;
    ripples.push(rp);
    gsap.to(rp, { r: max, duration: dur, ease: 'power2.out' });
    gsap.to(rp, {
      alpha: 0, duration: dur, ease: 'power1.in',
      onComplete: () => { const i = ripples.indexOf(rp); if (i > -1) ripples.splice(i, 1); },
    });
  }

  function ambientColor() {
    const roll = Math.random();
    return roll < 0.5 ? PRIMARY : roll < 0.82 ? SECONDARY : PINK;
  }
  function scheduleAmbient() {
    gsap.delayedCall(rand(2.4, 5.2), () => {
      if (!document.hidden) {
        ping(rand(0.10, 0.90) * vw, rand(0.12, 0.88) * vh, {
          alpha: 0.40, color: ambientColor(), width: 1.1,
          dur: rand(5, 7), max: Math.max(vw, vh) * rand(0.42, 0.6),
        });
      }
      scheduleAmbient();
    });
  }

  /* ── Pointer (parallax + cursor links) ────── */
  let curX = -999, curY = -999, hasCursor = false;
  let parX = 0, parY = 0, tParX = 0, tParY = 0;

  function onMove(e) {
    curX = e.clientX; curY = e.clientY; hasCursor = true;
    tParX = (e.clientX / vw - 0.5) * -42;
    tParY = (e.clientY / vh - 0.5) * -42;
  }
  function onLeave() { hasCursor = false; curX = curY = -999; }
  function onDown(e) {
    // Don't interrupt form usage; ping everywhere else
    if (e.target.closest && e.target.closest('input, textarea, select')) return;
    const c = ambientColor();
    ping(e.clientX, e.clientY, {
      alpha: 0.7, color: c, width: 2,
      dur: 4.6, max: Math.max(vw, vh) * 0.62,
    });
    // shove nearby particles outward
    for (const p of particles) {
      const dx = p.x - e.clientX, dy = p.y - e.clientY;
      const d = Math.hypot(dx, dy);
      if (d < 170 && d > 0.01) {
        const f = (170 - d) / 170 * 1.6;
        p.vx += (dx / d) * f; p.vy += (dy / d) * f;
      }
    }
  }

  /* ── Render ───────────────────────────────── */
  function draw() {
    if (document.hidden) return;

    parX += (tParX - parX) * 0.05;
    parY += (tParY - parY) * 0.05;

    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, vw, vh);

    // orbs (additive glow)
    ctx.globalCompositeOperation = 'lighter';
    for (const o of orbs) {
      ctx.save();
      ctx.translate(o.fx * vw + o.ox + parX * o.depth, o.fy * vh + o.oy + parY * o.depth);
      ctx.scale(o.scale, o.scale);
      ctx.globalAlpha = o.glow;
      ctx.fillStyle = o.grad;
      ctx.beginPath();
      ctx.arc(0, 0, o.r, 0, TAU);
      ctx.fill();
      ctx.restore();
    }
    ctx.globalAlpha = 1;

    // particle links
    if (DRAW_LINKS) {
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d = dx * dx + dy * dy;
          if (d < LINK_DIST * LINK_DIST) {
            const t = 1 - Math.sqrt(d) / LINK_DIST;
            ctx.strokeStyle = `rgba(124,58,237,${t * 0.13})`;
            ctx.lineWidth = 0.6;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
      }
    }

    // particles + cursor links
    for (const p of particles) {
      p.vx += (p.bvx - p.vx) * 0.03;
      p.vy += (p.bvy - p.vy) * 0.03;
      p.x += p.vx; p.y += p.vy; p.tw += 0.02;
      if (p.x < -10) p.x = vw + 10; else if (p.x > vw + 10) p.x = -10;
      if (p.y < -10) p.y = vh + 10; else if (p.y > vh + 10) p.y = -10;

      if (hasCursor) {
        const dx = curX - p.x, dy = curY - p.y;
        const d = Math.hypot(dx, dy);
        if (d < CURSOR_D) {
          const t = 1 - d / CURSOR_D;
          ctx.strokeStyle = `rgba(120,150,255,${t * 0.32})`;
          ctx.lineWidth = 0.7;
          ctx.beginPath(); ctx.moveTo(curX, curY); ctx.lineTo(p.x, p.y); ctx.stroke();
        }
      }

      const a = 0.35 + Math.sin(p.tw) * 0.32;
      ctx.fillStyle = `rgba(180,200,255,${Math.max(0, a)})`;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, TAU); ctx.fill();
    }

    // ripples
    for (const rp of ripples) {
      ctx.beginPath();
      ctx.arc(rp.x, rp.y, rp.r, 0, TAU);
      ctx.strokeStyle = `rgba(${rp.c[0]},${rp.c[1]},${rp.c[2]},${rp.alpha})`;
      ctx.lineWidth = rp.width;
      ctx.shadowColor = `rgba(${rp.c[0]},${rp.c[1]},${rp.c[2]},${rp.alpha})`;
      ctx.shadowBlur = 14;
      ctx.stroke();
    }
    ctx.shadowBlur = 0;

    // vignette keeps content readable
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, vw, vh);
  }

  /* ── Boot ─────────────────────────────────── */
  resize();
  seedParticles();
  window.addEventListener('resize', () => { resize(); seedParticles(); });

  if (reduce) {
    draw(); // single static frame, no motion
    return;
  }

  orbs.forEach((o, i) => {
    gsap.to(o, {
      ox: rand(-90, 90), oy: rand(-70, 70), scale: rand(0.82, 1.24),
      duration: rand(15, 27), repeat: -1, yoyo: true, ease: 'sine.inOut', delay: i * 0.7,
    });
    gsap.to(o, {
      glow: rand(0.65, 1), duration: rand(6, 11), repeat: -1, yoyo: true, ease: 'sine.inOut',
    });
  });

  window.addEventListener('pointermove', onMove, { passive: true });
  window.addEventListener('pointerleave', onLeave);
  window.addEventListener('pointerdown', onDown, { passive: true });

  gsap.ticker.add(draw);
  scheduleAmbient();
})();
