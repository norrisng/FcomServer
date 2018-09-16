from bot.discord_bot import start_bot
from schema import init_messages_db, init_registration_db

if __name__ == "__main__":
    init_registration_db()
    init_messages_db()
    start_bot()
