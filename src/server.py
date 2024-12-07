from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from flask_socketio import SocketIO
import sqlite3
import asyncio
import os
import tracemalloc

from services.crawlService import CrawlService
from services.DownloadAudio import DownloadAudio, process_title

tracemalloc.start()
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="http://localhost:3000")


# region 데이터 가져오기
async def get_data():
    if not os.path.exists("../database/posted_link.db"):
        await CrawlService().checkForNewPosts(100)

    db_conn = sqlite3.connect("../database/posted_link.db")
    db_cur = db_conn.cursor()
    db_cur.execute("SELECT * FROM posted_link ORDER BY link DESC")
    db_list = db_cur.fetchall()
    db_conn.close()

    title_dict = {}
    for item in db_list:
        title_dict[item[0]] = process_title(item[1])

    return title_dict


# endregion


# region 데이터 보내기
@app.route("/api/data", methods=["GET"])
async def send_data():
    data = await get_data()
    return jsonify(data)


# endregion


# region 새로 고침
@app.route("/api/trigger_refresh", methods=["POST"])
def trigger_refresh():
    # 클라이언트에게 새로 고침 신호 전송
    socketio.emit("refresh", {"message": "Please refresh the page!"})
    return "Refresh signal sent!", 200


# endregion


# region 다운로드 신호 받아오기
@app.route("/api/signal", methods=["POST"])
def get_signal():
    data = request.get_json()
    asyncio.run(DownloadAudio(data).download_audio())
    socketio.emit("done", {"message": "Successfully downloaded!"})
    return "Signal received", 200


# endregion


# region 게시물 다시 받아오기
@app.route("/api/refresh", methods=["POST"])
async def get_refresh():
    await CrawlService().check_new_posts(10)
    await send_data()
    trigger_refresh()
    return jsonify({"message": "Signal received"}), 200


# endregion

if __name__ == "__main__":
    socketio.run(app, allow_unsafe_werkzeug=True)
