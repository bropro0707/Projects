-- Add columns used by the detail page and personalization filtering.
ALTER TABLE `titles`
  ADD COLUMN `backdrop_path` VARCHAR(500) NULL AFTER `poster_path`,
  ADD COLUMN `runtime` INT UNSIGNED NULL AFTER `vote_average`,
  ADD COLUMN `vote_count` INT UNSIGNED NULL AFTER `runtime`,
  ADD COLUMN `popularity` DECIMAL(10,3) NULL AFTER `vote_count`,
  ADD COLUMN `original_language` VARCHAR(10) NULL AFTER `popularity`;