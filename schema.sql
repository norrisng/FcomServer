 CREATE TABLE messages
  (
     id            INTEGER PRIMARY KEY auto_increment,
     insert_time   TIMESTAMP NOT NULL,
     token         VARCHAR(43) NOT NULL,
     time_received TIMESTAMP NOT NULL,
     sender        VARCHAR(20) NOT NULL,
     receiver      VARCHAR(20) NOT NULL,
     message       TEXT
  )
CHARACTER SET utf8mb4;

CREATE TABLE registration
  (
     last_updated TIMESTAMP,
     token        VARCHAR(43),
     discord_id   BIGINT(20) UNIQUE,
     discord_name VARCHAR(32),
     is_verified  BOOLEAN,
     callsign     VARCHAR(20),
     PRIMARY KEY(token, discord_id)
  )
CHARACTER SET utf8mb4;  