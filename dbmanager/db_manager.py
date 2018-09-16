import sqlite3
import secrets
import os
import time
from dbmodels.user_registration import UserRegistration
from dbmodels.fsd_message import FsdMessage
from discord import DMChannel, Client
from typing import List

REGISTRATION_PATH = os.path.realpath('../FcomServer/registration.db')
MESSAGES_PATH = os.path.realpath('../FcomServer/messages.db')

# This acts as a local cache for DMChannel objects.
# This avoids the need to reach the Discord API every time a DM needs to be sent.
pm_channels = {}


def add_discord_user(discord_id: int, discord_name: str, channel_object: DMChannel) -> str:
    """
    Adds the specified Discord user to the DB, and generates a token for it.

    :param discord_id:      Discord ID
    :param discord_name:    Discord user name, including the discriminator (e.g. "username#001")
    :param channel_object:  DMChannel object for the specified Discord user
    :return:                Token, if the user isn't already in the DB
    """
    conn = sqlite3.connect(REGISTRATION_PATH)
    db = conn.cursor()

    # First, check if the user is already registered
    cmd = "SELECT * FROM registration where discord_id=?"
    db.execute(cmd, (discord_id,))
    user = db.fetchone()

    if user is not None:
        conn.close()
        return None
    else:
        token = secrets.token_urlsafe(32)

        cmd = "INSERT INTO registration VALUES (?,?,?,0,NULL)"
        db.execute(cmd, (token, discord_id, discord_name))
        conn.commit()
        conn.close()
        pm_channels[discord_id] = channel_object
        return token


def confirm_discord_user(token: str, callsign: str) -> bool:
    """
    Marks the specified token as confirmed, and saves the callsign to the Discord user.

    :param token:    the token associated with a given user
    :param callsign: the callsign that the Discord user wants to register
    :return:         True if success, False otherwise
    """
    conn = sqlite3.connect(REGISTRATION_PATH)
    db = conn.cursor()

    # First, check if the token exists
    cmd = "SELECT * FROM registration WHERE token=?"
    db.execute(cmd, (token,))
    user = db.fetchone()

    if user is None:
        conn.close()
        return False
    else:
        cmd = "UPDATE registration SET callsign=?, is_verified=1 WHERE token=?"
        db.execute(cmd, (callsign, token))
        conn.commit()
        conn.close()
        return True


# NOTE: original signature:
# get_user_record(param, client: Client) -> UserRegistration:
async def get_user_record(param, client: Client = None) -> UserRegistration:
    """
    Retrieves the specified user from the registration DB.

    :param param:   Discord ID (int) or token (str)
    :param client:  The bot object
    :return:        UserRegistration object if in DB, None otherwise
    """
    is_int = isinstance(param, int)
    is_str = isinstance(param, str)

    if not (isinstance(param, int) or isinstance(param, str)):
        return None
    else:
        result = get_user_record_tuple(param)

        if result is None:
            return None
        else:
            # user = UserRegistration()
            token = result[0]
            discord_id = result[1]
            discord_name = result[2]
            is_verified = result[3]
            callsign = result[4]

            # If a client isn't provided, assume that this function is being called by the API,
            # and therefore doesn't required Discord-related features
            if client is not None:
                channel_object = await get_channel(client, discord_id)
            else:
                channel_object = None

            return UserRegistration(token, discord_id, discord_name, is_verified, callsign, channel_object)


def get_user_registration(req_token: str) -> UserRegistration:
    """
    Retrieves the specified user from the registration DB.
    This function does not use ``asyncio``, and the corresponding ``DMChannel`` is not provided.

    :param req_token:   The token associated with the registered Discord user.
        :return:        User registration entry in the DB. Returns ``None`` if specified token doesn't exist.
                        ``UserRegistration.channel_object`` will be ``None``!
    """
    result = get_user_record_tuple(req_token)

    if result is None:
        return None
    else:
        # user = UserRegistration()
        token = result[0]
        discord_id = result[1]
        discord_name = result[2]
        is_verified = result[3]
        callsign = result[4]

    return UserRegistration(token, discord_id, discord_name, is_verified, callsign, None)


def remove_discord_user(discord_id: int) -> bool:
    """
    Removes the specified user from the DB.

    :param discord_id:  ID of the Discord user to de-register
    :return:            True on success, False otherwise
    """
    if not user_exists(discord_id):
        return False
    else:
        conn = sqlite3.connect(REGISTRATION_PATH)
        db = conn.cursor()
        cmd = "DELETE FROM registration WHERE discord_id=?"
        db.execute(cmd,(discord_id,))
        conn.commit()
        conn.close()
        try:
            del pm_channels[discord_id]
        except KeyError:
            pass
        return True


def insert_message(msg: FsdMessage):
    conn = sqlite3.connect(MESSAGES_PATH)
    db = conn.cursor()
    cmd = "INSERT INTO messages(insert_time, token, timestamp, sender, receiver, message) VALUES (?, ?, ?, ?, ?, ?)"
    db.execute(cmd, (int(time.time()), msg.token, msg.timestamp, msg.sender, msg.receiver, msg.message))
    conn.commit()
    conn.close()


def get_messages() -> List[FsdMessage]:
    """
    Retrieve and dequeue messages from the DB queue.
    Messages are aggregated if they share the same token and sender.
    Individual message contents are separated by a newline ('\n');
    e.g. 'contents of earlier message\ncontents of later message'.

    :return:    Messages in DB queue, aggregated by token/sender,
                and sorted by registration token, then by arrival order
                (both in ascending order).
    """
    connection = sqlite3.connect(MESSAGES_PATH)
    connection.isolation_level = None
    cursor = connection.cursor()

    cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
    cursor.execute("""SELECT 
                          token, 
                          timestamp, 
                          sender, 
                          receiver, 
                          GROUP_CONCAT(message,'\n')
                      FROM messages
                      GROUP BY 
                          token, sender
                      ORDER BY token ASC, id ASC;                      
                  """)
    messages = cursor.fetchall()

    cursor.execute("SELECT MAX(id) FROM messages")
    most_recent_id = cursor.fetchone()[0]

    cmd = "DELETE FROM messages WHERE id <= ?;"
    cursor.execute(cmd, (most_recent_id,))
    cursor.execute("COMMIT;")

    connection.close()

    # This is the list that gets returned
    message_list = []

    # Parse returned results into FsdMessage objects
    # DB schema:    (id, insert_time, token, timestamp, sender, receiver, message)
    # FsdMessage:   (token, timestamp, sender, receiver, message)
    for msg in messages:
        token = msg[0]
        timestamp = msg[1]
        sender = msg[2]
        receiver = msg[3]
        combined_contents = msg[4]
        message_list.append(FsdMessage(token, timestamp, sender, receiver, combined_contents))

    return message_list


def user_exists(discord_id: int) -> bool:
    """
    Internal helper function for determining if a particular Discord ID is in the DB.

    :param discord_id:  Discord ID
    :return:            True if it exists, False otherwise
    """

    connection = sqlite3.connect(REGISTRATION_PATH)
    cursor = connection.cursor()
    cmd = "SELECT * FROM registration WHERE discord_id=?;"
    cursor.execute(cmd,(discord_id,))
    user = cursor.fetchone()

    connection.close()

    if user is None:
        return False
    else:
        return True


def get_user_record_tuple(param) -> ():
    """
    Internal method for retrieving the user registration record from the DB.
    :return:
    """
    conn = sqlite3.connect(REGISTRATION_PATH)
    db = conn.cursor()

    # discord_id provided
    if isinstance(param, int):
        cmd = "SELECT * FROM registration WHERE discord_id=?"

    # token provided
    # else:
    elif isinstance(param, str):
        cmd = "SELECT * FROM registration WHERE token=?"
    else:
        return None

    db.execute(cmd, (param,))
    result = db.fetchone()

    return result


async def get_channel(client: Client, discord_id: int) -> DMChannel:
    """
    Internal method for retrieving the DMChannel for a particular user.

    :param client:      The bot object
    :param discord_id:  Discord snowflake ID of the user
    :return:            DMChannel for the specified Discord user
    """
    try:
        channel = pm_channels[discord_id]
    except KeyError:
        user = await client.get_user_info(discord_id)
        ch = user.dm_channel

        if ch is None:
            ch = await user.create_dm()

        # Save to internal dictionary
        pm_channels[discord_id] = ch
        channel = ch

        # channel = client.get_channel(channel_id)
        # channel = client.get_all_channels()
        # pm_channels[channel_id] = channel

    return channel
