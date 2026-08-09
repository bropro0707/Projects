-- MySQL schema for TMDB‑based content recommendation app
-- Engine: InnoDB, charset utf8mb4

CREATE DATABASE IF NOT EXISTS tmdb_recommender
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE tmdb_recommender;

-- 1. Titles (movies & TV shows)
CREATE TABLE `titles` (
    `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `tmdb_id`       BIGINT UNSIGNED NOT NULL,
    `media_type`    ENUM('movie','tv') NOT NULL,
    `title`         VARCHAR(500) NOT NULL,
    `overview`      TEXT,
    `release_date`  DATE,
    `poster_path`   VARCHAR(500),
    `vote_average`  DECIMAL(3,1) DEFAULT NULL,
    `created_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_tmdb_media` (`tmdb_id`, `media_type`),
    INDEX `idx_media_type` (`media_type`),
    INDEX `idx_release_date` (`release_date`),
    INDEX `idx_vote_average` (`vote_average`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Genres
CREATE TABLE `genres` (
    `id`          SMALLINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `tmdb_id`     SMALLINT UNSIGNED NOT NULL,
    `name`        VARCHAR(100) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_tmdb_id` (`tmdb_id`),
    UNIQUE KEY `uk_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Title <-> Genre many‑to‑many
CREATE TABLE `title_genres` (
    `title_id`   BIGINT UNSIGNED NOT NULL,
    `genre_id`   SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (`title_id`, `genre_id`),
    CONSTRAINT `fk_tg_title` FOREIGN KEY (`title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_tg_genre` FOREIGN KEY (`genre_id`) REFERENCES `genres` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Keywords
CREATE TABLE `keywords` (
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `tmdb_id`     INT UNSIGNED NOT NULL,
    `name`        VARCHAR(200) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_tmdb_id` (`tmdb_id`),
    UNIQUE KEY `uk_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Title <-> Keyword many‑to‑many
CREATE TABLE `title_keywords` (
    `title_id`    BIGINT UNSIGNED NOT NULL,
    `keyword_id`  INT UNSIGNED NOT NULL,
    PRIMARY KEY (`title_id`, `keyword_id`),
    CONSTRAINT `fk_tk_title` FOREIGN KEY (`title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_tk_keyword` FOREIGN KEY (`keyword_id`) REFERENCES `keywords` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. People (actors, directors, etc.)
CREATE TABLE `people` (
    `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `tmdb_id`     BIGINT UNSIGNED NOT NULL,
    `name`        VARCHAR(300) NOT NULL,
    `profile_path` VARCHAR(500),
    `gender`      TINYINT UNSIGNED,          -- 0=unknown,1=female,2=male,3=non‑binary
    `popularity`  DECIMAL(10,3) DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_tmdb_id` (`tmdb_id`),
    INDEX `idx_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Title <-> Person many‑to‑many with role
CREATE TABLE `title_people` (
    `title_id`   BIGINT UNSIGNED NOT NULL,
    `person_id`  BIGINT UNSIGNED NOT NULL,
    `role`       ENUM('actor','director','writer','producer','other') NOT NULL,
    `character`  VARCHAR(300),               -- only for actors
    `order_idx`  SMALLINT UNSIGNED,          -- billing order for cast
    PRIMARY KEY (`title_id`, `person_id`, `role`),
    CONSTRAINT `fk_tp_title` FOREIGN KEY (`title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_tp_person` FOREIGN KEY (`person_id`) REFERENCES `people` (`id`) ON DELETE CASCADE,
    INDEX `idx_role` (`role`),
    INDEX `idx_order` (`order_idx`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Pre‑computed similar titles (top‑N per title)
CREATE TABLE `similar_titles` (
    `source_title_id`   BIGINT UNSIGNED NOT NULL,
    `target_title_id`   BIGINT UNSIGNED NOT NULL,
    `similarity_score`  DECIMAL(6,5) NOT NULL,   -- e.g. cosine similarity 0.00000‑1.00000
    `rank`              SMALLINT UNSIGNED NOT NULL,  -- 1 = most similar
    `computed_at`       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`source_title_id`, `target_title_id`),
    CONSTRAINT `fk_sim_source` FOREIGN KEY (`source_title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_sim_target` FOREIGN KEY (`target_title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
    INDEX `idx_source_rank` (`source_title_id`, `rank`),
    INDEX `idx_score` (`similarity_score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optional: view to ease querying a title with its genres/keywords/people
-- (not required but handy)
-- CREATE OR REPLACE VIEW `title_detail` AS ...