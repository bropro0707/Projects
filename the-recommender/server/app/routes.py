from datetime import date, datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request, abort

from .db import get_db
from .search import search_titles
from .personalize import (
    personalization_query,
    _fetch_favorites,
    MOOD_LABELS,
    MOOD_ICONS,
    RUNTIME_OPTIONS,
    HARD_NO,
)

api_bp = Blueprint('api', __name__)

PER_PAGE = 12


def _serialize(row):
    """Convert a dict-row into JSON-safe primitives (dates, decimals)."""
    out = {}
    for k, v in row.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def _serialize_list(rows):
    return [_serialize(r) for r in rows]


@api_bp.route('/config')
def config():
    """Static quiz config (moods, runtime options, hard-no's) for the client."""
    return jsonify({
        'moods': {k: {'label': MOOD_LABELS[k], 'icon': MOOD_ICONS[k]} for k in MOOD_LABELS},
        'runtime_options': {k: label for k, (label, _) in RUNTIME_OPTIONS.items()},
        'hard_no': HARD_NO,
    })


@api_bp.route('/favorites')
def favorites():
    """Curated favorites for the quiz picker."""
    limit = request.args.get('limit', 24, type=int)
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        rows = _fetch_favorites(cursor, limit=limit)
    finally:
        cursor.close()
        conn.close()
    return jsonify({'favorites': _serialize_list(rows)})


@api_bp.route('/titles')
def index():
    """Browse all titles (paginated) or search with ?q=."""
    page = request.args.get('page', 1, type=int)
    query = request.args.get('q', '').strip()
    offset = (page - 1) * PER_PAGE

    conn = get_db()
    try:
        if query:
            total, titles = search_titles(conn, query, PER_PAGE, offset)
        else:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, media_type, title, poster_path, vote_average, release_date
                FROM titles
                ORDER BY release_date DESC
                LIMIT %s OFFSET %s
            """, (PER_PAGE, offset))
            titles = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) as cnt FROM titles")
            total = cursor.fetchone()['cnt']
            cursor.close()
    finally:
        conn.close()

    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    return jsonify({
        'titles': _serialize_list(titles),
        'total': total,
        'page': page,
        'total_pages': total_pages,
        'query': query,
        'per_page': PER_PAGE,
    })


@api_bp.route('/titles/<int:title_id>')
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

    return jsonify({'title': _serialize(title), 'similar': _serialize_list(similar)})


@api_bp.route('/personalize', methods=['POST'])
def personalize():
    """Run the Q&A filter and return favorites + ranked results."""
    data = request.get_json(silent=True) or {}
    answers = {
        'media_type': data.get('media_type', ''),
        'moods': data.get('moods') or [],
        'hard_no': data.get('hard_no') or [],
        'runtime': data.get('runtime', 'any') or 'any',
        'favorite_ids': data.get('favorite_ids') or data.get('favorite_id') or '',
        'favorite_text': data.get('favorite_text', '') or '',
    }

    conn = get_db()
    try:
        out = personalization_query(conn, answers)
    finally:
        conn.close()

    if out is None:
        return jsonify({'favorites': [], 'results': []})
    favorites, results = out
    return jsonify({
        'favorites': _serialize_list(favorites),
        'results': _serialize_list(results),
    })