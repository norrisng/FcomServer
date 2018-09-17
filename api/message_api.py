from flask import Flask, request, abort, jsonify
from dbmodels.fsd_message import FsdMessage
from dbmanager import db_manager
import sqlite3
import logging


app = Flask(__name__)
logging.basicConfig(filename='api.log', level=logging.INFO, format='%(asctime)s: %(message)s')


@app.route('/api/v1/test', methods=['GET'])
def test():
    return "Success"


@app.route('/api/v1/register', methods=['GET'])
def register_user():
    """
    Marks the user as registered in the registration DB, and returns info on the Discord user.
    :return:
    """
    callsign = request.args.get('callsign')
    token = request.args.get('token')

    if token is None:
        return jsonify(status=400, detail='Missing token'), 400

    elif callsign is None:
        return jsonify(status=400, detail='Missing callsign'), 400

    else:
        requested_user = db_manager.get_user_registration(token)
        if requested_user is None:
            return jsonify(status=400, detail="Provided token is not registered to any Discord user"), 400
        else:
            db_manager.confirm_discord_user(token, callsign)

            discord_id = requested_user.discord_id
            discord_name = requested_user.discord_name

            return_string = jsonify(token=token, discord_id=discord_id, discord_name=discord_name, callsign=callsign)
            return return_string


@app.route('/api/v1/messaging', methods=['POST'])
def post_message():
    if request.content_type != 'application/json':
        return jsonify(status=400, detail='Only JSON is supported at this time.'), 400

    payload = request.get_json()

    try:
        # token, list of messages
        token = payload['token']

        # TODO: support parsing of multiple messages per POST request
        message = payload['messages'][0]

        timestamp = message['timestamp']
        sender = message['sender']
        receiver = message['receiver']
        message = message['message']

        logging.info(f'{request.remote_addr} - - {token}, {timestamp}, {sender} > {receiver}: "{message}"')

        # Abort if token not associated with any Discord user
        discord_user = db_manager.get_user_registration(token)
        if discord_user is None:
            logging.info(f'{request.remote_addr} - - token "{token}" not found!')
            return jsonify(status=400, detail="Provided token isn't registered!"), 400

        # full_pm = FsdMessage(sender, receiver, timestamp, message)
        db_manager.insert_message(FsdMessage(token, timestamp, sender, receiver, message))

        # return jsonify({'message': message}), 201
        return 'ok'

    except KeyError:
        error_detail = ('Missing parameter(s). Requests should include a token, and an array of message objects.'
                        'Each message object should include a timestamp, sender, receiver, and message (contents).')
        return jsonify(status=400, detail=error_detail), 400


# Currently unused
def log_request(receive_time, timestamp, sender, receiver, message):

    conn = sqlite3.connect('../request_log.db')
    db = conn.cursor()
    cmd = "INSERT INTO messages VALUES (?, ?, ?, ?, ?)"

    db.excecute(cmd, receive_time)
    conn.close()
