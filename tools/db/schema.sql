
CREATE TABLE IF NOT EXISTS search_count (id64 BIGINT UNSIGNED NOT NULL, ip VARCHAR(40) NOT NULL);

CREATE TABLE IF NOT EXISTS profiles (id64 BIGINT UNSIGNED PRIMARY KEY,
                                     persona VARCHAR(32),
                                     vanity VARCHAR(32),
                                     real_name VARCHAR(60),
                                     last_server_ip VARCHAR(40),
                                     last_app_id INT UNSIGNED,
                                     last_game_info TEXT,
                                     profile_url TEXT,
                                     avatar_url TEXT,
                                     primary_group BIGINT UNSIGNED,
                                     profile_status TINYINT UNSIGNED,
                                     online_status TINYINT UNSIGNED,
                                     timestamp INTEGER NOT NULL,
                                     bp_views INTEGER UNSIGNED NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS items (id64 BIGINT UNSIGNED PRIMARY KEY,
                                  oid64 BIGINT UNSIGNED,
                                  owner BIGINT UNSIGNED NOT NULL,
                                  sid INTEGER UNSIGNED NOT NULL,
                                  level TINYINT UNSIGNED NOT NULL,
                                  untradeable BOOLEAN NOT NULL,
                                  token INTEGER UNSIGNED NOT NULL,
                                  quality TINYINT UNSIGNED NOT NULL,
                                  custom_name VARCHAR(40),
                                  custom_desc VARCHAR(80),
                                  style TINYINT UNSIGNED,
                                  quantity INTEGER UNSIGNED DEFAULT 1 NOT NULL) ENGINE MyISAM;

CREATE TABLE IF NOT EXISTS attributes (id64 BIGINT UNSIGNED PRIMARY KEY, attrs BLOB NOT NULL, contents BLOB) ENGINE MyISAM;

CREATE TABLE IF NOT EXISTS backpacks (id64 BIGINT UNSIGNED NOT NULL, backpack MEDIUMBLOB NOT NULL,
                                      timestamp INTEGER UNSIGNED NOT NULL,
                                      id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, INDEX (id64));

CREATE TABLE IF NOT EXISTS sessions (session_id CHAR(128) UNIQUE NOT NULL, atime timestamp NOT NULL default current_timestamp, data TEXT);
