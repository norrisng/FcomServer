from discord import User, DMChannel, Client
from dbmanager import db_manager
from dbmodels import user_registration


def register_user(user_channel: DMChannel) -> str:
    """
    Add the Discord user to the DB, generating a token to be used by the client.
    The user must be confirmed via the API within 5 minutes of creation.

    :param user_channel:    The DMChannel containing the Discord user to be added
    :return:                The token associated with the Discord user.
    """
    user = user_channel.recipient
    token = db_manager.add_discord_user(user.id, f'{user.name} #{user.discriminator}', user_channel)
    return token


async def get_user(client: Client, user: User) -> user_registration.UserRegistration:
    """
    Retrieves the registration entry of the given Discord user.

    :param client:  The bot object
    :param user:    discord.py User object
    :return:        Representation of user in the DB. Returns None if not present.
    """
    return await db_manager.get_user_record(user.id, client)


def remove_user(discord_id: int) -> bool:
    """
    Removes the specified user from the DB.

    :param discord_id:  Discord ID of the user to remove
    :return:            True on success, False otherwise
    """
    if db_manager.remove_discord_user(discord_id):
        return True
    else:
        return False
