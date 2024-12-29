from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="http://localhost:3000")


def create_app(debug=False):
    app = Flask(__name__)
    CORS(app)
    app.debug = debug

    from .backend import main as main_blueprint

    app.register_blueprint(main_blueprint)

    socketio.init_app(app)
    return app
