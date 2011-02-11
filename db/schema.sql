
CREATE TABLE IF NOT EXISTS search_count (id64 BIGINT UNSIGNED, ip VARCHAR(200));

CREATE TABLE IF NOT EXISTS profile_cache (id64 BIGINT UNSIGNED PRIMARY KEY, vanity TEXT, profile BLOB, timestamp INTEGER);

CREATE TABLE IF NOT EXISTS unique_views (id64 BIGINT UNSIGNED PRIMARY KEY, count INTEGER UNSIGNED DEFAULT 1, persona TEXT, valve BOOLEAN);

CREATE TABLE IF NOT EXISTS items (id64 BIGINT UNSIGNED PRIMARY KEY,
                                  owner BIGINT UNSIGNED,
                                  sid INTEGER UNSIGNED,
                                  level INTEGER UNSIGNED,
                                  untradeable BOOLEAN,
                                  token INTEGER UNSIGNED,
                                  quality TINYINT UNSIGNED,
                                  custom_name TEXT,
                                  custom_desc TEXT,
                                  attributes BLOB,
                                  quantity INTEGER UNSIGNED DEFAULT 1);

CREATE TABLE IF NOT EXISTS backpacks (id64 BIGINT UNSIGNED, backpack BLOB, timestamp INTEGER UNSIGNED);

CREATE TABLE IF NOT EXISTS sessions (session_id CHAR(128) UNIQUE NOT NULL, atime timestamp NOT NULL default current_timestamp, data TEXT);
