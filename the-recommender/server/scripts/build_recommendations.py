#!/usr/bin/env python3
"""
Build content‑based recommendations.

* Loads every title with its genres, keywords, top‑3 billed cast and director.
* Creates a weighted “feature soup” per title.
* TF‑IDF vectorises the soups, computes cosine similarity.
* Stores the top‑10 neighbours for each title in `similar_titles`.
* Prints a few sanity‑check rows.
"""

import os
import sys
import logging
from collections import defaultdict

import mysql.connector
from mysql.connector import errorcode
from dotenv import load_dotenv

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# ----------------------------------------------------------------------
# Config / logging
# ----------------------------------------------------------------------
load_dotenv()

MYSQL_CFG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "charset": "utf8mb4",
    "autocommit": False,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_rec")

TOP_N = 10                # neighbours per title
CAST_WEIGHT = 2           # repeat cast names this many times
DIRECTOR_WEIGHT = 3       # repeat director name this many times
MAX_CAST = 3              # only top‑billed actors


# ----------------------------------------------------------------------
# DB helpers
# ----------------------------------------------------------------------
def get_conn():
    return mysql.connector.connect(**MYSQL_CFG)


def fetch_titles(cursor):
    """Return list of (id, tmdb_id, media_type, title, overview)."""
    cursor.execute(
        """
        SELECT `id`, `tmdb_id`, `media_type`, `title`, `overview`
        FROM `titles`
        ORDER BY `id`
        """
    )
    return cursor.fetchall()


def fetch_genres(cursor):
    """Map title_id -> list of genre names."""
    cursor.execute(
        """
        SELECT tg.`title_id`, g.`name`
        FROM `title_genres` tg
        JOIN `genres` g ON g.`id` = tg.`genre_id`
        """
    )
    mapping = defaultdict(list)
    for title_id, name in cursor.fetchall():
        mapping[title_id].append(name)
    return mapping


def fetch_keywords(cursor):
    """Map title_id -> list of keyword names."""
    cursor.execute(
        """
        SELECT tk.`title_id`, k.`name`
        FROM `title_keywords` tk
        JOIN `keywords` k ON k.`id` = tk.`keyword_id`
        """
    )
    mapping = defaultdict(list)
    for title_id, name in cursor.fetchall():
        mapping[title_id].append(name)
    return mapping


def fetch_people_links(cursor):
    """
    Return two maps:
      - title_id -> list of (person_name, order_idx) for actors (role='actor')
      - title_id -> director name (role='director', first one)
    """
    cursor.execute(
        """
        SELECT tp.`title_id`, p.`name`, tp.`role`, tp.`order_idx`
        FROM `title_people` tp
        JOIN `people` p ON p.`id` = tp.`person_id`
        WHERE tp.`role` IN ('actor','director')
        ORDER BY tp.`title_id`, tp.`role`, tp.`order_idx`
        """
    )
    actors = defaultdict(list)
    directors = {}
    for title_id, name, role, order_idx in cursor.fetchall():
        if role == "actor":
            actors[title_id].append((name, order_idx or 0))
        elif role == "director" and title_id not in directors:
            directors[title_id] = name
    # keep only top‑billed cast
    for tid, lst in actors.items():
        lst.sort(key=lambda x: x[1])
        actors[tid] = [n for n, _ in lst[:MAX_CAST]]
    return actors, directors


# ----------------------------------------------------------------------
# Build feature soup
# ----------------------------------------------------------------------
def build_soups(titles, genres_map, keywords_map, actors_map, directors_map):
    """
    Returns (soups_list, id_list) where each soup is a single string.
    """
    soups = []
    ids = []
    for title_id, tmdb_id, media_type, title, overview in titles:
        parts = []

        # Genres (weight 1)
        parts.extend(genres_map.get(title_id, []))

        # Keywords (weight 1)
        parts.extend(keywords_map.get(title_id, []))

        # Top cast (weight CAST_WEIGHT)
        for name in actors_map.get(title_id, []):
            parts.extend([name] * CAST_WEIGHT)

        # Director (weight DIRECTOR_WEIGHT)
        director = directors_map.get(title_id)
        if director:
            parts.extend([director] * DIRECTOR_WEIGHT)

        # Overview (low weight – just once)
        if overview:
            parts.append(overview)

        soup = " ".join(parts)
        soups.append(soup)
        ids.append(title_id)

    return soups, ids


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    conn = get_conn()
    cur = conn.cursor()
    try:
        log.info("Loading data from MySQL …")
        titles = fetch_titles(cur)
        genres_map = fetch_genres(cur)
        keywords_map = fetch_keywords(cur)
        actors_map, directors_map = fetch_people_links(cur)

        log.info("Building feature soups for %d titles …", len(titles))
        soups, title_ids = build_soups(
            titles, genres_map, keywords_map, actors_map, directors_map
        )

        log.info("Vectorising with TF‑IDF …")
        vectorizer = TfidfVectorizer(
            stop_words="english",
            max_df=0.9,
            min_df=2,
            ngram_range=(1, 2),
        )
        tfidf = vectorizer.fit_transform(soups)

        log.info("Computing cosine similarity …")
        # linear_kernel is faster for dense/sparse dot‑product
        cosine = linear_kernel(tfidf, tfidf)

        log.info("Writing top‑%d neighbours per title …", TOP_N)
        cur.execute("TRUNCATE TABLE `similar_titles`")
        insert_sql = """
            INSERT INTO `similar_titles`
                (`source_title_id`, `target_title_id`, `similarity_score`, `rank`)
            VALUES (%s, %s, %s, %s)
        """
        batch = []
        for idx, src_id in enumerate(title_ids):
            # Get similarity scores for this row, exclude self
            sims = cosine[idx]
            # argsort descending
            top_idx = np.argpartition(sims, -(TOP_N + 1))[-(TOP_N + 1) :]
            top_idx = top_idx[np.argsort(-sims[top_idx])]
            rank = 0
            for tgt_idx in top_idx:
                if tgt_idx == idx:
                    continue
                rank += 1
                if rank > TOP_N:
                    break
                tgt_id = title_ids[tgt_idx]
                score = float(sims[tgt_idx])
                batch.append((src_id, tgt_id, score, rank))
                if len(batch) >= 1000:
                    cur.executemany(insert_sql, batch)
                    conn.commit()
                    batch.clear()
            if idx % 500 == 0:
                log.info("Processed %d / %d titles", idx, len(title_ids))

        if batch:
            cur.executemany(insert_sql, batch)
            conn.commit()

        log.info("Done. Printing sanity‑check samples …")
        # Show first 5 titles with their top 3 neighbours
        cur.execute(
            """
            SELECT t1.`title` AS src, t2.`title` AS tgt, st.`similarity_score`, st.`rank`
            FROM `similar_titles` st
            JOIN `titles` t1 ON t1.`id` = st.`source_title_id`
            JOIN `titles` t2 ON t2.`id` = st.`target_title_id`
            WHERE st.`rank` <= 3
            ORDER BY t1.`id`, st.`rank`
            LIMIT 15
            """
        )
        for src, tgt, score, rank in cur.fetchall():
            print(f"  {src}  ->  {tgt}  (score={score:.4f}, rank={rank})")

    except Exception as exc:
        log.exception("Build recommendations failed: %s", exc)
        conn.rollback()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()