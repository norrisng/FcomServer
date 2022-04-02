import discord
from discord.ext import commands, tasks
from discord import DMChannel, errors as discordpy_error
from aiohttp import ClientError
from websockets import exceptions as websocket_error
from bot import bot_user_commands
from dbmanager import db_manager
from logging.handlers import TimedRotatingFileHandler
import asyncio
import logging
import os
import discord_credentials
import traceback

description = 'FCOM bot'
bot = commands.Bot(command_prefix='!', description=description)

token = discord_credentials.TOKEN

# Logging config #

if not os.path.exists('logs'):
    os.mkdir('logs')

formatter = logging.Formatter(fmt='%(asctime)s: %(message)s')
handler = TimedRotatingFileHandler(f'logs/bot.log', when='midnight', backupCount=15)
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# End logging config #


# https://github.com/Rapptz/discord.py/blob/master/examples/background_task.py
class BotClient(discord.Client):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        logger.info(f'Now logged in as {self.user.name} ({self.user.id})')
        self.forward_messages.start()
        self.prune_registrations.start()

    async def on_message(self, message):
        """
        Handles user-issued commands via DM. All commands are case-insensitive.
        Supports the following commands:
            register:	Registers user to internal DB, and replies with a token.
                        This token must be confirmed via the API within 5 mins.
            status:     Shows the currently registered callsign (if any)
            remove:		De-registers the user from the internal DB.
        """
        # Do not reply to self
        if message.author.id == self.user.id:
            return

        # Ignore non-DM messages
        elif not isinstance(message.channel, DMChannel):
            return

        # register
        elif message.content.lower() == 'register':

            fcom_api_token = bot_user_commands.register_user(message.channel)

            if fcom_api_token is None:
                msg = "You're already registered! To reset your registration, type `remove` before typing `register` again."
            else:
                msg = f"Here's your Discord code: ```{fcom_api_token}```" + \
                      "\nPlease enter it into the client within the next 5 minutes.\n"
                logger.info(
                    f'Generate token:\t{fcom_api_token}, {message.channel.recipient.id} '
                    f'({message.channel.recipient.name} #{message.channel.recipient.discriminator}) ')
            await message.channel.send(msg)

        # status
        elif message.content.lower() == 'status':

            user = await bot_user_commands.get_user(self, message.channel.recipient)

            if user is None:
                msg = "You're currently not registered."
            elif not user.is_verified:
                msg = f"You're registered, but you haven't logged in via the client yet.\n" + \
                      f"**Discord code:** `{user.token}`"
            else:
                msg = f"You're registered! The callsign you're using is **{user.callsign}**.\n" + \
                      f"**Discord code:** `{user.token}`"

            await message.reply(msg, mention_author=False)

        # remove
        elif message.content.lower() == 'remove':

            if bot_user_commands.remove_user(message.channel.recipient.id):
                msg = "Successfully deregistered! You'll no longer receive forwarded messages."
                logger.info(f'Deregister user:\t{message.channel.recipient.id} '
                            f'({message.channel.recipient.name} #{message.channel.recipient.discriminator})')
            else:
                msg = "Could not unregister. Are you sure you're registered?"

            await message.channel.send(msg)

    # Reference: https://github.com/Rapptz/discord.py/blob/master/examples/background_task.py
    @tasks.loop(seconds=3)
    async def forward_messages(self):
        """
        Background task that retrieves submitted PMs from the DB and forwards them to the registered Discord user.
        """
        # while not bot.is_closed():
        messages = db_manager.get_messages()

        # Iterate through queued messages (if any), and forward them via Discord DM
        if messages is not None:
            for msg in messages:

                dm_user = await db_manager.get_user_record(msg.token, self)

                if dm_user is not None:

                    # if it's a frequency message (i.e. @xxyyy), parse it into a user-friendly format
                    if msg.receiver.startswith('@'):
                        freq = msg.receiver.replace('@', '1')[:3] + '.' + msg.receiver[3:]
                        dm_contents = f'**{msg.sender}** ({freq} MHz):\n{msg.message}'

                    else:
                        dm_contents = f'**{msg.sender}**:\n{msg.message}'

                    dm_channel = dm_user.channel_object
                    try:
                        await dm_channel.send(dm_contents)
                    except discordpy_error.Forbidden:
                        logger.info(f'[HTTP 403] Could not send DM to {dm_user.discord_name} ({dm_user.discord_id})')
                    except discordpy_error.HTTPException as e:
                        logger.error(f'{traceback.format_exc()}')

                else:
                    # NOTE: the API now checks if a token's registered before inserting messages
                    logger.info(f'Token {msg.token} is not registered!')

            # await asyncio.sleep(3)

    @forward_messages.before_loop
    async def before_forward_messages(self):
        await self.wait_until_ready()

    @tasks.loop(minutes=5)
    async def prune_registrations(self):
        """
        Remove registrations that are either unconfirmed and older than 5 minutes,
        or confirmed and older than 24 hours.

        """
        db_manager.remove_stale_users()
        await asyncio.sleep(60*5)

    @prune_registrations.before_loop
    async def before_prune_registrations(self):
        await self.wait_until_ready()


def start_bot():
    """
    Starts the bot
    :return:
    """
    # bot.loop.create_task(forward_messages())
    # bot.loop.create_task(prune_registrations())

    intents = discord.Intents.default()
    intents.messages = True
    intents.members = True

    retry = True

    # Based on https://gist.github.com/Hornwitser/93aceb86533ed3538b6f
    while retry:

        # Linearly increasing backoff for Discord server errors.
        wait_interval = 0
        max_wait_interval = 5 * 60      # 5-minute max interval between retries

        try:
            client = BotClient(intents=intents)
            client.run(token)
            # bot.run(token)

        except discordpy_error.HTTPException as e:
            logging.error("Couldn't login (discord.errors.HTTPException)")
            logging.error(f'{traceback.format_exc()}')

            if wait_interval < max_wait_interval:
                wait_interval = wait_interval + 5
            asyncio.sleep(wait_interval)

        except ClientError as e:
            logging.error("Couldn't login (discord.errors.ClientError)")
            logging.error()
            logging.error(f'{traceback.format_exc()}')

            if wait_interval < max_wait_interval:
                wait_interval = wait_interval + 5
            asyncio.sleep(wait_interval)

        except websocket_error.ConnectionClosed as e:
            logger.info(f'{traceback.format_exc()}')

            # Don't reconnect on authentication failure
            if e.code == 4004:
                logging.error("Authentication error!")
                retry = False
                raise

        else:
            break


start_bot()
