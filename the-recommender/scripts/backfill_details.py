#!/usr/bin/env python3
"""
Backfill detail columns that were left NULL when titles were ingested before the
detail-column migration (`scripts/migrations/001_add_title_columns.sql`):

  - backdrop_path, runtime, vote_count, popularity, original_language
  - adult, certification (movies) and content_rating (TV)

It only touches the fields above; genres/keywords/people are left untouched.

Usage:
    python scripts/backfill_details.py            # every title
    python scripts/backfill_details.py --limit 50 # first 50 titles
    python scripts/backfill_details.py --sleep 0.25
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest import get_conn, tmdb_get, fetch_content_flags  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill_details")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only process the first N titles")
    parser.add_argument("--sleep", type=float, default=0.15, help="seconds between titles")
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT id, tmdb_id, media_type, title
            FROM titles
            WHERE backdrop_path IS NULL OR runtime IS NULL OR original_language IS NULL
            ORDER BY id
            """
        )
        rows = cur.fetchall()
        if args.limit:
            rows = rows[: args.limit]

        log.info("Backfilling details for %d titles…", len(rows))
        done = 0
        for r in rows:
            mt, tid = r["media_type"], r["tmdb_id"]
            try:
                details = tmdb_get(f"/{mt}/{tid}", params={"language": "en-US"})
                if details is None:
                    log.warning("Skipping %s %s: detail request failed", mt, tid)
                    continue

                title = details.get("title") or details.get("name")
                overview = details.get("overview")
                release_date = details.get("release_date") or details.get("first_air_date")
                poster_path = details.get("poster_path")
                backdrop_path = details.get("backdrop_path")
                vote_average = details.get("vote_average")
                vote_count = details.get("vote_count")
                popularity = details.get("popularity")
                original_language = details.get("original_language")

                # normalise empty strings to NULL so the DATE / VARCHAR columns stay happy
                release_date = release_date or None
                poster_path = poster_path or None
                backdrop_path = backdrop_path or None
                original_language = original_language or None

                if mt == "movie":
                    runtime = details.get("runtime")
                else:
                    episode_runtimes = details.get("episode_run_time") or []
                    runtime = round(sum(episode_runtimes) / len(episode_runtimes)) if episode_runtimes else None

                adult, certification, content_rating = fetch_content_flags(mt, tid, details)

                cur.execute(
                    """
                    UPDATE `titles`
                    SET `title` = COALESCE(%s, `title`),
                        `overview` = COALESCE(%s, `overview`),
                        `release_date` = COALESCE(%s, `release_date`),
                        `poster_path` = COALESCE(%s, `poster_path`),
                        `backdrop_path` = COALESCE(%s, `backdrop_path`),
                        `vote_average` = COALESCE(%s, `vote_average`),
                        `runtime` = COALESCE(%s, `runtime`),
                        `vote_count` = COALESCE(%s, `vote_count`),
                        `popularity` = COALESCE(%s, `popularity`),
                        `original_language` = COALESCE(%s, `original_language`),
                        `adult` = %s,
                        `certification` = COALESCE(%s, `certification`),
                        `content_rating` = COALESCE(%s, `content_rating`)
                    WHERE `id` = %s
                    """,
                    (title, overview, release_date, poster_path, backdrop_path,
                     vote_average, runtime, vote_count, popularity, original_language,
                     bool(adult), certification, content_rating, r["id"]),
                )
                done += 1
                conn.commit()  # commit each title so a later failure can't undo this work
                if done % 25 == 0:
                    log.info("Progress: %d/%d", done, len(rows))
            except Exception as exc:
                log.error("Failed %s %s (%s): %s", mt, tid, r["title"], exc)
            time.sleep(args.sleep)

        log.info("Backfill complete (%d titles updated).", done)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
