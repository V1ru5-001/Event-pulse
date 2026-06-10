/* ═══════════════════════════════════════════
   EVENTPULSE — MAIN JS
   ═══════════════════════════════════════════ */

/* ── NAVBAR SCROLL ───────────────────────── */
const nav = document.getElementById('epNav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 40);
  }, { passive: true });
}

/* ── AVATAR DROPDOWN — CLICK TO OPEN ────── */
const avatarBtn    = document.getElementById('avatarBtn');
const userDropdown = document.getElementById('userDropdown');
const userMenu     = document.getElementById('userMenu');

if (avatarBtn && userDropdown) {
  avatarBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    userDropdown.classList.toggle('open');
  });
  document.addEventListener('click', (e) => {
    if (userMenu && !userMenu.contains(e.target)) {
      userDropdown.classList.remove('open');
    }
  });
}

/* ── PASSWORD EYE TOGGLE ─────────────────── */
document.querySelectorAll('.ep-field__eye').forEach((btn) => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const wrap  = btn.closest('.ep-field__input-wrap');
    if (!wrap) return;
    const input = wrap.querySelector('input[type="password"], input[type="text"]');
    if (!input) return;
    const eyeShow = btn.querySelector('.eye-show');
    const eyeHide = btn.querySelector('.eye-hide');
    if (input.type === 'password') {
      input.type = 'text';
      if (eyeShow) eyeShow.style.display = 'none';
      if (eyeHide) eyeHide.style.display = 'block';
    } else {
      input.type = 'password';
      if (eyeShow) eyeShow.style.display = 'block';
      if (eyeHide) eyeHide.style.display = 'none';
    }
  });
});

/* ── CATEGORY FILTER ─────────────────────── */
document.querySelectorAll('.ep-cat').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.ep-cat').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const cat = btn.dataset.cat;
    document.querySelectorAll('.ep-card').forEach((card) => {
      const show = cat === 'all' || card.dataset.cat === cat;
      card.style.display = show ? '' : 'none';
      if (show) {
        card.style.animation = 'none';
        void card.offsetWidth;
        card.style.animation = '';
      }
    });
  });
});

/* ── 3D CARD TILT ────────────────────────── */
document.querySelectorAll('.ep-card').forEach((card) => {
  card.addEventListener('mousemove', (e) => {
    const rect = card.getBoundingClientRect();
    const cx   = rect.left + rect.width  / 2;
    const cy   = rect.top  + rect.height / 2;
    const dx   = (e.clientX - cx) / (rect.width  / 2);
    const dy   = (e.clientY - cy) / (rect.height / 2);
    card.style.transform = `perspective(900px) rotateY(${dx * 5}deg) rotateX(${-dy * 5}deg) translateY(-6px) scale(1.01)`;
  });
  card.addEventListener('mouseleave', () => {
    card.style.transform = '';
  });
});

/* ── PASSWORD STRENGTH ───────────────────── */
const pwInput      = document.getElementById('id_password1');
const strengthFill = document.getElementById('strengthFill');
const strengthLbl  = document.getElementById('strengthLabel');

if (pwInput && strengthFill) {
  pwInput.addEventListener('input', () => {
    const v   = pwInput.value;
    let score = 0;
    if (v.length >= 8)          score++;
    if (/[A-Z]/.test(v))        score++;
    if (/[0-9]/.test(v))        score++;
    if (/[^A-Za-z0-9]/.test(v)) score++;
    const pct   = ['0%','35%','65%','100%'][score] || '0%';
    const cls   = ['','weak','medium','strong','strong'][score];
    const label = ['','Weak','Fair','Good','Strong'][score];
    strengthFill.style.width = pct;
    strengthFill.className   = 'ep-strength__fill ep-strength__fill--' + cls;
    if (strengthLbl) strengthLbl.textContent = label;
  });
}

/* ── STUDENT FIELDS TOGGLE (register) ───── */
const roleInputs    = document.querySelectorAll('input[name="role"]');
const studentFields = document.getElementById('studentFields');

if (roleInputs.length && studentFields) {
  function toggleStudentFields() {
    const sel = document.querySelector('input[name="role"]:checked');
    studentFields.style.display = (sel && sel.value === 'student') ? '' : 'none';
  }
  roleInputs.forEach(r => r.addEventListener('change', toggleStudentFields));
  toggleStudentFields();
}

/* ── AUTO-DISMISS MESSAGES ───────────────── */
document.querySelectorAll('.ep-message').forEach((msg) => {
  setTimeout(() => { msg.style.transition = 'opacity .4s'; msg.style.opacity = '0'; }, 4000);
  setTimeout(() => msg.remove(), 4400);
});

/* ── PRELOADER ───────────────────────────── */
(function () {
  const pl       = document.getElementById('ep-preloader');
  const plCanvas = document.getElementById('pl-stars');
  const bar      = document.getElementById('plBar');
  const statusEl = document.getElementById('plStatus');
  if (!pl || !plCanvas) return;

  const ctx = plCanvas.getContext('2d');
  let W = window.innerWidth;
  let H = window.innerHeight;
  plCanvas.width  = W;
  plCanvas.height = H;

  window.addEventListener('resize', () => {
    W = plCanvas.width  = window.innerWidth;
    H = plCanvas.height = window.innerHeight;
  });

  /* stars */
  const colors = ['#A5B4FC', '#C4B5FD', '#F9A8D4', '#ffffff', '#BAE6FD'];
  const stars = Array.from({ length: 220 }, () => ({
    x:     Math.random() * W,
    y:     Math.random() * H,
    r:     Math.random() * 1.6 + 0.3,
    alpha: Math.random() * 0.8 + 0.1,
    speed: Math.random() * 0.003 + 0.001,
    phase: Math.random() * Math.PI * 2,
    color: colors[Math.floor(Math.random() * colors.length)],
  }));

  /* shooting stars */
  function newShoot(delay) {
    return {
      x:    Math.random() * W * 0.8 + W * 0.1,
      y:    Math.random() * H * 0.4,
      vx:   -(Math.random() * 3 + 2),
      vy:    Math.random() * 2 + 1,
      len:   Math.random() * 80 + 60,
      age:   0,
      life:  90,
      delay: delay,
      born:  false,
    };
  }
  let shoots = Array.from({ length: 4 }, (_, i) => newShoot(i * 800));

  let t = 0, rafId;

  function drawFrame() {
    ctx.clearRect(0, 0, W, H);
    t++;

    stars.forEach(s => {
      s.alpha = 0.15 + 0.7 * (0.5 + 0.5 * Math.sin(s.phase + t * s.speed * 60));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle   = s.color;
      ctx.globalAlpha = s.alpha;
      ctx.fill();
    });

    shoots.forEach((s, i) => {
      if (!s.born && t * 16.7 < s.delay) return;
      s.born = true;
      s.age++;
      s.x += s.vx;
      s.y += s.vy;
      if (s.age > s.life) { shoots[i] = newShoot(s.life + Math.random() * 200 + 60); return; }
      const p = s.age / s.life;
      const a = p < 0.2 ? p / 0.2 : p > 0.8 ? (1 - p) / 0.2 : 1;
      const g = ctx.createLinearGradient(s.x, s.y, s.x - s.vx * s.len * 0.3, s.y - s.vy * s.len * 0.3);
      g.addColorStop(0,   'rgba(255,255,255,' + (a * 0.9) + ')');
      g.addColorStop(0.4, 'rgba(167,139,250,' + (a * 0.5) + ')');
      g.addColorStop(1,   'rgba(75,107,241,0)');
      ctx.globalAlpha = 1;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(s.x - s.vx * s.len * 0.3, s.y - s.vy * s.len * 0.3);
      ctx.strokeStyle = g;
      ctx.lineWidth   = 1.5;
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(s.x, s.y, 1.5, 0, Math.PI * 2);
      ctx.fillStyle   = '#fff';
      ctx.globalAlpha = a;
      ctx.fill();
    });

    ctx.globalAlpha = 1;
    rafId = requestAnimationFrame(drawFrame);
  }
  drawFrame();

  /* progress bar — tied to real load events */
  let progress = 0;
  function setBar(pct) {
    progress = Math.max(progress, pct);
    if (bar) bar.style.width = progress + '%';
  }

  setBar(20);
  document.addEventListener('DOMContentLoaded', () => setBar(55));
  setTimeout(() => setBar(75), 600);
  setTimeout(() => setBar(88), 1200);

  /* status messages */
  const msgs = ['Loading events…', 'Fetching campus news…', 'Almost ready…', 'Preparing your feed…'];
  let mi = 0;
  const msgInterval = setInterval(() => {
    mi = (mi + 1) % msgs.length;
    if (statusEl) statusEl.textContent = msgs[mi];
  }, 700);

  
  /* hide on full load */
function hidePl() {
  setBar(100);
  clearInterval(msgInterval);
  setTimeout(() => {
    cancelAnimationFrame(rafId);
    pl.classList.add('hidden');
    setTimeout(() => { pl.style.display = 'none'; }, 650);
  }, 400);
  const creepInterval = setInterval(() => {
    if (progress < 95) setBar(progress + 1);
  }, 1000);
}

if (document.readyState === 'complete') {
  hidePl();
} else {
  window.addEventListener('load', hidePl);
}
})();
