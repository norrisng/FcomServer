from discord.ext import commands
from bot import bot_user_commands
from dbmanager import db_manager
import asyncio
import logging

description = 'FCOM bot'
bot = commands.Bot(command_prefix='!', description=description)

token_file = open('../FcomServer/bot_token.txt')
token = token_file.read()

logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')


# Reference: https://github.com/Rapptz/discord.py/blob/rewrite/examples/background_task.py
async def forward_messages():
    """
    Retrieves submitted PMs from the DB and forwards them to the registered Discord user.
    """

    await bot.wait_until_ready()

    # TODO: do not run loop before the bot is ready
    while not bot.is_closed():
        messages = db_manager.get_messages()

        # Iterate through queued messages (if any), and forward them via Discord DM
        if messages is not None:
            for msg in messages:

                dm_user = await db_manager.get_user_record(msg.token, bot)

                if dm_user is not None:
                    dm_contents = f'**{msg.sender}**:\n{msg.message}'
                    dm_channel = dm_user.channel_object
                    # TODO: https://github.com/Rapptz/discord.py/issues/623
                    await dm_channel.send(dm_contents)

                else:
                    # NOTE: the API now checks if a token's registered before inserting messages
                    logging.info(f'Token {msg.token} is not registered!')

        await asyncio.sleep(3)


@bot.event
async def on_ready():
    logging.info(f'Now logged in as {bot.user.name} (#{bot.user.id})')


@bot.event
async def on_message(message):
    """
    Handles user-issued commands via DM. All commands are case-insensitive.
    Supports the following commands:
        register:	Registers user to internal DB, and replies with a token.
                    This token must be confirmed via the API within 5 mins.
        status:     Shows the currently registered callsign (if any)
        remove:		De-registers the user from the internal DB.
    """
    # register
    if message.content.lower() == 'register':

        token = bot_user_commands.register_user(message.channel)
        # Already registered, so no token
        if token is None:
            msg = "You're already registered! To reset your registration, type `remove` before typing `register` again."
        else:
            msg = f"Here's your verification code: ```{token}```Please enter it into the client within the next 5 minutes."
            msg += "\n**TIP:** triple-click to quickly highlight, but delete the trailing space after pasting the token into the client."
        await message.channel.send(msg)

    # status
    elif message.content.lower() == 'status':

        user = await bot_user_commands.get_user(bot, message.channel.recipient)

        if user is None:
            msg = "You're currently not registered."
        elif not user.is_verified:
            msg = f"You're registered, but you haven't logged in via the client yet.\n(token:`{user.token}`)"
        else:
            msg = f"You're registered! The callsign you're using is **{user.callsign}**.\n(**token:** `{user.token}`)"

        await message.channel.send(msg)

    # remove
    elif message.content.lower() == 'remove':

        if bot_user_commands.remove_user(message.channel.recipient.id):
            msg = "Successfully deregistered! You'll no longer receive forwarded messages."
        else:
            msg = "Could not unregister. Are you sure you're registered?"

        await message.channel.send(msg)

    # test
    elif message.content.lower().startswith('test'):
        await message.channel.send('`beep boop`')
        usr = bot.get_user(message.channel.recipient.id)
        await usr.send("`i'm alive!`")


def start_bot():
    """
    Starts the bot
    :return:
    """
    bot.loop.create_task(forward_messages())
    bot.run(token)


start_bot()