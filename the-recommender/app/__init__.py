from flask import Flask, render_template, request, abort
import os
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
    'adult': {'pornography', 'erotic', 'nudity', 'adult film', 'sex scene'},
}


def _score_title(t, genres, keywords, moods, seed_id, seed_genres, seed_keywords, runtime):
    """Return a personalization score for one title dict."""
    gs = genres.get(t['id'], set())
    ks = keywords.get(t['id'], set())
    score = float(t['vote_average'] or 0) * 1.0

    if moods:
        for m in moods:
            score += 14 * len(gs & MOOD_GENRES.get(m, set()))
        # small tiebreak for having any of the mood's genres at all
        if any(gs & MOOD_GENRES.get(m, set()) for m in moods):
            score += 2

    if seed_id:
        shared_g = len(gs & seed_genres)
        shared_k = len(ks & seed_keywords)
        score += 10 * shared_g
        score += 4 * min(shared_k, 6)

    if runtime and t['runtime']:
        _, test = RUNTIME_OPTIONS[runtime]
        if test(t['runtime']):
            score += 4
        else:
            score -= 6
    elif runtime and not t['runtime']:
        score -= 2  # unknown runtime -> gently deprioritise when a preference exists

    return score


def personalization_query(conn, answers):
    """Run the Q&A filter and return a ranked list of title dicts (empty if no answers)."""
    media_type = answers.get('media_type') or ''
    moods = answers.get('moods') or []
    hard_no = answers.get('hard_no') or []
    runtime = answers.get('runtime') or 'any'
    fav_id = answers.get('favorite_id')
    fav_text = (answers.get('favorite_text') or '').strip()

    if not media_type and not moods and not hard_no and runtime == 'any' and not fav_id and not fav_text:
        return None

    cursor = conn.cursor(dictionary=True)
    try:
        # random shortlist for the "recent favorite" picker
        cursor.execute("""
            SELECT id, media_type, title, poster_path, vote_average, release_date
            FROM titles ORDER BY RAND() LIMIT 12
        """)
        favorites = cursor.fetchall()

        cursor.execute("""
            SELECT t.id, t.media_type, t.title, t.poster_path, t.vote_average, t.release_date,
                   t.runtime, t.original_language, t.overview
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

        genres, keywords = {}, {}
        for r in genre_rows:
            genres.setdefault(r['title_id'], set()).add(r['name'])
        for r in kw_rows:
            keywords.setdefault(r['title_id'], set()).add(r['name'])

        # resolve favourite seed
        seed_id = None
        if fav_id:
            try:
                seed_id = int(fav_id)
            except (TypeError, ValueError):
                seed_id = None
        if not seed_id and fav_text:
            cursor.execute(
                "SELECT id FROM titles WHERE LOWER(title) LIKE %s ORDER BY CHAR_LENGTH(title) LIMIT 1",
                (f'%{fav_text.lower()}%',),
            )
            row = cursor.fetchone()
            if row:
                seed_id = row['id']

        seed_genres = genres.get(seed_id, set()) if seed_id else set()
        seed_keywords = keywords.get(seed_id, set()) if seed_id else set()

        # apply filters
        kept = []
        for t in titles:
            if media_type in ('movie', 'tv') and t['media_type'] != media_type:
                continue

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

            score = _score_title(t, genres, keywords, moods, seed_id, seed_genres, seed_keywords, runtime)
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
            cursor.execute("""
                SELECT id, media_type, title, poster_path, vote_average, release_date
                FROM titles ORDER BY RAND() LIMIT 12
            """)
            favorites = cursor.fetchall()
        except Exception:
            pass

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
                    sql = """
                        SELECT id, media_type, title, poster_path, vote_average, release_date
                        FROM titles
                        WHERE title LIKE %s
                        ORDER BY title
                        LIMIT %s OFFSET %s
                    """
                    like = f"%{query}%"
                    cursor.execute(sql, (like, PER_PAGE, offset))
                    titles = cursor.fetchall()
                    # count total for pagination
                    cursor.execute("SELECT COUNT(*) as cnt FROM titles WHERE title LIKE %s", (like,))
                    total = cursor.fetchone()['cnt']
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
            cursor.execute("""
                SELECT id, media_type, title, poster_path, vote_average, release_date
                FROM titles ORDER BY RAND() LIMIT 12
            """)
            favorites = cursor.fetchall()
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