import mysql.connector as mariadb
import secrets
import os
import time
from dbmodels.user_registration import UserRegistration
from dbmodels.fsd_message import FsdMessage
from discord import DMChannel, Client
from typing import List

# MariaDB
DB_URI = 'localhost'
DB_USERNAME = os.environ['FCOM_DB_USERNAME']
DB_PASSWORD = os.environ['FCOM_DB_PASSWORD']
DB_NAME = 'fcom'


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
    conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)

    db = conn.cursor()

    # First, check if the user is already registered
    cmd = "SELECT * FROM registration where discord_id=%s"
    db.execute(cmd, (discord_id,))
    user = db.fetchone()

    if user is not None:
        conn.close()
        return None
    else:
        token = secrets.token_urlsafe(32)

        # NOTE: 32 bytes = 43 characters
        token_length = 43

        # Replace all instances of the following with alphanumerics: _ - ~
        token = token.replace('_','')
        token = token.replace('-', '')

        # How many characters to regenerate?
        num_replacements = token_length - len(token)

        # Having these characters in here ensures that the subsequent loop runs at least once
        replacements = '_-'

        # Keep re-generating until there aren't any "_" or "-" 's
        while '_' in replacements or '-' in replacements:
            replacements = secrets.token_urlsafe(num_replacements)

        # token_urlsafe(n) produces a string of length n or higher (because n is in bytes),
        # so lop off any extra characters as necessary
        token = (token + replacements)[0:token_length]

        cmd = "INSERT INTO registration(token, discord_id, discord_name, is_verified) VALUES (%s,%s,%s,0)"
        db.execute(cmd, (token, discord_id, discord_name))
        conn.commit()
        conn.close()

        # Save the channel object to the internal cache
        pm_channels[discord_id] = channel_object
        return token


def confirm_discord_user(token: str, callsign: str, user_agent: str=None) -> bool:
    """
    Marks the specified token as confirmed, and saves the callsign to the Discord user.

    :param token:       the token associated with a given user
    :param callsign:    the callsign that the Discord user wants to register
    :param user_agent:  the user agent of the client (i.e. FcomClient)
    :return:            True if success, False otherwise
    """
    conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)

    db = conn.cursor()

    # First, check if the token exists
    cmd = "SELECT * FROM registration WHERE token=%s"
    db.execute(cmd, (token,))
    user = db.fetchone()

    if user is None:
        conn.close()
        return False
    else:
        cmd = "UPDATE registration SET callsign=%s, is_verified=1 WHERE token=%s"
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
    if not (isinstance(param, int) or isinstance(param, str)):
        return None
    else:
        result = get_user_record_tuple(param)

        if result is None:
            return None
        else:
            # user = UserRegistration()
            last_updated = result[0]
            token = result[1]
            discord_id = result[2]
            discord_name = result[3]
            is_verified = result[4]
            callsign = result[5]

            # If a client isn't provided, assume that this function is being called by the API,
            # and therefore doesn't required Discord-related features
            if client is not None:
                channel_object = await get_channel(client, discord_id)
            else:
                channel_object = None

            return UserRegistration(last_updated, token, discord_id, discord_name, is_verified, callsign, channel_object)


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
        last_updated = result[0]
        token = result[1]
        discord_id = result[2]
        discord_name = result[3]
        is_verified = result[4]
        callsign = result[5]

    return UserRegistration(last_updated, token, discord_id, discord_name, is_verified, callsign, None)


def remove_stale_users():
    """
    Remove unconfirmed users older than 5 minutes, and confirmed users registered for over 24 hours
    """
    conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)
    db = conn.cursor()

    db.execute("""
        DELETE FROM 
            registration
        WHERE 
            (is_verified is TRUE and last_updated < DATE_SUB(now(), interval 24 hour)) OR
            (is_verified is false and last_updated < DATE_SUB(now(), interval 5 minute))
        ;
    """)
    conn.commit()
    conn.close()


def remove_discord_user(discord_id: int) -> bool:
    """
    Removes the specified user from the DB.

    :param discord_id:  ID of the Discord user to de-register
    :return:            True on success, False otherwise
    """
    if not user_exists(discord_id):
        return False
    else:
        conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)

        db = conn.cursor()
        cmd = "DELETE FROM registration WHERE discord_id=%s"
        db.execute(cmd,(discord_id,))

        conn.commit()
        conn.close()
        try:
            del pm_channels[discord_id]
        except KeyError:
            pass
        return True


def insert_message(msg: FsdMessage):
    conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)

    db = conn.cursor()
    cmd = """   INSERT INTO 
                    messages(token, time_received, sender, receiver, message) 
                VALUES 
                    (%s, FROM_UNIXTIME(%s), %s, %s, %s)
            """
    db.execute(cmd, (msg.token, msg.timestamp, msg.sender, msg.receiver, msg.message))
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

    conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)
    cursor = conn.cursor()

    # TODO: implement a discord_id field in FsdMessage so that we don't need to make a separate query
    # cursor.execute("""SELECT
    #                         MAX(id),
    #                         discord_id,
    #                         messages.token,
    #                         time_received,
    #                         sender,
    #                         receiver,
    #                         GROUP_CONCAT(message ORDER BY id SEPARATOR ' / ') as message_contents
    #                     FROM messages
    #                     LEFT JOIN
    #                         registration on messages.token = registration.token
    #                     GROUP BY
    #                         token, sender
    #                     ORDER BY insert_time asc;
    #                 """)

    # NOTE: until we've implemented discord_id in FsdMessage, use NULL as a placeholder,
    #       so that the tuple indexes remain constant.
    cursor.execute("""SELECT 
                                MAX(id),
                                NULL,
                                messages.token, 
                                time_received, 
                                sender, 
                                receiver, 
                                GROUP_CONCAT(message ORDER BY id SEPARATOR '\n') as message_contents
                            FROM messages
                            -- LEFT JOIN 
                                -- registration on messages.token = registration.token
                            GROUP BY 
                                token, sender
                            ORDER BY insert_time asc;
                        """)

    messages = cursor.fetchall()

    # Old SQLite stuff
    # cursor.execute("SELECT MAX(id) FROM messages")
    # most_recent_id = cursor.fetchone()[0]

    # Default case: no messages retrieved
    if len(messages) == 0:
        most_recent_id = 0
    else:
        most_recent_id = messages[-1][0]

    cmd = "DELETE FROM messages WHERE id <= %s;"
    cursor.execute(cmd, (most_recent_id,))

    # Old SQLite stuff
    # cursor.execute("COMMIT;")

    conn.commit()
    conn.close()

    # This is the list that gets returned
    message_list = []

    # Parse returned results into FsdMessage objects
    # MariaDB results schema:
    #   (MAX(id), discord_id, messages.token, time_received, sender, receiver, message)
    # FsdMessage:
    #   (token, timestamp, sender, receiver, message)
    for msg in messages:
        # token = msg[0]
        # timestamp = msg[1]
        # sender = msg[2]
        # receiver = msg[3]
        # combined_contents = msg[4]

        token = msg[2]
        timestamp = msg[3]
        sender = msg[4]
        receiver = msg[5]
        combined_contents = msg[6]

        message_list.append(FsdMessage(token, timestamp, sender, receiver, combined_contents))

    return message_list


def is_beta_tester(discord_id: int) -> bool:
    """
    (CLOSED BETA ONLY) Determines if a Discord user is part of the closed beta.
    This info is stored in a SQLite file named `testers.db`.

    :param discord_id:  Discord snowflake ID of the user to check

    :return:    True if a beta tester, False otherwise
    """
    conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)
    db = conn.cursor()

    cmd = "SELECT * FROM testers where discord_id=%s"
    db.execute(cmd, (discord_id,))
    user = db.fetchone()
    conn.close()
    if user is not None:
        return True
    else:
        return False


def user_exists(discord_id: int) -> bool:
    """
    Internal helper function for determining if a particular Discord ID is in the DB.

    :param discord_id:  Discord ID
    :return:            True if it exists, False otherwise
    """
    conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)
    cursor = conn.cursor()
    cmd = "SELECT * FROM registration WHERE discord_id=%s;"
    cursor.execute(cmd,(discord_id,))
    user = cursor.fetchone()

    conn.close()

    if user is None:
        return False
    else:
        return True


def get_user_record_tuple(param) -> ():
    """
    Internal method for retrieving the user registration record from the DB.
    :return:
    """
    conn = mariadb.connect(host=DB_URI, user=DB_USERNAME, password=DB_PASSWORD, database=DB_NAME)

    db = conn.cursor()

    # discord_id provided
    if isinstance(param, int):
        cmd = "SELECT * FROM registration WHERE discord_id=%s"

    # token provided
    # else:
    elif isinstance(param, str):
        cmd = "SELECT * FROM registration WHERE token=%s"
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
