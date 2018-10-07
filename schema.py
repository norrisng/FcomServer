import sqlite3
import os

REGISTRATION_PATH = os.path.realpath('../FcomServer/registration.db')
MESSAGES_PATH = os.path.realpath('../FcomServer/messages.db')


def init_registration_db():
    conn = sqlite3.connect(REGISTRATION_PATH)
    db = conn.cursor()
    registration_schema = """
                            CREATE TABLE IF NOT EXISTS registration ( 
                                    last_updated INTEGER,
                                    token TEXT, 
                                    discord_id INTEGER UNIQUE, 
                                    discord_name TEXT, 
                                    is_verified INTEGER, 
                                    callsign TEXT, 
                                    PRIMARY KEY(token, discord_id) 
                            );
                        """
    db.execute(registration_schema)
    conn.commit()
    conn.close()


def init_messages_db():
    conn = sqlite3.connect(MESSAGES_PATH)
    db = conn.cursor()
    messages_schema = """
                        CREATE TABLE IF NOT EXISTS messages ( 
                            id INTEGER PRIMARY KEY AUTOINCREMENT, 
                            insert_time INTEGER NOT NULL, 
                            token TEXT NOT NULL, 
                            timestamp REAL NOT NULL, 
                            sender TEXT NOT NULL, 
                            receiver TEXT NOT NULL, 
                            message TEXT 
                        );
                    """
    db.execute(messages_schema)
    conn.commit()
    conn.close()
