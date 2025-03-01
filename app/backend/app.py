import os.path

from flask import Flask, Blueprint, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

from events import main as main_blueprint, socketio

app = Flask(__name__, static_folder="../frontend/build", template_folder="../frontend/build")
CORS(app)
app.debug = True

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    if path != "" and os.path.exists(app.static_folder + "/" + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, "index.html")

app.register_blueprint(main_blueprint)
socketio.init_app(app)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)