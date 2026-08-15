// Index page: browse all titles with search + pagination.
(function () {
  const PER_PAGE = 12;

  function posterCard(t) {
    const year = t.release_date ? '<span><i class="bi bi-calendar3 me-1"></i>' + new Date(t.release_date).getFullYear() + '</span>' : '';
    const img = t.poster_path
      ? '<img src="' + tmdbImage(t.poster_path, 'w342') + '" alt="' + escapeHtml(t.title) + '" class="w-100" loading="lazy" style="aspect-ratio:2/3;object-fit:cover;">'
      : '<div class="w-100 d-flex align-items-center justify-content-center" style="aspect-ratio:2/3;background:var(--surface-2);"><i class="bi bi-film" style="font-size:3rem;color:var(--muted);"></i></div>';
    const rating = '<span class="rating-pill position-absolute top-0 start-0 m-2"><i class="bi bi-star-fill"></i> ' + (t.vote_average || 0).toFixed(1) + '</span>';
    const type = t.media_type ? '<span class="type-badge">' + t.media_type.toUpperCase() + '</span>' : '';
    return '<div class="col-6 col-sm-4 col-md-3 col-lg-2 reveal" style="transition-delay:calc(' + 0 + ' * 45ms);">' +
      '<a href="detail.html?id=' + t.id + '" class="poster-card d-block text-decoration-none" aria-label="View ' + escapeHtml(t.title) + '">' +
        img + rating + type +
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

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function renderPagination(page, totalPages, total, query) {
    const wrap = document.getElementById('paginationWrap');
    const info = document.getElementById('paginationInfo');
    const ul = document.getElementById('pagination');
    if (totalPages <= 1) { wrap.style.display = 'none'; return; }
    wrap.style.display = '';
    const start = (page - 1) * PER_PAGE + 1;
    const end = Math.min(page * PER_PAGE, total);
    info.textContent = 'Showing ' + start + '–' + end + ' of ' + total;
    let html = '';
    const qs = query ? ('&q=' + encodeURIComponent(query)) : '';
    html += '<li class="page-item ' + (page === 1 ? 'disabled' : '') + '"><a class="page-link" href="index.html?page=' + (page - 1) + qs + '" aria-label="Previous"><i class="bi bi-chevron-left"></i></a></li>';
    for (let p = 1; p <= totalPages; p++) {
      if (p === page || p === 1 || p === totalPages || (p >= page - 1 && p <= page + 1)) {
        html += '<li class="page-item ' + (p === page ? 'active' : '') + '"><a class="page-link" href="index.html?page=' + p + qs + '">' + p + '</a></li>';
      } else if (p === page - 2 || p === page + 2) {
        html += '<li class="page-item disabled"><span class="page-link">…</span></li>';
      }
    }
    html += '<li class="page-item ' + (page === totalPages ? 'disabled' : '') + '"><a class="page-link" href="index.html?page=' + (page + 1) + qs + '" aria-label="Next"><i class="bi bi-chevron-right"></i></a></li>';
    ul.innerHTML = html;
  }

  async function load() {
    const params = new URLSearchParams(window.location.search);
    const page = parseInt(params.get('page') || '1', 10);
    const q = (params.get('q') || '').trim();

    const loading = document.getElementById('loading');
    const grid = document.getElementById('posterGrid');
    const empty = document.getElementById('emptyState');
    const titleEl = document.getElementById('sectionTitle');
    loading.style.display = '';
    grid.innerHTML = '';
    empty.style.display = 'none';

    // keep navbar + hero search boxes in sync with the current query
    document.querySelectorAll('input[type="search"]').forEach(inp => { inp.value = q; });

    let path = '/titles?page=' + page + '&per_page=' + PER_PAGE;
    if (q) path += '&q=' + encodeURIComponent(q);
    if (q) {
      titleEl.textContent = 'Results for "' + q + '"';
    } else {
      titleEl.textContent = 'Latest Releases';
    }

    try {
      const data = await apiFetch(path);
      const titles = data.titles || [];
      loading.style.display = 'none';
      if (!titles.length) {
        empty.style.display = '';
        return;
      }
      grid.innerHTML = titles.map(posterCard).join('');
      renderPagination(data.page || 1, data.total_pages || 1, data.total || 0, q);
      if ('IntersectionObserver' in window) {
        const ro = new IntersectionObserver((entries) => {
          entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); ro.unobserve(e.target); } });
        }, { threshold: .12, rootMargin: '0px 0px -40px 0px' });
        grid.querySelectorAll('.reveal').forEach(el => ro.observe(el));
      } else {
        grid.querySelectorAll('.reveal').forEach(el => el.classList.add('visible'));
      }
    } catch (err) {
      loading.style.display = 'none';
      empty.style.display = '';
    }
  }

  document.addEventListener('DOMContentLoaded', load);
})();