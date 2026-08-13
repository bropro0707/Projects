from flask import Flask, render_template, request, abort
import os
import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv()

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

    @app.route('/')
    def index():
        page = request.args.get('page', 1, type=int)
        query = request.args.get('q', '').strip()
        offset = (page - 1) * PER_PAGE

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
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
            cursor.close()
            conn.close()

        total_pages = (total + PER_PAGE - 1) // PER_PAGE
        return render_template('index.html',
                               titles=titles,
                               page=page,
                               total_pages=total_pages,
                               total=total,
                               query=query,
                               PER_PAGE=PER_PAGE)

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