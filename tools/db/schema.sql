
CREATE TABLE IF NOT EXISTS search_count (id64 BIGINT UNSIGNED, ip VARCHAR(200));

CREATE TABLE IF NOT EXISTS profile_cache (id64 BIGINT UNSIGNED PRIMARY KEY, vanity TEXT, profile BLOB, timestamp INTEGER);

CREATE TABLE IF NOT EXISTS unique_views (id64 BIGINT UNSIGNED PRIMARY KEY, count INTEGER UNSIGNED DEFAULT 1, persona TEXT, valve BOOLEAN);

CREATE TABLE IF NOT EXISTS items (id64 BIGINT UNSIGNED PRIMARY KEY,
                                  oid64 BIGINT UNSIGNED,
                                  owner BIGINT UNSIGNED,
                                  sid INTEGER UNSIGNED,
                                  level TINYINT UNSIGNED,
                                  untradeable BOOLEAN,
                                  token INTEGER UNSIGNED,
                                  quality TINYINT UNSIGNED,
                                  custom_name VARCHAR(40),
                                  custom_desc VARCHAR(80),
                                  style TINYINT UNSIGNED,
                                  quantity INTEGER UNSIGNED DEFAULT 1);

CREATE TABLE IF NOT EXISTS attributes (id64 BIGINT UNSIGNED PRIMARY KEY, attrs BLOB NOT NULL);

CREATE TABLE IF NOT EXISTS backpacks (id64 BIGINT UNSIGNED, backpack BLOB, timestamp INTEGER UNSIGNED, INDEX (id64, timestamp));

CREATE TABLE IF NOT EXISTS sessions (session_id CHAR(128) UNIQUE NOT NULL, atime timestamp NOT NULL default current_timestamp, data TEXT);
