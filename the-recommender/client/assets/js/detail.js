// Detail page: load a title by ?id= and render its info + similar titles.
(function () {
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  }

  function posterCard(t, matchPct) {
    const year = t.release_date ? '<span><i class="bi bi-calendar3 me-1"></i>' + new Date(t.release_date).getFullYear() + '</span>' : '';
    const img = t.poster_path
      ? '<img src="' + tmdbImage(t.poster_path, 'w342') + '" alt="' + escapeHtml(t.title) + '" class="w-100" loading="lazy" style="aspect-ratio:2/3;object-fit:cover;">'
      : '<div class="w-100 d-flex align-items-center justify-content-center" style="aspect-ratio:2/3;background:var(--surface-2);"><i class="bi bi-film" style="font-size:3rem;color:var(--muted);"></i></div>';
    const rating = '<span class="rating-pill position-absolute top-0 start-0 m-2"><i class="bi bi-star-fill"></i> ' + (t.vote_average || 0).toFixed(1) + '</span>';
    const match = matchPct != null
      ? '<span class="type-badge" style="border-color:rgba(45,212,191,.55);color:#2dd4bf;">' + matchPct + '% Match</span>'
      : '';
    return '<div class="col-6 col-sm-4 col-md-3 col-lg-2 reveal" style="transition-delay:calc(' + 0 + ' * 45ms);">' +
      '<a href="detail.html?id=' + t.id + '" class="poster-card d-block text-decoration-none" aria-label="View ' + escapeHtml(t.title) + '">' +
        img + rating + match +
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

  function render(data) {
    document.title = data.title.title + ' – The Recommender';
    const t = data.title;

    const backdrop = document.getElementById('detailBackdrop');
    if (t.backdrop_path) {
      backdrop.style.backgroundImage = "url('" + tmdbImage(t.backdrop_path, 'w1280') + "')";
    }

    const poster = document.getElementById('detailPoster');
    if (t.poster_path) {
      poster.innerHTML = '<img src="' + tmdbImage(t.poster_path, 'w342') + '" alt="' + escapeHtml(t.title) + '" class="detail-poster img-fluid rounded-4" loading="eager">';
    } else {
      poster.innerHTML = '<div class="detail-poster rounded-4 d-flex align-items-center justify-content-center" style="aspect-ratio:2/3;background:var(--surface-2);"><i class="bi bi-film" style="font-size:4rem;color:var(--muted);"></i></div>';
    }

    document.getElementById('detailTitle').textContent = t.title;
    document.getElementById('detailOverview').textContent = t.overview || 'No overview available yet.';

    let meta = '<span class="rating-pill" style="background:var(--gradient);border:none;color:#0b0d14;"><i class="bi bi-star-fill me-1" style="color:#0b0d14;"></i>' + (t.vote_average || 0).toFixed(1) + '</span>';
    if (t.release_date) meta += '<span class="meta-chip"><i class="bi bi-calendar3 me-1"></i>' + new Date(t.release_date).getFullYear() + '</span>';
    meta += '<span class="meta-chip"><i class="bi bi-film me-1"></i>' + (t.media_type || '').charAt(0).toUpperCase() + (t.media_type || '').slice(1) + '</span>';
    meta += '<span class="meta-chip"><i class="bi bi-activity me-1"></i>' + (t.popularity || 0).toFixed(1) + ' popularity</span>';
    document.getElementById('detailMeta').innerHTML = meta;

    const info = [
      ['Released', formatDate(t.release_date)],
      ['Rating', (t.vote_average || 0).toFixed(1)],
      ['Votes', t.vote_count ? Number(t.vote_count).toLocaleString() : '—'],
      ['Type', (t.media_type || '').charAt(0).toUpperCase() + (t.media_type || '').slice(1)],
      ['Popularity', (t.popularity || 0).toFixed(1)],
      ['Language', t.original_language ? t.original_language.toUpperCase() : '—'],
    ];
    document.getElementById('infoGrid').innerHTML = info.map(([label, value]) =>
      '<div class="col-6 col-md-4 col-lg-2"><div class="info-tile reveal"><small>' + label + '</small><div class="info-value">' + value + '</div></div></div>'
    ).join('');

    const similar = data.similar || [];
    if (similar.length) {
      document.getElementById('similarSection').style.display = '';
      document.getElementById('similarGrid').innerHTML = similar.map(s =>
        posterCard(s, Math.round((parseFloat(s.similarity_score) || 0) * 100))
      ).join('');
    }

    // reveal newly injected elements
    document.querySelectorAll('.reveal').forEach(el => el.classList.add('visible'));
  }

  async function load() {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('id');
    if (!id) {
      document.getElementById('detailError').style.display = '';
      return;
    }
    try {
      const data = await apiFetch('/titles/' + encodeURIComponent(id));
      render(data);
    } catch (err) {
      document.getElementById('detailError').style.display = '';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    load();

    // Parallax backdrop
    const bg = document.getElementById('detailBackdrop');
    window.addEventListener('scroll', () => {
      if (bg) bg.style.transform = 'translateY(' + (window.scrollY * 0.35) + 'px)';
    }, { passive: true });

    // Action buttons with toast feedback
    document.querySelectorAll('.action-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const msg = btn.dataset.toast || 'Done';
        const icon = btn.dataset.icon || 'bi-check2-circle';
        btn.style.transform = 'scale(.95)';
        window.showToast(msg, icon);
        setTimeout(() => { btn.style.transform = ''; }, 350);
      });
    });
  });
})();