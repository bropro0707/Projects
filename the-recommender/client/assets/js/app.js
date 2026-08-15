// Shared UI behaviours for all pages.
(function () {
  // Navbar scroll effect
  const navbar = document.getElementById('mainNavbar');
  if (navbar) {
    window.addEventListener('scroll', () => {
      navbar.classList.toggle('scrolled', window.scrollY > 20);
    }, { passive: true });
  }

  // Navbar search: hide on load while the big hero search is on screen,
  // reveal it once the user scrolls past the hero search bar.
  const navbarSearch = document.getElementById('navbarSearch');
  const heroSearch = document.querySelector('.hero-search');
  if (navbar && navbarSearch && heroSearch) {
    const hideNavSearch = () => {
      navbarSearch.classList.add('search-hidden');
      navbar.classList.add('search-centered');
    };
    const showNavSearch = () => {
      navbarSearch.classList.remove('search-hidden');
      navbar.classList.remove('search-centered');
    };
    if ('IntersectionObserver' in window) {
      const so = new IntersectionObserver(entries => {
        entries.forEach(e => { e.isIntersecting ? hideNavSearch() : showNavSearch(); });
      }, { threshold: 0 });
      so.observe(heroSearch);
    } else {
      hideNavSearch();
      window.addEventListener('scroll', () => {
        heroSearch.getBoundingClientRect().bottom <= 0 ? showNavSearch() : hideNavSearch();
      }, { passive: true });
    }
  }

  // Scroll reveal
  const revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const ro = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); ro.unobserve(e.target); } });
    }, { threshold: .12, rootMargin: '0px 0px -40px 0px' });
    revealEls.forEach(el => ro.observe(el));
  } else {
    revealEls.forEach(el => el.classList.add('visible'));
  }

  // Back to top
  const backToTop = document.getElementById('backToTop');
  if (backToTop) {
    window.addEventListener('scroll', () => {
      backToTop.classList.toggle('show', window.scrollY > 500);
    }, { passive: true });
    backToTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
  }
})();