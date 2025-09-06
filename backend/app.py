import os.path

from flask import Flask, Blueprint, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv

from events import main as main_blueprint
load_dotenv()

app = Flask(__name__, static_folder="./build", template_folder="./build")
app.config['SECRET_KEY'] = os.getenv("SECRECT_KEY")
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


if __name__ == "__main__":
    Flask.run(app, host="0.0.0.0", port=5000)
