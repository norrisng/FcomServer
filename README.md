# FCOM server

**Note:** if you're just looking to use FCOM, please see [the repository for FcomClient](https://github.com/norrisng/FcomClient/).

Also, I would prefer that you don't run an instance of my bot. Just use the one I have!

## Overview ##

Although the bot appears to users as a single, cohesive entity, it actually consists of three separate components:

* A client-facing Flask API
    * Accepts forwarded messages
    * Allows clients to "confirm" a registration token and provide a callsign
        * The API responds with the Discord username (and Snowflake ID) associated with the given token
* A Discord bot
    * Sends the forwarded messages to the associated Discord user
* A relational database (specifically, MariaDB)
    * This acts as the link between the two
    * It also stores the mappings between Discord users and FCOM clients

The bot and the API need to be run simultaneously.

## Requirements

- Python 3.6+
- discord.py (rewrite)
- Flask
- Gunicorn
- mysql.connector

The `requirements.txt` file also contains a number of dependencies, but these are the main ones required.

## Server setup

### Database ###

#### Initial setup ####

```mysql
CREATE DATABASE fcom;
CREATE USER '<username>'@'localhost' identified by '<password>';
```

Create the following environment variables for the login:
* Username: `FCOM_DB_USERNAME`
* Password: `FCOM_DB_PASSWORD`

#### Tables ####

See included `schema.sql` file.


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

Create a file named `bot_token.txt` inside the FcomServer folder (i.e. at the top level). It should contain your bot token, and nothing else.

Then, run both the bot and the API. They must be run simultaneously.

```bash
python3 main_bot.py
python3 main_api.py
```
If you want to have both run in the background, you'll have to set them up as a service on your operating system.

As is the case with any Flask API, please use a production server to serve the FCOM API.
My implementation uses `gunicorn`, but you can use anything, really.

To get out of the virtual environment:

```bash
deactivate
```



#### User registration expiry ####

As of the time of writing, due to difficulties in getting the bot to clean up old registrations, this feature is implemented via a cronjob that runs every 5 minutes.

Implement the following SQL command via any tool of your choice, as long as it can be executed via `cron`:

```mysql
DELETE FROM registration
WHERE  ( is_verified IS TRUE
         AND last_updated < Date_sub(Now(), INTERVAL 24 hour) )
        OR ( is_verified IS FALSE
             AND last_updated < Date_sub(Now(), INTERVAL 5 minute) );
```