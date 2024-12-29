import asyncio
import os
import sqlite3

from flask import request, jsonify
from flask_socketio import emit, SocketIO
from dotenv import load_dotenv

from . import main
from .features import *
from .. import socketio

async def fetch_data():
    if not os.path.exists("./database/posted_link.db"):
        await CrawlService().checkForNewPosts(100)

    db_conn = sqlite3.connect("./database/posted_link.db")
    db_cur = db_conn.cursor()
    db_cur.execute("SELECT * FROM posted_link ORDER BY link DESC")
    db_list = db_cur.fetchall()
    db_conn.close()

    title_dict = {}
    for item in db_list:
        title_dict[item[0]] = process_title(item[1])

    return title_dict


@main.route("/refresh", methods=["POST"])
def get_refresh():
    asyncio.run(CrawlService().check_new_posts(10))
    data = asyncio.run(fetch_data())
    trigger_refresh()
    return jsonify({"message": "Signal received", "data": data}), 200


@main.route("/data", methods=["GET"])
def send_data():
    data = asyncio.run(fetch_data())
    return jsonify(data)

@main.route("/trigger_refresh", methods=["POST"])
def trigger_refresh():
    socketio.emit("refresh", {"message": "Please refresh the page!"})
    return "Refresh signal sent!", 200


@main.route("/signal", methods=["POST"])
def get_signal():
    data = request.get_json()
    load_dotenv("crawl.env")
    asyncio.create_task(
        DownloadAudio(data).download_audio(os.getenv("NAVER_ID"), os.getenv("NAVER_PW"))
    )
    socketio.emit("done", {"message": "Successfully downloaded!"})
    return "Signal received", 200
