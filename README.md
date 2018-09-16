# FCOM server

Although the bot appears to users as a single, cohesive entity, it actually consists of three separate components:

* A client-facing Flask API
    * Accepts forwarded messages
    * Provides clients with the Discord username (and Snowflake ID) associated with a given registration token  
* A Discord bot
    * Sends the forwarded messages to the associated Discord user
* A SQLite database
    * This acts as the link between the two
    
Both the bot and the API need to be run simultaneously.

## Requirements

Aside from the packages specified inside `requirements.txt`, **Python 3.6** is also required.

## Server setup

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

More instructions on setting up the two programs as a persistent service to follow. 

## Third-party libraries

The following third-party Python libraries are used:
* discord.py (rewrite)
* Flask
