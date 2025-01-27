import asyncio
import os
import sqlite3
import time
import json
import re

from flask import request, jsonify, send_file
from flask_socketio import join_room, leave_room, emit

from . import main
from .features import *
from .. import socketio

down_task_id = 0

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
        s = process_title(item[1])
        if not bool(re.search(r"[가-힣A-Za-z]", s[1])):
            title_dict[item[0]] = s

    return title_dict

def run_async_task(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@socketio.on("refresh")
def get_refresh():
    run_async_task(CrawlService().check_new_posts(10))
    socketio.emit("refresh", {"message": "Please refresh the page!"})

@main.route("/data", methods=["GET"])
def send_data():
    data = run_async_task(fetch_data())
    return jsonify(data)

@main.route("/download/<zip_name>", methods=["GET"])
def download_zip(zip_name):
    zip_path = os.path.join(os.path.abspath("./video"), zip_name)
    return send_file(zip_path, as_attachment=True)

@socketio.on("download_signal")
def handle_signal(data):
    run_async_task(download_video(data))
    socketio.emit("done", {"message": "Signal received"})

async def download_video(data):
    await DownloadAudio().download_audio(data)