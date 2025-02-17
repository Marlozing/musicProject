from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*", ping_timeout=600, ping_interval=25, async_mode='eventlet')

def create_app(debug=False):
    app = Flask(__name__)
    CORS(app, resources=(r"/api/*", {"origins": "*"}))
    app.debug = debug

    from .backend import main as main_blueprint

    app.register_blueprint(main_blueprint)

    socketio.init_app(app)
    return app