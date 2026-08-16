// Personalize page: render the quiz, submit to the API, show ranked results.
(function () {
  let quizConfig = null;
  let favorites = [];

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function posterCard(t, matchPct) {
    const year = t.release_date ? '<span><i class="bi bi-calendar3 me-1"></i>' + releaseYear(t.release_date) + '</span>' : '';
    const img = t.poster_path
      ? '<img src="' + tmdbImage(t.poster_path, 'w342') + '" alt="' + escapeHtml(t.title) + '" class="w-100" loading="lazy" style="aspect-ratio:2/3;object-fit:cover;">'
      : '<div class="w-100 d-flex align-items-center justify-content-center" style="aspect-ratio:2/3;background:var(--surface-2);"><i class="bi bi-film" style="font-size:3rem;color:var(--muted);"></i></div>';
    const rating = '<span class="rating-pill position-absolute top-0 start-0 m-2"><i class="bi bi-star-fill"></i> ' + (t.vote_average || 0).toFixed(1) + '</span>';
    const type = t.media_type ? '<span class="type-badge">' + t.media_type.toUpperCase() + '</span>' : '';
    const match = matchPct != null
      ? '<span class="type-badge" style="border-color:rgba(45,212,191,.55);color:#2dd4bf;">' + matchPct + '% Match</span>'
      : '';
    return '<div class="col-6 col-sm-4 col-md-3 col-lg-2">' +
      '<a href="detail.html?id=' + t.id + '" class="poster-card d-block text-decoration-none" aria-label="View ' + escapeHtml(t.title) + '">' +
        img + rating + type + match +
        '<span class="card-overlay">' +
          '<span class="text-white fw-semibold" style="font-size:.95rem;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">' + escapeHtml(t.title) + '</span>' +
          '<span class="d-flex align-items-center gap-2 mt-1 small" style="color:var(--muted);">' +
            year +
            '<span class="badge-view ms-auto"><i class="bi bi-arrow-up-right"></i></span>' +
          '</span>' +
        '</span>' +
      '</a>' +
    '</div>';
  }

  function renderMoods(cfg) {
    const box = document.getElementById('moodOptions');
    let html = '';
    for (const [key, meta] of Object.entries(cfg.moods)) {
      html += '<div class="form-check m-0">' +
        '<input class="form-check-input" type="checkbox" name="mood" id="mood-' + key + '" value="' + key + '">' +
        '<label class="opt-chip" for="mood-' + key + '">' +
          '<i class="bi ' + meta.icon + '"></i>' + escapeHtml(meta.label) + '<i class="bi bi-check2 check"></i>' +
        '</label>' +
      '</div>';
    }
    box.innerHTML = html;
  }

  function renderHardNo(cfg) {
    const box = document.getElementById('hardNoOptions');
    let html = '';
    for (const [key, meta] of Object.entries(cfg.hard_no)) {
      html += '<div class="form-check m-0">' +
        '<input class="form-check-input" type="checkbox" name="hard_no" id="hn-' + key + '" value="' + key + '">' +
        '<label class="opt-chip" for="hn-' + key + '" title="' + escapeHtml(meta.desc) + '">' +
          '<i class="bi bi-x-octagon"></i>' + escapeHtml(meta.label) + '<i class="bi bi-check2 check"></i>' +
        '</label>' +
      '</div>';
    }
    box.innerHTML = html;
  }

  function renderRuntime(cfg) {
    const box = document.getElementById('runtimeOptions');
    let html = box.querySelector('.form-check').outerHTML; // "Any length" option
    for (const [key, label] of Object.entries(cfg.runtime_options)) {
      html += '<div class="form-check m-0">' +
        '<input class="form-check-input" type="radio" name="runtime" id="rt-' + key + '" value="' + key + '">' +
        '<label class="opt-chip" for="rt-' + key + '"><i class="bi bi-hourglass-split"></i>' + escapeHtml(label) + '<i class="bi bi-check2 check"></i></label>' +
      '</div>';
    }
    box.innerHTML = html;
  }

  function renderFavorites() {
    const grid = document.getElementById('favoriteGrid');
    if (!favorites.length) {
      grid.innerHTML = '<div class="col-12"><p class="fav-note mb-0">No curated favorites available right now — type any title above instead.</p></div>';
      return;
    }
    let html = '';
    favorites.forEach(f => {
      const img = f.poster_path
        ? '<img src="' + tmdbImage(f.poster_path, 'w185') + '" alt="' + escapeHtml(f.title) + '" loading="lazy">'
        : '<div class="w-100 d-flex align-items-center justify-content-center" style="aspect-ratio:2/3;background:var(--surface-2);"><i class="bi bi-film" style="font-size:1.6rem;color:var(--muted);"></i></div>';
      html += '<div class="col-4 col-sm-3 col-md-2 col-lg-1-5">' +
        '<div class="fav-item" data-id="' + f.id + '" data-title="' + escapeHtml(f.title) + '" data-type="' + f.media_type + '">' +
          img +
          '<span class="fav-badge">' + (f.media_type === 'movie' ? 'MOVIE' : 'SERIES') + '</span>' +
          '<span class="fav-name">' + escapeHtml(f.title) + '</span>' +
        '</div>' +
      '</div>';
    });
    grid.innerHTML = html;
    wireFavoritePicker();
  }

  function wireFavoritePicker() {
    const favHidden = document.getElementById('favoriteIds');
    const favText = document.getElementById('favoriteText');
    const favCount = document.getElementById('favCount');
    function syncFavorites() {
      const selected = Array.from(document.querySelectorAll('.fav-item.selected')).map(i => i.dataset.id);
      favHidden.value = selected.join(',');
      favCount.textContent = selected.length
        ? (selected.length === 1 ? '1 favorite selected' : selected.length + ' favorites selected')
        : 'Pick a few favorites';
    }
    document.querySelectorAll('.fav-item').forEach(item => {
      item.addEventListener('click', () => {
        if (favText.value.trim()) favText.value = '';
        item.classList.toggle('selected');
        syncFavorites();
      });
    });
    favText.addEventListener('input', () => {
      if (favText.value.trim()) {
        document.querySelectorAll('.fav-item').forEach(i => i.classList.remove('selected'));
        syncFavorites();
      }
    });
  }

  function wireSkips() {
    document.querySelectorAll('[data-skip]').forEach(btn => {
      btn.addEventListener('click', () => {
        const card = document.querySelector('[data-question="' + btn.dataset.skip + '"]');
        card.classList.toggle('skipped');
        const skipped = card.classList.contains('skipped');
        card.querySelectorAll('input').forEach(inp => {
          inp.disabled = skipped;
          if (skipped) inp.checked = false;
        });
        if (skipped) {
          // Clear any picked favorites so a skipped Q3 doesn't submit them.
          card.querySelectorAll('.fav-item.selected').forEach(i => i.classList.remove('selected'));
          const favHidden = document.getElementById('favoriteIds');
          const favText = document.getElementById('favoriteText');
          const favCount = document.getElementById('favCount');
          if (favHidden) favHidden.value = '';
          if (favText) favText.value = '';
          if (favCount) favCount.textContent = 'Pick a few favorites';
        }
        btn.textContent = skipped ? 'Restore question' : 'Skip this question';
      });
    });
  }

  function collectAnswers(form) {
    const favHidden = document.getElementById('favoriteIds');
    const favText = document.getElementById('favoriteText');
    return {
      media_type: (form.querySelector('input[name="media_type"]:checked') || {}).value || '',
      moods: Array.from(form.querySelectorAll('input[name="mood"]:checked')).map(i => i.value),
      hard_no: Array.from(form.querySelectorAll('input[name="hard_no"]:checked')).map(i => i.value),
      runtime: (form.querySelector('input[name="runtime"]:checked') || {}).value || 'any',
      favorite_ids: (favHidden.value || '').split(',').filter(Boolean).map(x => parseInt(x, 10)),
      favorite_text: (favText.value || '').trim(),
    };
  }

  function showResults(data) {
    const quizView = document.getElementById('quizView');
    const resultsView = document.getElementById('resultsView');
    quizView.style.display = 'none';
    resultsView.style.display = '';

    const results = data.results || [];
    let chips = '';
    const lastAnswers = window._lastAnswers || {};
    if (lastAnswers.media_type) {
      chips += '<span class="result-chip"><i class="bi bi-film"></i>' + (lastAnswers.media_type === 'movie' ? 'Movies' : 'Series') + '</span>';
    }
    (lastAnswers.moods || []).forEach(m => {
      if (quizConfig && quizConfig.moods[m]) {
        chips += '<span class="result-chip"><i class="bi ' + quizConfig.moods[m].icon + '"></i>' + escapeHtml(quizConfig.moods[m].label) + '</span>';
      }
    });
    const favCount = (lastAnswers.favorite_ids || []).length;
    if (lastAnswers.favorite_text || favCount) {
      chips += '<span class="result-chip"><i class="bi bi-heart"></i>' + (favCount ? favCount + ' favorite' + (favCount === 1 ? '' : 's') : 'typed favorite') + '</span>';
    }
    (lastAnswers.hard_no || []).forEach(h => {
      if (quizConfig && quizConfig.hard_no[h]) {
        chips += '<span class="result-chip"><i class="bi bi-x-octagon"></i>' + escapeHtml(quizConfig.hard_no[h].label) + '</span>';
      }
    });
    if (lastAnswers.runtime && lastAnswers.runtime !== 'any' && quizConfig && quizConfig.runtime_options[lastAnswers.runtime]) {
      chips += '<span class="result-chip"><i class="bi bi-hourglass-split"></i>' + escapeHtml(quizConfig.runtime_options[lastAnswers.runtime]) + '</span>';
    }

    let html = '<section class="pt-4 pb-5" id="picks">' +
      '<div class="container px-3 px-md-5">' +
        '<div class="section-head reveal visible">' +
          '<span class="section-kicker"><i class="bi bi-stars me-1"></i> Your personalized picks</span>' +
          '<h2 class="section-title">Made for you</h2>';
    if (results.length) {
      const total = data.total || 0;
      html += '<p class="result-count mt-3 mb-2">' + results.length + ' of ' + total.toLocaleString() + ' titles in our database match your answers.</p>' +
        (chips ? '<div class="d-flex flex-wrap gap-2 justify-content-center">' + chips + '</div>' : '');
    }
    html += '<div class="mt-4"><a href="personalize.html" class="btn btn-ghost"><i class="bi bi-arrow-counterclockwise me-2"></i>Take another round</a></div>' +
      '</div>';

    if (results.length) {
      html += '<div class="row g-4 mt-1" id="posterGrid">' + results.map(t => posterCard(t)).join('') + '</div>';
    } else {
      html += '<div class="empty-state text-center mt-4"><div class="empty-icon mx-auto mb-3"><i class="bi bi-funnel"></i></div>' +
        '<h3 class="fw-semibold mb-2">No matches yet</h3>' +
        '<p class="muted mb-4">Your answers were too strict for my catalog. Loosen a couple of hard no’s and try again.</p>' +
        '<a href="personalize.html" class="btn btn-gradient"><i class="bi bi-arrow-counterclockwise me-2"></i>Take another round</a></div>';
    }
    html += '</div></section>';
    resultsView.innerHTML = html;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function init() {
    try {
      quizConfig = await apiFetch('/config');
      renderMoods(quizConfig);
      renderHardNo(quizConfig);
      renderRuntime(quizConfig);
    } catch (err) {
      document.getElementById('moodOptions').innerHTML = '<p class="fav-note mb-0">Could not load quiz config.</p>';
    }

    try {
      const data = await apiFetch('/favorites?limit=24');
      favorites = data.favorites || [];
    } catch (err) {
      favorites = [];
    }
    renderFavorites();
    wireSkips();

    const form = document.getElementById('quizForm');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const answers = collectAnswers(form);
      window._lastAnswers = answers;
      const btn = form.querySelector('.btn-submit');
      const original = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Finding your picks…';
      try {
        const data = await apiFetch('/personalize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(answers),
        });
        showResults(data);
      } catch (err) {
        window.showToast('Something went wrong. Please try again.', 'bi-exclamation-triangle');
        btn.disabled = false;
        btn.innerHTML = original;
      }
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();