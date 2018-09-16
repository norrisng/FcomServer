from api.message_api import app
from schema import init_messages_db, init_registration_db

if __name__ == "__main__":
    init_registration_db()
    init_messages_db()
    app.run(host='0.0.0.0', debug=False)
