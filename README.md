# FCOM server

**Note:** if you're just looking to use FCOM, please see [the repository for FcomClient](https://github.com/norrisng/FcomClient/).

Also, I would prefer that you don't run an instance of my bot. Just use the one I have!

## Overview ##

Although the bot appears to users as a single, cohesive entity, it actually consists of three separate components:

* A client-facing Flask API
    * Accepts forwarded messages
    * Provides clients with the Discord username (and Snowflake ID) associated with a given registration token  
* A Discord bot
    * Sends the forwarded messages to the associated Discord user
* A relational database (specifically, MariaDB)
    * This acts as the link between the two
    * It also stores the mappings between Discord users and FCOM clients

The bot and the API (i.e. this repository) need to be run simultaneously.

## Requirements

- Python 3.6+
- discord.py (rewrite)
- Flask
- mysql.connector

The `requirements.txt` file also contains a number of dependencies, but these are the main ones required.

## Server setup

### Database ###

```mysql
CREATE DATABASE fcom;
```

#### Tables ####

```mariadb
CREATE TABLE messages ( 
	id INTEGER PRIMARY KEY AUTO_INCREMENT,
	insert_time timestamp NOT NULL, 
	token varchar(43) NOT NULL, 
	time_received timestamp NOT NULL,
	sender varchar(20) NOT NULL, 
	receiver varchar(20) NOT NULL, 
	message TEXT 
);
```

```mariadb
CREATE TABLE registration ( 
	last_updated timestamp,
	token varchar(43), 
	discord_id bigint(20) UNIQUE, 
	discord_name varchar(32), 
	is_verified boolean, 
	callsign varchar(20), 
	PRIMARY KEY(token, discord_id) 
);
```

(Yes, you'll have to do this manually for now. Seriously, just use my own bot!)

Of course, you'll also have to create a user in the DB. The username and password for it should be stored in the following environment variables:

* Username: `FCOM_DB_USERNAME`
* Password: `FCOM_DB_PASSWORD`

### Bot and API ###

First, download from GitHub, then set up `virtualenv`:

```commandline
cd FcomServer
python3.6 -m venv ./venv
source ./venv/bin/activate
pip3 install wheel
pip3 install -r requirements.txt
pip3 install gunicorn
```

Then, run both the bot and the API. They must be run simultaneously.
```commandline
python3 main_bot.py
python3 main_api.py
```
To get out of the virtual environment:
```commandline
deactivate
```



