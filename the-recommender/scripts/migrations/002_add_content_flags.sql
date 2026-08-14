-- Add content-flag columns used by the "Adult content" hard-no filter.
--  - adult          : TMDB's own adult flag (0/1)
--  - certification  : US theatrical certification for movies (e.g. R, NC-17, X)
--  - content_rating : US content rating for TV (e.g. TV-14, TV-MA)
ALTER TABLE `titles`
  ADD COLUMN `adult` TINYINT(1) NOT NULL DEFAULT 0 AFTER `original_language`,
  ADD COLUMN `certification` VARCHAR(10) NULL AFTER `adult`,
  ADD COLUMN `content_rating` VARCHAR(10) NULL AFTER `certification`;
