#!/usr/bin/env python3
"""
Backfill the `adult`, `certification` (movies) and `content_rating` (TV) columns
for titles that were ingested before the content-flag migration.

Usage:
    python scripts/backfill_content_flags.py            # every title
    python scripts/backfill_content_flags.py --limit 50 # first 50 titles
"""

import argparse
import os
import sys
import time
import logging
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest import get_conn, tmdb_get  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("backfill")


def fetch_flags(media_type, tmdb_id, details):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only process the first N titles")
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, tmdb_id, media_type, title FROM titles ORDER BY id")
        rows = cur.fetchall()
        if args.limit:
            rows = rows[: args.limit]

        log.info("Backfilling content flags for %d titles…", len(rows))
        done = 0
        for r in rows:
            tid = r["tmdb_id"]
            details = tmdb_get(f"/{r['media_type']}/{tid}", params={"language": "en-US"})
            if details is None:
                log.warning("Skipping %s %s: no detail", r["media_type"], tid)
                continue
            adult, cert, cr = fetch_flags(r["media_type"], tid, details)
            cur.execute(
                """
                UPDATE `titles`
                SET `adult` = %s, `certification` = %s, `content_rating` = %s
                WHERE `id` = %s
                """,
                (bool(adult), cert, cr, r["id"]),
            )
            done += 1
            if done % 25 == 0:
                conn.commit()
                log.info("Progress: %d/%d", done, len(rows))
            time.sleep(0.2)  # be nice to the API

        conn.commit()
        log.info("Backfill complete (%d titles updated).", done)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
