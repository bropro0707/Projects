// API configuration for The Recommender client.
//
// When Flask also serves the client/ folder (default dev setup), leave this as ''
// so requests go to the same origin.
//
// When the client is hosted separately (e.g. on GitHub Pages / Netlify), point
// this at the server, e.g.:
//   window.API_BASE = 'https://your-server.example.com';
window.API_BASE = '';

// Convert a TMDB image path into a full CDN URL.
function tmdbImage(path, size) {
  if (!path) return '';
  if (!path.startsWith('/')) path = '/' + path;
  return 'https://image.tmdb.org/t/p/' + (size || 'w342') + path;
}

// Extract the year from a 'YYYY-MM-DD' date. We read the first four characters
// instead of `new Date(...).getFullYear()` because a date-only ISO string is
// parsed as UTC midnight, which can shift the year by one in negative-offset
// timezones for releases on Jan 1.
function releaseYear(iso) {
  if (!iso) return '';
  const m = String(iso).match(/^(\d{4})/);
  return m ? m[1] : '';
}

// Helper that prefixes the API base and parses JSON.
async function apiFetch(path, options) {
  const base = (window.API_BASE || '').replace(/\/+$/, '');
  const res = await fetch(base + '/api' + path, options);
  if (!res.ok) throw new Error('API request failed: ' + res.status);
  return res.json();
}

// Shared showToast helper (used by detail page).
window.showToast = function (message, icon) {
  icon = icon || 'bi-check2-circle';
  const stack = document.getElementById('toastStack');
  if (!stack) return;
  const t = document.createElement('div');
  t.className = 'app-toast';
  t.innerHTML = '<i class="bi ' + icon + '"></i><span></span>';
  t.querySelector('span').textContent = message;
  stack.appendChild(t);
  setTimeout(() => {
    t.classList.add('hide');
    setTimeout(() => t.remove(), 300);
  }, 2400);
};