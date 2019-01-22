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
- Gunicorn
- mysql.connector

The `requirements.txt` file also contains a number of dependencies, but these are the main ones required.

## Server setup

### Database ###

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

Create a file named `bot_token.txt` inside the FcomServer folder (i.e. at the top level). It should contain your bot token.

Then, run both the bot and the API. They must be run simultaneously.

```commandline
python3 main_bot.py
python3 main_api.py
```
If you want to have both run in the background, you'll have to set them up as a service on your operating system.

To get out of the virtual environment:

```commandline
deactivate
```



