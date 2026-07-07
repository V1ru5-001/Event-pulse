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

/* ── PRELOADER — wordmark + fill line, hardened ── */
(function () {
  const pl       = document.getElementById('ep-preloader');
  if (!pl) return;
  const bar      = document.getElementById('plBar');
  const statusEl = document.getElementById('plStatus');
  const shownAt  = Date.now();
  const MIN_SHOW = 500;   // always visible at least this long
  const MAX_SHOW = 4000;  // never block the page longer than this
  let hidden = false;

  let progress = 0;
  function setBar(pct) {
    progress = Math.max(progress, Math.min(pct, 100));
    if (bar) bar.style.width = progress + '%';
  }

  setBar(20);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { setBar(60); });
  } else {
    setBar(60);
  }
  setTimeout(function () { setBar(80); }, 400);
  setTimeout(function () { setBar(92); }, 900);

  const msgs = ['Loading events…', 'Fetching campus news…', 'Preparing your feed…'];
  let mi = 0;
  const msgInterval = setInterval(function () {
    mi = (mi + 1) % msgs.length;
    if (statusEl) statusEl.textContent = msgs[mi];
  }, 800);

  function hidePl() {
    if (hidden) return;
    hidden = true;
    setBar(100);
    clearInterval(msgInterval);
    const wait = Math.max(0, MIN_SHOW - (Date.now() - shownAt));
    setTimeout(function () {
      pl.classList.add('hidden');
      pl.style.pointerEvents = 'none';
      pl.style.display = 'none';
      setTimeout(function () { pl.style.display = 'none'; }, 500);
    }, wait + 250);
  }

  if (document.readyState === 'complete') {
    hidePl();
  } else {
    window.addEventListener('load', hidePl);
  }
  // fail-safe: hide no matter what (slow images, JS errors elsewhere, etc.)
  setTimeout(hidePl, MAX_SHOW);
})();