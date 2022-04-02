from flask import Flask, request, jsonify
from dbmodels.fsd_message import FsdMessage
from dbmanager import db_manager
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import re
from datetime import datetime, timedelta


app = Flask(__name__)

# Logging config #

if not os.path.exists('logs'):
    os.mkdir('logs')

formatter = logging.Formatter(fmt='%(asctime)s: %(message)s')
handler = TimedRotatingFileHandler(f'logs/api.log', when='midnight', backupCount=15)
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# End logging config #

try:
    curr_version_file = open('../FcomServer/curr_client_version.txt')
    curr_version = curr_version_file.read().replace('FcomClient/','').rstrip()

    # Just in case curr_client_version.txt isn't in the format FcomClient/x.y.z
    version_regex = '\d\.\d\.\d'    # x.y.z
    if not re.match(version_regex, curr_version):
        curr_version = '0.0.0'

except FileNotFoundError:
    curr_version = '0.0.0'


@app.route('/api/v1/test', methods=['GET'])
def test():
    """
    Simple test endpoint for checking if the API is working.

    :return: "Success"
    """
    return "Success"


@app.route('/api/v1/register', methods=['GET'])
def register_user():
    """
    Marks the user as registered in the registration DB, and returns info on the Discord user.

    :return: JSON object containing the token, Discord ID, Discord name, and callsign.
            If the token doesn't exist, an error is returned.
    """
    callsign = request.args.get('callsign').upper()
    token = request.args.get('token')
    client_version = request.headers.get('User-Agent').replace('FcomClient/','')

    logger.info(f'Registration:\t{token} ({callsign})')

    if token is None:
        return jsonify(status=400, detail='Missing token'), 400

    elif callsign is None:
        return jsonify(status=400, detail='Missing callsign'), 400

    else:
        requested_user = db_manager.get_user_registration(token)
        if requested_user is None:
            return jsonify(status=400, detail="Provided token is not registered to any Discord user"), 400
        else:
            db_manager.confirm_discord_user(token, callsign.upper())

            expiry_time = requested_user.last_updated + timedelta(1.5)
            expiry_time_string = f"{str(expiry_time)[:16]}"

            curr_time = round(datetime.utcnow().timestamp())
            message = f"Callsign **{callsign}** " +\
                      f"(expires **{expiry_time_string}** UTC)\n" +\
                      "To deregister, type `remove` here, or click on **Stop** inside the client."

            # Error in parsing curr_client_version.txt
            if curr_version == '0.0.0':
                pass
            # Client version is newer (suppresses "new version available" message)
            elif float(client_version[0:3]) >= float(curr_version[0:3]):
                pass
            # Outdated client version
            elif client_version != curr_version:
                message = message + "\n\n**NEW CLIENT VERSION AVAILABLE**" +\
                            f" - latest version is **{curr_version}** " +\
                            "\nhttps://github.com/norrisng/FcomClient/releases"

            db_manager.insert_message(FsdMessage(token, curr_time, 'Registered', callsign, message))

            discord_id = requested_user.discord_id
            discord_name = requested_user.discord_name

            return_string = jsonify(token=token, discord_id=discord_id, discord_name=discord_name, callsign=callsign)
            return return_string


@app.route('/api/v1/messaging', methods=['POST'])
def post_message():
    """
    Forwards a message to a Discord user.

    :return: 'ok' on success. A 400 error with details is returned if the request is in the incorrect format.
    """
    if request.content_type != 'application/json':
        return jsonify(status=400, detail='Only JSON is supported at this time.'), 400

    payload = request.get_json()

    try:
        # token, list of messages
        token = payload['token']

        # TODO: support parsing of multiple messages per POST request
        message = payload['messages'][0]

        timestamp_raw = message['timestamp']
        sender_raw = message['sender']
        receiver_raw = message['receiver']
        message = message['message']

        # Check timestamp
        try:
            timestamp = int(timestamp_raw)
        except ValueError:
            return jsonify(status=400, detail='Timestamp must be an integer.'), 400

        # Check sender
        sender_regex = '(\w|\d|_|-)+'

        if re.match(sender_regex, sender_raw, re.ASCII):
            sender = sender_raw
        else:
            error_detail = ('Sender field must be 20 characters or less,'
                            'and can only contain letters, numbers, dashes, and underscores.')
            return jsonify(status=400, detail=error_detail), 400

        # Check receiver (we also have to accept frequencies; e.g. @22800)
        receiver_regex = '(@\d{5})|(\w|\d|_|-)+'

        if re.match(receiver_regex, receiver_raw, re.ASCII):

            # Parse @xxyyy into 1xx.yyy MHz
            # if receiver_raw.startswith('@') and len(receiver_raw) == 6:
            #     receiver = f'{receiver_raw[:3]}.{receiver_raw[3:]} MHz'
            # else:
            receiver = receiver_raw
        else:
            error_detail = ('Receiver field must be 20 characters or less, '
                            'and can only contain letters, numbers, dashes, and underscores.'
                            'Alternatively, if it is a frequency message, it may begin with an '
                            '"@" and contain precisely 5 numerical digits.')
            return jsonify(status=400, detail=error_detail), 400

        logger.info(f'Message:\t\t{token}, {sender} > {receiver}')

        # Check token - if it's not associated with any Discord user, return an error
        discord_user = db_manager.get_user_registration(token)
        if discord_user is None:
            logger.info(f'Token not found:\t\t\t({token})')
            return jsonify(status=400, detail="Provided token isn't registered!"), 400

        db_manager.insert_message(FsdMessage(token, timestamp, sender, receiver, message))

        return 'ok'

    except KeyError:
        error_detail = ('Missing parameter(s). Requests should include a token, and an array of message objects.'
                        'Each message object should include a timestamp, sender, receiver, and message (contents).')
        return jsonify(status=400, detail=error_detail), 400
    
    except:
        logger.error(f'[Error] {payload}')
        error_detail = ('An unknown error occurred'
                        'Please see request_body for your original request which resulted in this error.')
        return jsonify(status=500, detail=error_detail, request_body=payload), 500


@app.route('/api/v1/deregister/<string:token>', methods=['DELETE'])
def deregister(token: str):
    """
    Deregisters a user via the API.
    Has the same effect as the `remove` Discord bot command.
    :return: 'ok' on success, 404 if it doesn't exist
    """

    error_msg = jsonify(status=404, detail='The requested token was not found.')

    discord_user = db_manager.get_user_registration(token)
    if discord_user is None:
        logger.info(f'Deregister request: [Not found] {token}')
        return error_msg
    else:
        logger.info(f'Deregister token {token}')

        if db_manager.remove_discord_user(token):
            return 'ok'
        else:
            return error_msg
