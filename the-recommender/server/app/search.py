import re
import time
from threading import Lock

# ----------------------------------------------------------------------
# Powerful search helpers
# ----------------------------------------------------------------------
SEARCH_TITLE_EXACT = 1000
SEARCH_TITLE_PREFIX = 800
SEARCH_TITLE_SUBSTRING = 600
SEARCH_TITLE_TOKENS = 400
SEARCH_CHARACTER_EXACT = 400
SEARCH_CHARACTER_PREFIX = 300
SEARCH_CHARACTER_SUBSTRING = 200
SEARCH_CHARACTER_TOKENS = 120
SEARCH_PERSON_EXACT = 350
SEARCH_PERSON_PREFIX = 250
SEARCH_PERSON_SUBSTRING = 150
SEARCH_PERSON_TOKENS = 100
SEARCH_GENRE_EXACT = 250
SEARCH_GENRE_PARTIAL = 200
SEARCH_GENRE_TOKENS = 150
SEARCH_KEYWORD_EXACT = 250
SEARCH_KEYWORD_SUBSTRING = 220
SEARCH_KEYWORD_TOKENS = 160
SEARCH_OVERVIEW_SUBSTRING = 90

# How long to cache the full-table dataset (titles/genres/keywords/people).
_DATA_TTL_SECONDS = 60.0
_search_cache = None
_search_cache_ts = 0.0
_search_cache_lock = Lock()


def _load_search_data(cursor):
    """Load titles, genres, keywords and people/characters for search scoring.

    Building this means full-table scans, so the result is cached briefly. It is
    read-only after build, so sharing it across requests/threads is safe.
    """
    global _search_cache, _search_cache_ts
    now = time.time()
    with _search_cache_lock:
        if _search_cache is not None and now - _search_cache_ts < _DATA_TTL_SECONDS:
            return _search_cache

    cursor.execute("""
        SELECT id, media_type, title, poster_path, vote_average, release_date, overview
        FROM titles
    """)
    titles = cursor.fetchall()

    cursor.execute(
        "SELECT tg.title_id, g.name FROM title_genres tg JOIN genres g ON g.id = tg.genre_id"
    )
    genres = {}
    for r in cursor.fetchall():
        genres.setdefault(r['title_id'], set()).add(r['name'])

    cursor.execute(
        "SELECT tk.title_id, k.name FROM title_keywords tk JOIN keywords k ON k.id = tk.keyword_id"
    )
    keywords = {}
    for r in cursor.fetchall():
        keywords.setdefault(r['title_id'], set()).add(r['name'])

    cursor.execute("""
        SELECT tp.title_id, p.name, tp.character
        FROM title_people tp
        JOIN people p ON p.id = tp.person_id
        WHERE tp.role IN ('actor', 'director')
    """)
    people = {}
    for r in cursor.fetchall():
        entry = people.setdefault(r['title_id'], {'names': set(), 'characters': set()})
        entry['names'].add(r['name'])
        if r['character']:
            entry['characters'].add(r['character'])

    cache = (titles, genres, keywords, people)
    with _search_cache_lock:
        _search_cache = cache
        _search_cache_ts = time.time()
    return cache


def _search_score(t, genres, keywords, people, q, q_words):
    """Relevance score for one title against a query (higher = better match)."""
    score = 0.0

    title = (t.get('title') or '').lower()
    if title == q:
        score += SEARCH_TITLE_EXACT
    elif title.startswith(q):
        score += SEARCH_TITLE_PREFIX
    elif q in title:
        score += SEARCH_TITLE_SUBSTRING
    elif q_words and all(w in title for w in q_words):
        score += SEARCH_TITLE_TOKENS

    p = people.get(t['id'])
    if p:
        best_person = 0
        for name in p['names']:
            nl = name.lower()
            if nl == q:
                best_person = max(best_person, SEARCH_PERSON_EXACT)
            elif nl.startswith(q):
                best_person = max(best_person, SEARCH_PERSON_PREFIX)
            elif q in nl:
                best_person = max(best_person, SEARCH_PERSON_SUBSTRING)
            elif q_words and all(w in nl for w in q_words):
                best_person = max(best_person, SEARCH_PERSON_TOKENS)
        score += best_person

        best_char = 0
        for ch in p['characters']:
            cl = ch.lower()
            if cl == q:
                best_char = max(best_char, SEARCH_CHARACTER_EXACT)
            elif cl.startswith(q):
                best_char = max(best_char, SEARCH_CHARACTER_PREFIX)
            elif q in cl:
                best_char = max(best_char, SEARCH_CHARACTER_SUBSTRING)
            elif q_words and all(w in cl for w in q_words):
                best_char = max(best_char, SEARCH_CHARACTER_TOKENS)
        score += best_char

    gs = genres.get(t['id'], set())
    if any(g.lower() == q for g in gs):
        score += SEARCH_GENRE_EXACT
    elif any(g.lower().startswith(q) for g in gs):
        score += SEARCH_GENRE_PARTIAL
    elif any(q in g.lower() for g in gs):
        score += SEARCH_GENRE_PARTIAL
    elif q_words and all(w in ' '.join(gs).lower() for w in q_words):
        score += SEARCH_GENRE_TOKENS

    ks = keywords.get(t['id'], set())
    if any(k.lower() == q for k in ks):
        score += SEARCH_KEYWORD_EXACT
    elif any(q in k.lower() for k in ks):
        score += SEARCH_KEYWORD_SUBSTRING
    elif q_words and all(w in ' '.join(ks).lower() for w in q_words):
        score += SEARCH_KEYWORD_TOKENS

    overview = (t.get('overview') or '').lower()
    if q in overview:
        score += SEARCH_OVERVIEW_SUBSTRING

    if score > 0:
        score += (float(t.get('vote_average') or 0)) * 0.1
    return score


def search_titles(conn, query, limit=12, offset=0):
    """Powerful search across titles, partial names, genres, keywords, people and
    character names. Returns (total_matches, paginated_title_rows)."""
    q = query.strip().lower()
    if not q:
        return 0, []
    q_words = re.findall(r"[a-z0-9']+", q)

    cursor = conn.cursor(dictionary=True)
    try:
        titles, genres, keywords, people = _load_search_data(cursor)

        scored = []
        for t in titles:
            s = _search_score(t, genres, keywords, people, q, q_words)
            if s > 0:
                scored.append((s, t))

        scored.sort(key=lambda x: (-x[0], -(x[1].get('vote_average') or 0), x[1].get('title') or ''))
        total = len(scored)
        results = [t for _, t in scored[offset:offset + limit]]
        return total, results
    finally:
        cursor.close()