from flask import Flask, request, jsonify
from dbmodels.fsd_message import FsdMessage
from dbmanager import db_manager
import logging
import re
from datetime import datetime, timedelta


app = Flask(__name__)
logging.basicConfig(filename='api.log', level=logging.INFO, format='%(asctime)s: %(message)s')


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

    logging.info(f'Registration request:\t\t{token} ({callsign})')

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

            expiry_time = requested_user.last_updated + timedelta(1)

            curr_time = round(datetime.utcnow().timestamp())
            message = f"You've registered with the callsign **{callsign}**. " +\
                      "Don't forget to send `remove` to fully deregister!\n" +\
                      f"Your registration will expire at **{str(expiry_time)[:16]} (UTC)**."
            db_manager.insert_message(FsdMessage(token, curr_time, '[Registration]', callsign, message))

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
            return jsonify(status=400, detail='Sender field must be 20 characters or less,'
                                              'and can only contain letters, numbers, dashes, and underscores.'), \
                   400

        # Check receiver (we also have to accept frequencies; e.g. @22800)
        receiver_regex = '(@\d{5})|(\w|\d|_|-)+'

        if re.match(receiver_regex, receiver_raw, re.ASCII):

            # Parse @xxyyy into 1xx.yyy MHz
            # if receiver_raw.startswith('@') and len(receiver_raw) == 6:
            #     receiver = f'{receiver_raw[:3]}.{receiver_raw[3:]} MHz'
            # else:
            receiver = receiver_raw
        else:
            return jsonify(status=400, detail='Receiver field must be 20 characters or less,'
                                              'and can only contain letters, numbers, dashes, and underscores.'
                                              'Alternatively, if it is a frequency message, it may begin with an '
                                              '"@" and contain precisely 5 numerical digits.'), \
                   400

        logging.info(f'Forwarded message received:\t{token}, {sender} > {receiver}')

        # Check token - if it's not associated with any Discord user, return an error
        discord_user = db_manager.get_user_registration(token)
        if discord_user is None:
            logging.info(f'Token not found:\t\t\t({token})')
            return jsonify(status=400, detail="Provided token isn't registered!"), 400

        db_manager.insert_message(FsdMessage(token, timestamp, sender, receiver, message))

        return 'ok'

    except KeyError:
        error_detail = ('Missing parameter(s). Requests should include a token, and an array of message objects.'
                        'Each message object should include a timestamp, sender, receiver, and message (contents).')
        return jsonify(status=400, detail=error_detail), 400


@app.route('/api/v1/deregister/<string:token>', methods=['DELETE'])
def deregister(token: str):
    """
    Deregisters a user via the API.
    Has the same effect as the `remove` Discord bot command.
    :return: 'ok' on success, 404 if it doesn't exist
    """

    discord_user = db_manager.get_user_registration(token)
    if discord_user is None:
        logging.info(f'Deregister request: [Not found] {token}')
        return jsonify(status=404, detail='The requested token was not found.')
    else:
        logging.info(f'Deregister token {token}')
        # TODO: implement db_manager.remove_discord_user(token)
        return 'ok'