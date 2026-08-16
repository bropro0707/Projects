import re
import time
from threading import Lock

from .search import search_titles

# ----------------------------------------------------------------------
# Personalization helpers
# ----------------------------------------------------------------------
MOOD_GENRES = {
    'laugh': {'Comedy', 'Animation', 'Family'},
    'cry': {'Drama', 'Romance'},
    'tense': {'Thriller', 'Crime', 'Mystery', 'Horror'},
    'intellectual': {'Documentary', 'History', 'Science Fiction', 'Mystery', 'War & Politics'},
    'comforted': {'Family', 'Animation', 'Romance', 'Fantasy', 'Comedy'},
    'devastated': {'Drama', 'Romance', 'War'},
    'escape': {'Action', 'Adventure', 'Fantasy', 'Science Fiction', 'Animation', 'Comedy'},
}

MOOD_LABELS = {
    'laugh': 'Make me laugh',
    'cry': 'Make me cry',
    'tense': 'Keep me on edge',
    'intellectual': 'Make me think',
    'comforted': 'Comfort me',
    'devastated': 'Shatter me',
    'escape': 'Just let me escape',
}

MOOD_ICONS = {
    'laugh': 'bi-emoji-laughing',
    'cry': 'bi-emoji-tear',
    'tense': 'bi-lightning-charge',
    'intellectual': 'bi-brain',
    'comforted': 'bi-heart',
    'devastated': 'bi-emoji-frown',
    'escape': 'bi-rocket-takeoff',
}

RUNTIME_OPTIONS = {
    'short': ('< 90 min', lambda r: r < 90),
    'standard': ('90–120 min', lambda r: 90 <= r <= 120),
    'long': ('120–150 min', lambda r: 120 < r <= 150),
    'epic': ('150+ min', lambda r: r > 150),
}

HARD_NO = {
    'subtitles': {
        'label': 'Subtitles',
        'desc': 'No foreign-language films',
    },
    'horror': {
        'label': 'Horror',
        'desc': 'No horror movies',
    },
    'nonlinear': {
        'label': 'Non-linear narratives',
        'desc': 'No flashbacks or time jumps',
    },
    'long_runtime': {
        'label': 'Excessive runtime',
        'desc': 'Nothing over 3 hours',
    },
    'triggers': {
        'label': 'Specific triggers',
        'desc': 'No self-harm, abuse or violence',
    },
    'sexual_violence': {
        'label': 'Sexual violence',
        'desc': 'No sexual assault themes',
    },
    'animal_harm': {
        'label': 'Animal harm',
        'desc': 'No animal cruelty',
    },
    'gore': {
        'label': 'Extreme gore',
        'desc': 'No gore or torture',
    },
    'adult': {
        'label': 'Adult content',
        'desc': 'No explicit/nudity',
    },
}

HARD_NO_KEYWORDS = {
    'nonlinear': {'nonlinear', 'time jump', 'flashback', 'time travel', 'nonlinear timeline', 'non-chronological'},
    'triggers': {'suicide', 'self-harm', 'self harm', 'domestic abuse', 'child abuse', 'violence', 'assault'},
    'sexual_violence': {'rape', 'sexual assault', 'sexual violence', 'molestation'},
    'animal_harm': {'animal cruelty', 'animal abuse', 'animal death', 'animal harm'},
    'gore': {'gore', 'torture', 'extreme violence', 'mutilation'},
}

# Certifications / ratings that unambiguously flag a title as 18+ / explicit.
# (TV-MA is deliberately NOT included: mainstream prestige shows like Breaking Bad
# are TV-MA but are not "adult content". Explicit titles are still caught via the
# keyword / overview signals below.)
ADULT_CERTIFICATIONS = {'NC-17', 'X', 'AO'}
ADULT_TV_RATINGS = {'TV-M18'}

# Explicit-content terms. Matched against a title's keywords AND its overview,
# so titles without certification data (e.g. foreign pink films, ecchi anime)
# are still filtered out.
ADULT_KEYWORDS = {
    'porn', 'pornography', 'pornographic', 'porn movie', 'porn star', 'hardcore',
    'softcore', 'soft-core', 'erotic', 'erotica', 'erotic movie', 'erotic thriller',
    'sexploitation', 'pink film', 'pink eiga', 'adult film', 'adult movie',
    'nude', 'nudity', 'nudist', 'nude scene', 'full frontal', 'male nudity', 'female nudity',
    'sex scene', 'sex tape', 'sexual content', 'explicit sex', 'sexploitation film',
    'hentai', 'ecchi', 'blue film', 'fetish film', 'dominatrix', 'bdsm',
    'prostitute', 'prostitution', 'sex work', 'sex worker', 'orgy', 'masturbation',
}

HARD_NO_KEYWORDS['adult'] = ADULT_KEYWORDS

# Word-boundary regex for scanning free-text overviews. Note: `xxx` is deliberately
# NOT matched here (or in ADULT_KEYWORDS above) — the "xXx" action franchise is a
# legitimately PG-13 series whose title/overview contain the token, and a
# case-insensitive `\bxxx\b` cannot distinguish it from adult content. Genuinely
# explicit titles are still caught by the `adult` flag, NC-17/X/AO certifications,
# TV-M18 ratings, and the many unambiguous terms below.
ADULT_OVERVIEW_RE = re.compile(
    r'\b(orgy|bdsm|ecchi|hentai|nude|nudity|porn|softcore|soft-core|erotic|erotica|'
    r'sexploitation|pink film|pink eiga|adult film|adult movie|sex scene|sex tape|'
    r'sexual content|explicit sex|fetish film|dominatrix|prostitute|prostitution|'
    r'sex work|sex worker|masturbation|full frontal)\b',
    re.IGNORECASE,
)


def _is_adult_title(t, keywords):
    """Return True if a title should be treated as explicit / 18+ content."""
    if t.get('adult'):
        return True
    cert = (t.get('certification') or '').strip().upper()
    if cert in ADULT_CERTIFICATIONS:
        return True
    rating = (t.get('content_rating') or '').strip().upper()
    if rating in ADULT_TV_RATINGS:
        return True
    # keywords: TMDB tags for actual explicit content
    for k in keywords.get(t['id'], set()):
        kl = k.lower()
        for term in ADULT_KEYWORDS:
            if term in kl:
                return True
    # overview: word-boundary scan
    if ADULT_OVERVIEW_RE.search(t.get('overview') or ''):
        return True
    return False


def _score_title(t, genres, keywords, people, moods, seeds,
                 seed_genres, seed_keywords, seed_cast, seed_directors, similar_map, runtime):
    """Return a personalization score for one title dict.

    Signals, roughly in order of influence:
      - mood genre fit
      - precomputed cosine similarity to each favorite seed (similar_titles)
      - genre / keyword overlap with each seed
      - shared cast members and shared director with each seed
      - rating quality (vote_average) and runtime preference
    """
    gs = genres.get(t['id'], set())
    ks = keywords.get(t['id'], set())
    score = float(t['vote_average'] or 0)

    if moods:
        for m in moods:
            score += 14 * len(gs & MOOD_GENRES.get(m, set()))
        # small tiebreak for having any of the mood's genres at all
        if any(gs & MOOD_GENRES.get(m, set()) for m in moods):
            score += 2

    for sid in seeds:
        sim = similar_map.get(sid, {}).get(t['id'])
        if sim is not None:
            score += 22 * sim  # strong "soulmate" signal from precomputed similarity

        shared_g = len(gs & seed_genres.get(sid, set()))
        shared_k = len(ks & seed_keywords.get(sid, set()))
        score += 9 * shared_g
        score += 3.5 * min(shared_k, 6)

        # cast / director affinity with the seed
        p = people.get(t['id'])
        if p:
            shared_cast = len(p['actors'] & seed_cast.get(sid, set()))
            score += 5 * min(shared_cast, 3)
            seed_director = seed_directors.get(sid)
            if seed_director and p['director'] and p['director'] == seed_director:
                score += 7

    if runtime != 'any' and runtime in RUNTIME_OPTIONS:
        if t['runtime']:
            _, test = RUNTIME_OPTIONS[runtime]
            if test(t['runtime']):
                score += 4
            else:
                score -= 6
        else:
            score -= 2  # unknown runtime -> gently deprioritise when a preference exists

    return score


def _fetch_favorites(cursor, limit=24):
    """Curated set of recognizable titles for the Q3 picker (multi-select)."""
    cursor.execute("""
        SELECT id, media_type, title, poster_path, vote_average, release_date
        FROM titles
        WHERE vote_average >= 6.5
        ORDER BY RAND()
        LIMIT %s
    """, (limit,))
    return cursor.fetchall()


# How long to cache the full-table catalog (titles + genre/keyword/people maps).
_CATALOG_TTL_SECONDS = 60.0
_catalog_cache = None
_catalog_cache_ts = 0.0
_catalog_cache_lock = Lock()


def _load_catalog(cursor):
    """Load titles plus genre/keyword/people maps for personalization.

    Building this means full-table scans, so the result is cached briefly. It is
    read-only after build, so sharing it across requests/threads is safe.
    """
    global _catalog_cache, _catalog_cache_ts
    now = time.time()
    with _catalog_cache_lock:
        if _catalog_cache is not None and now - _catalog_cache_ts < _CATALOG_TTL_SECONDS:
            return _catalog_cache

    cursor.execute("""
        SELECT t.id, t.media_type, t.title, t.poster_path, t.vote_average, t.release_date,
               t.runtime, t.original_language, t.overview, t.adult, t.certification, t.content_rating
        FROM titles t
    """)
    titles = cursor.fetchall()

    cursor.execute(
        "SELECT tg.title_id, g.name FROM title_genres tg JOIN genres g ON g.id = tg.genre_id"
    )
    genre_rows = cursor.fetchall()
    cursor.execute(
        "SELECT tk.title_id, k.name FROM title_keywords tk JOIN keywords k ON k.id = tk.keyword_id"
    )
    kw_rows = cursor.fetchall()
    cursor.execute("""
        SELECT tp.title_id, p.name, tp.role
        FROM title_people tp
        JOIN people p ON p.id = tp.person_id
        WHERE tp.role IN ('actor', 'director')
    """)
    people_rows = cursor.fetchall()

    genres, keywords = {}, {}
    for r in genre_rows:
        genres.setdefault(r['title_id'], set()).add(r['name'])
    for r in kw_rows:
        keywords.setdefault(r['title_id'], set()).add(r['name'])

    people = {}
    for r in people_rows:
        entry = people.setdefault(r['title_id'], {'actors': set(), 'director': None})
        if r['role'] == 'actor':
            entry['actors'].add(r['name'])
        elif r['role'] == 'director' and entry['director'] is None:
            entry['director'] = r['name']

    catalog = (titles, genres, keywords, people)
    with _catalog_cache_lock:
        _catalog_cache = catalog
        _catalog_cache_ts = time.time()
    return catalog


def personalization_query(conn, answers):
    """Run the Q&A filter and return (favorites, ranked_results, matched_count)
    (None if no answers were given at all)."""
    media_type = answers.get('media_type') or ''
    moods = answers.get('moods') or []
    hard_no = answers.get('hard_no') or []
    runtime = answers.get('runtime') or 'any'
    if runtime != 'any' and runtime not in RUNTIME_OPTIONS:
        runtime = 'any'  # unknown value -> behave as "no preference"

    # --- resolve favorite seeds (multiple posters + one typed title) ---
    raw_ids = answers.get('favorite_ids') or answers.get('favorite_id') or ''
    if isinstance(raw_ids, str):
        raw_ids = [x for x in raw_ids.replace(',', ' ').split() if x.strip().isdigit()]
    elif isinstance(raw_ids, (list, tuple)):
        raw_ids = [str(x) for x in raw_ids if str(x).strip().isdigit()]
    fav_text = (answers.get('favorite_text') or '').strip()

    if (not media_type and not moods and not hard_no and runtime == 'any'
            and not raw_ids and not fav_text):
        return None

    cursor = conn.cursor(dictionary=True)
    try:
        favorites = _fetch_favorites(cursor)

        titles, genres, keywords, people = _load_catalog(cursor)

        # resolve the favorite seed ids
        seed_ids = []
        for raw in raw_ids[:6]:
            try:
                sid = int(raw)
            except (TypeError, ValueError):
                continue
            if any(x['id'] == sid for x in titles) and sid not in seed_ids:
                seed_ids.append(sid)

        if fav_text:
            _, matches = search_titles(conn, fav_text, limit=3)
            for m in matches:
                if m['id'] not in seed_ids:
                    seed_ids.append(m['id'])

        # per-seed feature profiles for scoring
        seed_genres = {sid: genres.get(sid, set()) for sid in seed_ids}
        seed_keywords = {sid: keywords.get(sid, set()) for sid in seed_ids}
        seed_cast = {sid: people.get(sid, {}).get('actors', set()) for sid in seed_ids}
        seed_directors = {sid: people.get(sid, {}).get('director') for sid in seed_ids}

        # precomputed cosine neighbours of each seed (the "soulmates" signal)
        similar_map = {}
        if seed_ids:
            placeholders = ','.join(['%s'] * len(seed_ids))
            cursor.execute(
                f"""
                SELECT source_title_id, target_title_id, similarity_score
                FROM similar_titles WHERE source_title_id IN ({placeholders})
                """,
                tuple(seed_ids),
            )
            for r in cursor.fetchall():
                similar_map.setdefault(r['source_title_id'], {})[r['target_title_id']] = float(r['similarity_score'])

        # apply filters + rank
        kept = []
        for t in titles:
            if media_type in ('movie', 'tv') and t['media_type'] != media_type:
                continue
            if t['id'] in seed_ids:
                continue  # never recommend the favorites themselves

            gs = genres.get(t['id'], set())
            ks = keywords.get(t['id'], set())
            lang = (t['original_language'] or '').lower()

            exclude = False
            for flag in hard_no:
                if flag == 'subtitles' and lang and lang != 'en':
                    exclude = True
                elif flag == 'horror' and 'Horror' in gs:
                    exclude = True
                elif flag == 'long_runtime' and t['runtime'] and t['runtime'] > 180:
                    exclude = True
                elif flag == 'adult' and _is_adult_title(t, keywords):
                    exclude = True
                else:
                    banned = HARD_NO_KEYWORDS.get(flag, set())
                    if banned and any(b in k.lower() for k in ks for b in banned):
                        exclude = True
                if exclude:
                    break
            if exclude:
                continue

            if runtime != 'any' and t['runtime']:
                _, test = RUNTIME_OPTIONS[runtime]
                if not test(t['runtime']):
                    continue

            score = _score_title(t, genres, keywords, people, moods, seed_ids,
                                 seed_genres, seed_keywords, seed_cast, seed_directors,
                                 similar_map, runtime)
            kept.append((score, t))

        kept.sort(key=lambda x: x[0], reverse=True)
        results = [t for _, t in kept][:24]
        return favorites, results, len(kept)
    finally:
        cursor.close()