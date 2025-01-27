import sys
import os
from dotenv import load_dotenv
from werkzeug.serving import is_running_from_reloader

if __name__ == "__main__":
    if not is_running_from_reloader():
        print("Starting server")

    from app import create_app, socketio

    app = create_app(debug=True)
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)