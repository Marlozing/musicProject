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

# 새로고침 이벤트
@socketio.on("refresh")
def get_refresh():
    run_async_task(CrawlService().check_new_posts(10))
    socketio.emit("refresh", {"message": "Please refresh the page!"})

# 데이터 요청 이벤트
@main.route("/data", methods=["GET"])
def send_data():
    data = run_async_task(fetch_data())
    return jsonify(data)

# 다운로드 이벤트
@main.route("/download/<zip_name>", methods=["GET"])
def download_zip(zip_name):
    zip_path = os.path.join(os.path.abspath("./video"), zip_name)
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True, mimetype="application/zip")
    else:
        return jsonify({"message": "File not found"})

# 파일 삭제 이벤트
@main.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        # 파일 삭제 처리
        file_path = os.path.join('./video', filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'message': f'{filename} deleted successfully'}), 200
        else:
            return jsonify({'error': f'{filename} not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 다운로드 신호 이벤트
@socketio.on("download_signal")
def handle_signal(data):
    print(data)
    run_async_task(download_video(data))
    print(data)
    socketio.emit("done", {"message": "Signal received"})

async def download_video(data):
    await DownloadAudio().download_audio(data)