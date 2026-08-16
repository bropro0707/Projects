-- The Recommender – base database schema.
--
-- Run this BEFORE the numbered migrations, e.g.:
--   mysql -u root -p movie_recommender < scripts/schema.sql
--   mysql -u root -p movie_recommender < scripts/migrations/001_add_title_columns.sql
--   mysql -u root -p movie_recommender < scripts/migrations/002_add_content_flags.sql
--
-- Note: 001/002 were written as standalone ALTERs for pre-existing databases.
-- This file already includes all of their columns, so on a fresh install you
-- only need to run schema.sql.

CREATE TABLE IF NOT EXISTS `genres` (
  `id`      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tmdb_id` INT UNSIGNED NOT NULL,
  `name`    VARCHAR(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_genres_tmdb` (`tmdb_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `keywords` (
  `id`      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tmdb_id` INT UNSIGNED NOT NULL,
  `name`    VARCHAR(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_keywords_tmdb` (`tmdb_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `people` (
  `id`           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tmdb_id`      INT UNSIGNED NOT NULL,
  `name`         VARCHAR(255) NOT NULL,
  `profile_path` VARCHAR(500) NULL,
  `gender`       TINYINT NULL,
  `popularity`   DECIMAL(10,3) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_people_tmdb` (`tmdb_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `titles` (
  `id`               INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tmdb_id`          INT UNSIGNED NOT NULL,
  `media_type`       ENUM('movie','tv') NOT NULL,
  `title`            VARCHAR(255) NOT NULL,
  `overview`         TEXT NULL,
  `release_date`     DATE NULL,
  `poster_path`      VARCHAR(500) NULL,
  `backdrop_path`    VARCHAR(500) NULL,
  `vote_average`     DECIMAL(3,1) NULL,
  `runtime`          INT UNSIGNED NULL,
  `vote_count`       INT UNSIGNED NULL,
  `popularity`       DECIMAL(10,3) NULL,
  `original_language` VARCHAR(10) NULL,
  `adult`            TINYINT(1) NOT NULL DEFAULT 0,
  `certification`    VARCHAR(10) NULL,
  `content_rating`   VARCHAR(10) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_titles_tmdb_media` (`tmdb_id`, `media_type`),
  KEY `idx_titles_media_type` (`media_type`),
  KEY `idx_titles_release_date` (`release_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `title_genres` (
  `title_id` INT UNSIGNED NOT NULL,
  `genre_id` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`title_id`, `genre_id`),
  KEY `idx_tg_genre` (`genre_id`),
  CONSTRAINT `fk_tg_title` FOREIGN KEY (`title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_tg_genre` FOREIGN KEY (`genre_id`) REFERENCES `genres` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `title_keywords` (
  `title_id`   INT UNSIGNED NOT NULL,
  `keyword_id` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`title_id`, `keyword_id`),
  KEY `idx_tk_keyword` (`keyword_id`),
  CONSTRAINT `fk_tk_title` FOREIGN KEY (`title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_tk_keyword` FOREIGN KEY (`keyword_id`) REFERENCES `keywords` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `title_people` (
  `title_id`  INT UNSIGNED NOT NULL,
  `person_id` INT UNSIGNED NOT NULL,
  `role`      ENUM('actor','director') NOT NULL,
  `character` VARCHAR(255) NULL,
  `order_idx` INT UNSIGNED NULL,
  PRIMARY KEY (`title_id`, `person_id`, `role`),
  KEY `idx_tp_person` (`person_id`),
  CONSTRAINT `fk_tp_title` FOREIGN KEY (`title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_tp_person` FOREIGN KEY (`person_id`) REFERENCES `people` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `similar_titles` (
  `source_title_id` INT UNSIGNED NOT NULL,
  `target_title_id` INT UNSIGNED NOT NULL,
  `similarity_score` DOUBLE NOT NULL,
  `rank`             INT UNSIGNED NOT NULL,
  PRIMARY KEY (`source_title_id`, `target_title_id`),
  KEY `idx_st_target` (`target_title_id`),
  CONSTRAINT `fk_st_source` FOREIGN KEY (`source_title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_st_target` FOREIGN KEY (`target_title_id`) REFERENCES `titles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;