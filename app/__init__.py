from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

if __name__ == "__main__":
    socketio = SocketIO(cors_allowed_origins="*", ping_timeout=600, ping_interval=25, async_mode='eventlet')
    app = Flask(__name__, static_folder="./frontend/build")
    CORS(app, resources=(r"/api/*", {"origins": "*"}))
    app.debug = debug

    from .backend import main as main_blueprint

    app.register_blueprint(main_blueprint)

    socketio.init_app(app)

    app = create_app(debug=True)
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)