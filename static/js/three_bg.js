/* ═══════════════════════════════════════════
   CAMPUSPULSE — THREE.JS BACKGROUND
   Place this file at: static/js/three_bg.js
   Load it in base.html BEFORE main.js
   ═══════════════════════════════════════════ */

(function () {
  'use strict';

  // Only run if Three.js is available
  if (typeof THREE === 'undefined') return;

  const canvas = document.getElementById('aurora-canvas');
  if (!canvas) return;

  /* ── SCENE SETUP ─────────────────────────── */
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x0A0A0F, 1);

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
  camera.position.z = 5;

  /* ── SIZE ────────────────────────────────── */
  function resize() {
    const W = window.innerWidth;
    const H = window.innerHeight;
    renderer.setSize(W, H);
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener('resize', resize);

  /* ── PARTICLE FIELD ──────────────────────── */
  const PARTICLE_COUNT = 1800;
  const positions  = new Float32Array(PARTICLE_COUNT * 3);
  const colors     = new Float32Array(PARTICLE_COUNT * 3);
  const sizes      = new Float32Array(PARTICLE_COUNT);
  const velocities = [];

  const palette = [
    new THREE.Color(0x4B6BF1),
    new THREE.Color(0x7C3AED),
    new THREE.Color(0x3B82F6),
    new THREE.Color(0x8B5CF6),
    new THREE.Color(0xA78BFA),
  ];

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const i3 = i * 3;
    positions[i3]     = (Math.random() - 0.5) * 20;
    positions[i3 + 1] = (Math.random() - 0.5) * 20;
    positions[i3 + 2] = (Math.random() - 0.5) * 10;

    const col = palette[Math.floor(Math.random() * palette.length)];
    colors[i3]     = col.r;
    colors[i3 + 1] = col.g;
    colors[i3 + 2] = col.b;

    sizes[i] = Math.random() * 3 + 1;

    velocities.push({
      x: (Math.random() - 0.5) * 0.004,
      y: (Math.random() - 0.5) * 0.004,
      z: 0,
    });
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color',    new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('size',     new THREE.BufferAttribute(sizes, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uTime:  { value: 0 },
      uMouse: { value: new THREE.Vector2(0, 0) },
    },
    vertexShader: `
      attribute float size;
      attribute vec3 color;
      varying vec3 vColor;
      uniform float uTime;
      uniform vec2 uMouse;
      void main() {
        vColor = color;
        vec3 pos = position;

        // subtle drift with time
        pos.x += sin(uTime * 0.3 + position.y * 0.5) * 0.08;
        pos.y += cos(uTime * 0.2 + position.x * 0.5) * 0.08;

        // mouse repulsion
        vec4 mvPos = modelViewMatrix * vec4(pos, 1.0);
        vec2 screenPos = mvPos.xy;
        vec2 diff = screenPos - uMouse * vec2(5.0, 3.0);
        float dist = length(diff);
        if (dist < 2.5) {
          float force = (2.5 - dist) / 2.5;
          pos.xy += normalize(diff) * force * 0.6;
        }

        gl_PointSize = size * (300.0 / -mvPos.z);
        gl_Position  = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      void main() {
        float d = distance(gl_PointCoord, vec2(0.5));
        if (d > 0.5) discard;
        float alpha = smoothstep(0.5, 0.1, d) * 0.75;
        gl_FragColor = vec4(vColor, alpha);
      }
    `,
    transparent: true,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const particles = new THREE.Points(geo, mat);
  scene.add(particles);

  /* ── CONNECTING LINES ────────────────────── */
  const lineMat = new THREE.LineBasicMaterial({
    color: 0x4B6BF1,
    transparent: true,
    opacity: 0.06,
    blending: THREE.AdditiveBlending,
  });

  // Build a sparse connection mesh (every 8th particle)
  const linePositions = [];
  const step = 8;
  for (let i = 0; i < PARTICLE_COUNT; i += step) {
    for (let j = i + step; j < Math.min(i + step * 6, PARTICLE_COUNT); j += step) {
      const i3 = i * 3, j3 = j * 3;
      const dx = positions[i3] - positions[j3];
      const dy = positions[i3+1] - positions[j3+1];
      const dist = Math.sqrt(dx*dx + dy*dy);
      if (dist < 4) {
        linePositions.push(
          positions[i3], positions[i3+1], positions[i3+2],
          positions[j3], positions[j3+1], positions[j3+2]
        );
      }
    }
  }

  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(linePositions), 3));
  const lines = new THREE.LineSegments(lineGeo, lineMat);
  scene.add(lines);

  /* ── AURORA MESH PLANES ──────────────────── */
  function makeAurora(color, x, y, scaleX, scaleY, opacity) {
    const g = new THREE.PlaneGeometry(scaleX, scaleY, 32, 32);
    const m = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(g, m);
    mesh.position.set(x, y, -2);

    // warp the plane vertices
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      pos.setZ(i, (Math.random() - 0.5) * 0.5);
    }
    pos.needsUpdate = true;
    return mesh;
  }

  const aurora1 = makeAurora(0x4B6BF1, -4, 2, 10, 6, 0.04);
  const aurora2 = makeAurora(0x7C3AED, 4, -2, 8, 5, 0.035);
  const aurora3 = makeAurora(0x3B82F6, 0, 3, 7, 4, 0.03);
  scene.add(aurora1, aurora2, aurora3);

  /* ── MOUSE ───────────────────────────────── */
  const mouse = new THREE.Vector2(0, 0);
  const targetMouse = new THREE.Vector2(0, 0);

  window.addEventListener('mousemove', (e) => {
    targetMouse.x = (e.clientX / window.innerWidth)  * 2 - 1;
    targetMouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
  });

  /* ── ANIMATION LOOP ──────────────────────── */
  const clock = new THREE.Clock();

  function animate() {
    requestAnimationFrame(animate);
    const t = clock.getElapsedTime();

    // smooth mouse lerp
    mouse.x += (targetMouse.x - mouse.x) * 0.05;
    mouse.y += (targetMouse.y - mouse.y) * 0.05;

    // update shader uniforms
    mat.uniforms.uTime.value  = t;
    mat.uniforms.uMouse.value = mouse;

    // slow camera drift following mouse
    camera.position.x += (mouse.x * 0.4 - camera.position.x) * 0.03;
    camera.position.y += (mouse.y * 0.3 - camera.position.y) * 0.03;
    camera.lookAt(scene.position);

    // rotate particle cloud very slowly
    particles.rotation.y = t * 0.015;
    particles.rotation.x = t * 0.008;

    // aurora planes breathe
    aurora1.material.opacity = 0.04 + Math.sin(t * 0.4) * 0.02;
    aurora2.material.opacity = 0.035 + Math.sin(t * 0.3 + 1) * 0.015;
    aurora3.material.opacity = 0.03  + Math.sin(t * 0.5 + 2) * 0.015;

    aurora1.rotation.z = t * 0.02;
    aurora2.rotation.z = -t * 0.015;
    aurora3.rotation.z = t * 0.01;

    // update particle positions for drift
    const posAttr = geo.attributes.position;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;
      posAttr.array[i3]     += velocities[i].x;
      posAttr.array[i3 + 1] += velocities[i].y;

      // wrap around bounds
      if (posAttr.array[i3]     >  10) posAttr.array[i3]     = -10;
      if (posAttr.array[i3]     < -10) posAttr.array[i3]     =  10;
      if (posAttr.array[i3 + 1] >  10) posAttr.array[i3 + 1] = -10;
      if (posAttr.array[i3 + 1] < -10) posAttr.array[i3 + 1] =  10;
    }
    posAttr.needsUpdate = true;

    renderer.render(scene, camera);
  }

  animate();
})();
