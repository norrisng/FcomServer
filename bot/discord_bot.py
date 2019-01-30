from discord.ext import commands
from discord import errors as discordpy_error, Game, Status
from aiohttp import ClientError
from websockets import exceptions as websocket_error
from bot import bot_user_commands
from dbmanager import db_manager
import asyncio
import logging

description = 'FCOM bot'
bot = commands.Bot(command_prefix='!', description=description)

token_file = open('../FcomServer/bot_token.txt')
token = token_file.read()

logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s: %(message)s')


# Reference: https://github.com/Rapptz/discord.py/blob/rewrite/examples/background_task.py
async def forward_messages():
    """
    Background task that retrieves submitted PMs from the DB and forwards them to the registered Discord user.
    """

    await bot.wait_until_ready()

    while not bot.is_closed():
        messages = db_manager.get_messages()

        # Iterate through queued messages (if any), and forward them via Discord DM
        if messages is not None:
            for msg in messages:

                dm_user = await db_manager.get_user_record(msg.token, bot)

                if dm_user is not None:

                    # if it's a frequency message (i.e. @xxyyy), parse it into a user-friendly format
                    if msg.receiver.startswith('@'):
                        freq = msg.receiver.replace('@','1')[:3] + '.' + msg.receiver[3:]
                        dm_contents = f'**{msg.sender} ({freq} MHz):**\n{msg.message}'

                    else:
                        dm_contents = f'**{msg.sender}**:\n{msg.message}'

                    dm_channel = dm_user.channel_object
                    await dm_channel.send(dm_contents)

                else:
                    # NOTE: the API now checks if a token's registered before inserting messages
                    logging.info(f'Token {msg.token} is not registered!')

        await asyncio.sleep(3)


async def update_status():
    """
    Updates the bot's status, which contains the number of FCOM-registered users.
    Updates every 30s.
    """
    await bot.wait_until_ready()

    while not bot.is_closed():
        num_users = db_manager.get_num_users()
        status_string = f'with messages for {num_users} users'

        bot.change_presence(status=Status.idle, activity=Game(status_string))

        await asyncio.sleep(30)


async def prune_registrations():
    """
    Remove registrations that are either unconfirmed and older than 5 minutes,
    or confirmed and older than 24 hours.

    """
    db_manager.remove_stale_users()
    await asyncio.sleep(60*5)


@bot.event
async def on_ready():
    logging.info(f'Now logged in as {bot.user.name} ({bot.user.id})')


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
    # Do not reply to self
    if message.author.id == bot.user.id:
        return

    # register
    elif message.content.lower() == 'register':

        fcom_api_token = bot_user_commands.register_user(message.channel)

        if fcom_api_token is None:
            msg = "You're already registered! To reset your registration, type `remove` before typing `register` again."
        else:
            msg = f"Here's your verification code: ```{fcom_api_token}```" +\
                    "Please enter it into the client within the next 5 minutes.\n"
            logging.info(
                f'Generate token:\t\t{fcom_api_token}, {message.channel.recipient.id} '
                f'({message.channel.recipient.name} #{message.channel.recipient.discriminator}) ')
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
            logging.info(f'Deregister user:\t{message.channel.recipient.id} '
                         f'({message.channel.recipient.name} #{message.channel.recipient.discriminator})')
        else:
            msg = "Could not unregister. Are you sure you're registered?"

        await message.channel.send(msg)


def start_bot():
    """
    Starts the bot
    :return:
    """
    bot.loop.create_task(forward_messages())
    bot.loop.create_task(prune_registrations())
    bot.loop.create_task(update_status())

    retry = True

    # Based on https://gist.github.com/Hornwitser/93aceb86533ed3538b6f
    while retry:

        # Linearly increasing backoff for Discord server errors.
        wait_interval = 0
        max_wait_interval = 5 * 60      # 5-minute max interval between retries

        try:
            bot.run(token)

        except (discordpy_error.HTTPException) as e:
            logging.error("Couldn't login (discord.errors.HTTPException)")
            logging.error(f'{e.message}')

            if wait_interval < max_wait_interval:
                wait_interval = wait_interval + 5
            asyncio.sleep(wait_interval)

        except (ClientError) as e:
            logging.error("Couldn't login (discord.errors.ClientError)")
            logging.error(f'{e.message}')

            if wait_interval < max_wait_interval:
                wait_interval = wait_interval + 5
            asyncio.sleep(wait_interval)

        except (websocket_error.ConnectionClosed) as e:
            logging.info(f'{e.message}')

            # Don't reconnect on authentication failure
            if e.code == 4004:
                logging.error("Authentication error!")
                retry = False
                raise

        else:
            break


start_bot()
