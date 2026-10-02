/* EventPulse — small behaviours for pages on the new design (body.epx). */

/* ── Save / unsave an event without a page reload ── */
document.addEventListener('submit', function (e) {
  var form = e.target;
  if (!form.classList || !form.classList.contains('epx-save-form')) return;
  e.preventDefault();
  var btn = form.querySelector('.epx-save');
  btn.disabled = true;
  fetch(form.action, {
    method: 'POST',
    body: new FormData(form),
    headers: { 'X-Requested-With': 'XMLHttpRequest' },
    credentials: 'same-origin'
  }).then(function (res) {
    if (!res.ok) throw new Error('save failed');
    return res.json();
  }).then(function (data) {
    btn.classList.toggle('is-saved', data.saved);
    btn.setAttribute('aria-pressed', data.saved ? 'true' : 'false');
    btn.setAttribute('aria-label', data.saved ? 'Remove from saved' : 'Save event');
    btn.title = data.saved ? 'Saved' : 'Save';
    if (!data.saved && form.classList.contains('js-remove-on-unsave')) {
      var card = form.closest('[data-saved-card]');
      if (card) card.remove();
      var left = document.querySelectorAll('[data-saved-card]').length;
      var count = document.getElementById('savedCount');
      if (count) count.textContent = left;
      var empty = document.getElementById('savedEmpty');
      if (empty && !left) empty.hidden = false;
    }
  }).catch(function () {
    form.submit();
  }).finally(function () {
    btn.disabled = false;
  });
});
