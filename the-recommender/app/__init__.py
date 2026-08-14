from flask import Flask, render_template, request, abort
import os
import re
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

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
    'hentai', 'ecchi', 'xxx', 'blue film', 'fetish film', 'dominatrix', 'bdsm',
    'prostitute', 'prostitution', 'sex work', 'sex worker', 'orgy', 'masturbation',
}

HARD_NO_KEYWORDS['adult'] = ADULT_KEYWORDS

# Word-boundary regex for scanning free-text overviews (short/ambiguous terms are
# matched as whole words so e.g. "xXx" an action film isn't flagged by "xxx").
ADULT_OVERVIEW_RE = re.compile(
    r'\b(xxx|orgy|bdsm|ecchi|hentai|nude|nudity|porn|softcore|soft-core|erotic|erotica|'
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

    if runtime != 'any':
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


def _load_search_data(cursor):
    """Load titles, genres, keywords and people/characters for search scoring."""
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

    return titles, genres, keywords, people


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


def personalization_query(conn, answers):
    """Run the Q&A filter and return (favorites, ranked_results) (None if no answers)."""
    media_type = answers.get('media_type') or ''
    moods = answers.get('moods') or []
    hard_no = answers.get('hard_no') or []
    runtime = answers.get('runtime') or 'any'

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
        return favorites, results
    finally:
        cursor.close()

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True

    # Database connection pool
    db_config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'database': os.getenv('MYSQL_DATABASE', 'movie_recommender'),
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci',
        'auth_plugin': 'mysql_native_password',
    }
    cnx_pool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **db_config)

    def get_db():
        return cnx_pool.get_connection()

    PER_PAGE = 12

    @app.route('/', methods=['GET', 'POST'])
    def index():
        page = request.args.get('page', 1, type=int)
        query = request.args.get('q', '').strip()
        offset = (page - 1) * PER_PAGE

        conn = get_db()
        cursor = conn.cursor(dictionary=True)

        # ---- Quiz mode (default landing / after submitting answers) ----
        quiz = True
        results = None
        favorites = []

        try:
            favorites = _fetch_favorites(cursor)
        except Exception:
            favorites = []

        if request.method == 'POST':
            answers = {
                'media_type': request.form.get('media_type', ''),
                'moods': request.form.getlist('mood'),
                'hard_no': request.form.getlist('hard_no'),
                'runtime': request.form.get('runtime', 'any'),
                'favorite_id': request.form.get('favorite_id', ''),
                'favorite_text': request.form.get('favorite_text', ''),
            }
            try:
                out = personalization_query(conn, answers)
                if out is not None:
                    favorites, results = out
            except Exception:
                results = []
            return render_template('index.html',
                                   quiz=quiz, results=results, favorites=favorites,
                                   titles=[], page=1, total_pages=0, total=0,
                                   query='', PER_PAGE=PER_PAGE,
                                   MOOD_LABELS=MOOD_LABELS, MOOD_ICONS=MOOD_ICONS,
                                   RUNTIME_OPTIONS=RUNTIME_OPTIONS, HARD_NO=HARD_NO)

        # Skip quiz / search -> plain browse all
        if request.args.get('skip') == '1' or query:
            quiz = False

        if quiz:
            titles, total = [], 0
        else:
            try:
                if query:
                    total, titles = search_titles(conn, query, PER_PAGE, offset)
                else:
                    sql = """
                        SELECT id, media_type, title, poster_path, vote_average, release_date
                        FROM titles
                        ORDER BY release_date DESC
                        LIMIT %s OFFSET %s
                    """
                    cursor.execute(sql, (PER_PAGE, offset))
                    titles = cursor.fetchall()
                    cursor.execute("SELECT COUNT(*) as cnt FROM titles")
                    total = cursor.fetchone()['cnt']
            finally:
                pass

        cursor.close()
        conn.close()

        total_pages = (total + PER_PAGE - 1) // PER_PAGE
        return render_template('index.html',
                               quiz=quiz, results=results, favorites=favorites,
                               titles=titles,
                               page=page,
                               total_pages=total_pages,
                               total=total,
                               query=query,
                               PER_PAGE=PER_PAGE,
                               MOOD_LABELS=MOOD_LABELS, MOOD_ICONS=MOOD_ICONS,
                               RUNTIME_OPTIONS=RUNTIME_OPTIONS, HARD_NO=HARD_NO)

    @app.route('/personalize', methods=['GET', 'POST'])
    def personalize():
        conn = get_db()
        favorites = []
        results = None
        try:
            cursor = conn.cursor(dictionary=True)
            favorites = _fetch_favorites(cursor)
            cursor.close()

            if request.method == 'POST':
                answers = {
                    'media_type': request.form.get('media_type', ''),
                    'moods': request.form.getlist('mood'),
                    'hard_no': request.form.getlist('hard_no'),
                    'runtime': request.form.get('runtime', 'any'),
                    'favorite_id': request.form.get('favorite_id', ''),
                    'favorite_text': request.form.get('favorite_text', ''),
                }
                out = personalization_query(conn, answers)
                if out is not None:
                    favorites, results = out
        finally:
            conn.close()

        return render_template('personalize.html',
                               favorites=favorites,
                               results=results,
                               MOOD_LABELS=MOOD_LABELS,
                               MOOD_ICONS=MOOD_ICONS,
                               RUNTIME_OPTIONS=RUNTIME_OPTIONS,
                               HARD_NO=HARD_NO,
                               quiz=True)

    @app.route('/title/<int:title_id>')
    def title_detail(title_id):
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT id, tmdb_id, media_type, title, overview, release_date,
                       poster_path, backdrop_path, vote_average, vote_count, popularity, original_language
                FROM titles WHERE id = %s
            """, (title_id,))
            title = cursor.fetchone()
            if not title:
                abort(404)

            # similar titles
            cursor.execute("""
                SELECT t.id, t.title, t.poster_path, t.vote_average, t.release_date, s.similarity_score, s.rank
                FROM similar_titles s
                JOIN titles t ON t.id = s.target_title_id
                WHERE s.source_title_id = %s
                ORDER BY s.rank
                LIMIT 12
            """, (title_id,))
            similar = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        return render_template('detail.html', title=title, similar=similar)

    @app.template_filter('tmdb_image')
    def tmdb_image(path, size='w342'):
        if not path:
            return ''
        if not path.startswith('/'):
            path = '/' + path
        return f'https://image.tmdb.org/t/p/{size}{path}'

    return app