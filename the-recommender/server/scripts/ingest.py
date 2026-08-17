#!/usr/bin/env python3
"""
Ingest TMDB data into MySQL.
- Loads TMDB_API_KEY from .env
- Stores genre lists
- Pulls top 200 popular movies and TV shows (10 pages each)
- For each title fetches details, keywords, credits (cast + director)
- Upserts into the schema defined in schema.sql
"""

import os
import sys
import time
import logging
from pathlib import Path

import requests
import mysql.connector
from mysql.connector import errorcode
from dotenv import load_dotenv

# ----------------------------------------------------------------------
# Configuration & Logging
# ----------------------------------------------------------------------
load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    sys.exit("TMDB_API_KEY not set in .env")

TMDB_BASE = "https://api.themoviedb.org/3"
HEADERS = {"accept": "application/json"}
API_KEY_PARAM = {"api_key": TMDB_API_KEY}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

MYSQL_CFG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "charset": "utf8mb4",
    "autocommit": False,
}

# TiDB Cloud (and most managed MySQL hosts) require an encrypted connection.
# Set MYSQL_SSL=true in production; local dev against plain MySQL is untouched
# since this defaults to off. Mirrors server/app/db.py.
if os.getenv("MYSQL_SSL", "false").lower() == "true":
    import certifi

    MYSQL_CFG["ssl_ca"] = os.getenv("MYSQL_SSL_CA", certifi.where())
    MYSQL_CFG["ssl_verify_cert"] = True
else:
    MYSQL_CFG["auth_plugin"] = "mysql_native_password"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ingest")

print(f"Connecting to database: {MYSQL_CFG['database']}")

# ----------------------------------------------------------------------
# DB helpers
# ----------------------------------------------------------------------
def get_conn():
    return mysql.connector.connect(**MYSQL_CFG)


def upsert_genre(cursor, tmdb_id, name):
    sql = """
        INSERT INTO `genres` (`tmdb_id`, `name`)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE `name` = VALUES(`name`)
    """
    cursor.execute(sql, (tmdb_id, name))
    return cursor.lastrowid or _fetch_genre_id(cursor, tmdb_id)


def _fetch_genre_id(cursor, tmdb_id):
    cursor.execute("SELECT `id` FROM `genres` WHERE `tmdb_id` = %s", (tmdb_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def upsert_keyword(cursor, tmdb_id, name):
    sql = """
        INSERT INTO `keywords` (`tmdb_id`, `name`)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE `name` = VALUES(`name`)
    """
    cursor.execute(sql, (tmdb_id, name))
    return cursor.lastrowid or _fetch_keyword_id(cursor, tmdb_id)


def _fetch_keyword_id(cursor, tmdb_id):
    cursor.execute("SELECT `id` FROM `keywords` WHERE `tmdb_id` = %s", (tmdb_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def upsert_person(cursor, tmdb_id, name, profile_path=None, gender=None, popularity=None):
    sql = """
        INSERT INTO `people` (`tmdb_id`, `name`, `profile_path`, `gender`, `popularity`)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            `name` = VALUES(`name`),
            `profile_path` = VALUES(`profile_path`),
            `gender` = VALUES(`gender`),
            `popularity` = VALUES(`popularity`)
    """
    cursor.execute(sql, (tmdb_id, name, profile_path, gender, popularity))
    return cursor.lastrowid or _fetch_person_id(cursor, tmdb_id)


def _fetch_person_id(cursor, tmdb_id):
    cursor.execute("SELECT `id` FROM `people` WHERE `tmdb_id` = %s", (tmdb_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def upsert_title(cursor, tmdb_id, media_type, title, overview, release_date, poster_path, vote_average,
                 backdrop_path=None, runtime=None, vote_count=None, popularity=None, original_language=None,
                 adult=False, certification=None, content_rating=None):
    sql = """
        INSERT INTO `titles`
            (`tmdb_id`, `media_type`, `title`, `overview`, `release_date`,
             `poster_path`, `backdrop_path`, `vote_average`, `runtime`,
             `vote_count`, `popularity`, `original_language`,
             `adult`, `certification`, `content_rating`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            `title` = VALUES(`title`),
            `overview` = VALUES(`overview`),
            `release_date` = VALUES(`release_date`),
            `poster_path` = VALUES(`poster_path`),
            `backdrop_path` = VALUES(`backdrop_path`),
            `vote_average` = VALUES(`vote_average`),
            `runtime` = VALUES(`runtime`),
            `vote_count` = VALUES(`vote_count`),
            `popularity` = VALUES(`popularity`),
            `original_language` = VALUES(`original_language`),
            `adult` = VALUES(`adult`),
            `certification` = VALUES(`certification`),
            `content_rating` = VALUES(`content_rating`)
    """
    cursor.execute(sql, (tmdb_id, media_type, title, overview, release_date, poster_path, backdrop_path,
                         vote_average, runtime, vote_count, popularity, original_language,
                         bool(adult), certification, content_rating))
    return cursor.lastrowid or _fetch_title_id(cursor, tmdb_id, media_type)


def _fetch_title_id(cursor, tmdb_id, media_type):
    cursor.execute(
        "SELECT `id` FROM `titles` WHERE `tmdb_id` = %s AND `media_type` = %s",
        (tmdb_id, media_type),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def link_title_genre(cursor, title_id, genre_id):
    sql = """
        INSERT IGNORE INTO `title_genres` (`title_id`, `genre_id`) VALUES (%s, %s)
    """
    cursor.execute(sql, (title_id, genre_id))


def link_title_keyword(cursor, title_id, keyword_id):
    sql = """
        INSERT IGNORE INTO `title_keywords` (`title_id`, `keyword_id`) VALUES (%s, %s)
    """
    cursor.execute(sql, (title_id, keyword_id))


def link_title_person(cursor, title_id, person_id, role, character=None, order_idx=None):
    sql = """
        INSERT IGNORE INTO `title_people`
            (`title_id`, `person_id`, `role`, `character`, `order_idx`)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (title_id, person_id, role, character, order_idx))


# ----------------------------------------------------------------------
# TMDB request helpers
# ----------------------------------------------------------------------
def tmdb_get(path, params=None):
    url = f"{TMDB_BASE}{path}"
    if params is None:
        params = {}
    params.update(API_KEY_PARAM)
    for attempt in range(3):
        try:
            resp = SESSION.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt == 2:
                log.warning("TMDB request failed %s after 3 attempts: %s", path, exc)
                return None
            delay = 2 ** attempt
            log.debug("TMDB request failed %s (attempt %d/3), retrying in %ds: %s", path, attempt + 1, delay, exc)
            time.sleep(delay)
    return None


def fetch_genres(media_type):
    data = tmdb_get(f"/genre/{media_type}/list")
    if not data:
        return []
    return data.get("genres", [])


def fetch_popular(media_type, pages=10):
    results = []
    for page in range(1, pages + 1):
        data = tmdb_get(f"/{media_type}/popular", params={"page": page, "language": "en-US"})
        if not data:
            continue
        results.extend(data.get("results", []))
        log.info("Fetched page %d/%d for %s (%d items)", page, pages, media_type, len(data.get("results", [])))
        time.sleep(0.25)  # be nice to the API
    return results[:200]


def fetch_details(media_type, tmdb_id):
    return tmdb_get(f"/{media_type}/{tmdb_id}", params={"language": "en-US"})


def fetch_keywords(media_type, tmdb_id):
    data = tmdb_get(f"/{media_type}/{tmdb_id}/keywords")
    if not data:
        return []
    # movie returns {keywords: [...]}, tv returns {results: [...]}
    return data.get("keywords") or data.get("results") or []


def fetch_credits(media_type, tmdb_id):
    return tmdb_get(f"/{media_type}/{tmdb_id}/credits", params={"language": "en-US"})


def fetch_content_flags(media_type, tmdb_id, details):
    """Return (adult, certification, content_rating) for a title.

    - adult          : TMDB's `adult` flag
    - certification  : US theatrical certification for movies (release_dates)
    - content_rating : US content rating for TV shows (content_ratings)
    """
    adult = bool(details.get("adult"))
    certification = None
    content_rating = None
    if media_type == "movie":
        data = tmdb_get(f"/movie/{tmdb_id}/release_dates")
        if data:
            for entry in data.get("results", []):
                if entry.get("iso_3166_1") == "US":
                    for rd in entry.get("release_dates", []):
                        cert = (rd.get("certification") or "").strip()
                        if cert:
                            certification = cert
                            break
                    break
    else:
        data = tmdb_get(f"/tv/{tmdb_id}/content_ratings")
        if data:
            for entry in data.get("results", []):
                if entry.get("iso_3166_1") == "US":
                    rating = (entry.get("rating") or "").strip()
                    if rating:
                        content_rating = rating
                    break
    return adult, certification, content_rating


# ----------------------------------------------------------------------
# Main ingest flow
# ----------------------------------------------------------------------
def ingest_genres(cursor):
    log.info("Ingesting genres...")
    for media_type in ("movie", "tv"):
        for g in fetch_genres(media_type):
            upsert_genre(cursor, g["id"], g["name"])
    log.info("Genres done.")


def ingest_titles(media_type, items, conn, cursor):
    log.info("Processing %d %s titles", len(items), media_type)
    for idx, item in enumerate(items, 1):
        tmdb_id = item["id"]
        try:
            details = fetch_details(media_type, tmdb_id)
            if not details:
                continue

            title = details.get("title") or details.get("name")
            overview = details.get("overview")
            release_date = details.get("release_date") or details.get("first_air_date")
            if release_date == "":
                release_date = None
            poster_path = details.get("poster_path")
            vote_average = details.get("vote_average")
            backdrop_path = details.get("backdrop_path")
            # movies have a single `runtime`; tv exposes an episode runtime list
            if media_type == "movie":
                runtime = details.get("runtime")
            else:
                episode_runtimes = details.get("episode_run_time") or []
                runtime = round(sum(episode_runtimes) / len(episode_runtimes)) if episode_runtimes else None
            vote_count = details.get("vote_count")
            popularity = details.get("popularity")
            original_language = details.get("original_language")
            genre_ids = [g["id"] for g in details.get("genres", [])]

            adult, certification, content_rating = fetch_content_flags(media_type, tmdb_id, details)

            title_id = upsert_title(
                cursor,
                tmdb_id,
                media_type,
                title,
                overview,
                release_date,
                poster_path,
                vote_average,
                backdrop_path=backdrop_path,
                runtime=runtime,
                vote_count=vote_count,
                popularity=popularity,
                original_language=original_language,
                adult=adult,
                certification=certification,
                content_rating=content_rating,
            )
            if not title_id:
                log.warning("Could not upsert title %s %s", media_type, tmdb_id)
                continue

            # link genres
            for gid in genre_ids:
                genre_internal = _fetch_genre_id(cursor, gid)
                if genre_internal:
                    link_title_genre(cursor, title_id, genre_internal)

            # keywords
            for kw in fetch_keywords(media_type, tmdb_id):
                kid = upsert_keyword(cursor, kw["id"], kw["name"])
                if kid:
                    link_title_keyword(cursor, title_id, kid)

            # credits
            credits = fetch_credits(media_type, tmdb_id)
            if credits:
                # cast
                for cast_member in credits.get("cast", [])[:20]:  # limit to top 20 billed
                    pid = upsert_person(
                        cursor,
                        cast_member["id"],
                        cast_member["name"],
                        cast_member.get("profile_path"),
                        cast_member.get("gender"),
                        cast_member.get("popularity"),
                    )
                    if pid:
                        link_title_person(
                            cursor,
                            title_id,
                            pid,
                            "actor",
                            character=cast_member.get("character"),
                            order_idx=cast_member.get("order"),
                        )
                # crew – directors
                for crew_member in credits.get("crew", []):
                    if crew_member.get("job") == "Director":
                        pid = upsert_person(
                            cursor,
                            crew_member["id"],
                            crew_member["name"],
                            crew_member.get("profile_path"),
                            crew_member.get("gender"),
                            crew_member.get("popularity"),
                        )
                        if pid:
                            link_title_person(cursor, title_id, pid, "director")
            conn.commit()
            if idx % 20 == 0:
                log.info("Progress: %d/%d %s titles", idx, len(items), media_type)
        except Exception as exc:
            log.error("Failed title %s %s: %s", media_type, tmdb_id, exc)
            conn.rollback()
            continue


def main():
    conn = get_conn()
    cursor = conn.cursor()
    try:
        ingest_genres(cursor)
        conn.commit()

        movies = fetch_popular("movie", pages=10)
        tv_shows = fetch_popular("tv", pages=10)

        ingest_titles("movie", movies, conn, cursor)
        ingest_titles("tv", tv_shows, conn, cursor)

        log.info("Ingest completed.")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()