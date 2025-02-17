import asyncio
import os
import subprocess
import sqlite3
import time
import warnings
import json
import threading
import librosa
import numpy as np
import soundfile
import requests
import zipfile

from tempfile import TemporaryDirectory
from bs4 import BeautifulSoup as bs
from pytubefix import YouTube
from dotenv import load_dotenv

from .FindStartTime import find_time
from ... import socketio
from flask_socketio import emit

# region 특정 경고 무시
warnings.filterwarnings("ignore", category=UserWarning, message="PySoundFile failed.*")
warnings.filterwarnings(
    "ignore", category=FutureWarning, message="librosa.core.audio.__audioread_load.*"
)
# endregion


# region 유튜브 URL 변환
def change_to_youtube_url(embed_url: str) -> str:
    # URL에서 비디오 ID 추출
    video_id = embed_url.split("/")[-1].split("?")[0]
    # 일반 링크 형식으로 변환
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    return watch_url


# endregion


# region 동영상 파일 이름 결정
def get_viewer(author: str, title: str) -> str:
    names = [
        "우왁굳",
        "아이네",
        "징버거",
        "릴파",
        "주르르",
        "고세구",
        "비챤",
        "뢴트게늄",
    ]
    authors = {
        "우왁굳의 반찬가게": "[우왁굳]",
        "데친 숙주나물": "[아이네]",
        "징버거가 ZZANG센 주제에 너무 신중하다": "[징버거]",
        "릴파의 순간들": "[릴파]",
        "주르르": "[주르르]",
        "고세구의 짧은거": "[고세구]",
        "비챤의 나랑놀아": "[비챤]",
        "하치키타치": "[뢴트게늄]",
    }
    wav_path = "원본"  # 기본 경로

    if author == "반응정리":
        for name in names:
            if name in title.split(" ")[0]:  # 제목의 첫 단어와 비교
                wav_path = title.split(" ")[0]  # 첫 단어를 경로로 설정
                break

    if author in authors and "반응" in title:
        wav_path = authors[author]

    return wav_path  # 최종 이름 반환


# endregion 로그인 함수


# region 제목 처리
def process_title(title: str):

    if "했어요]" in title:
        splited_title = title.split("했어요]")[1].replace(" 반응정리", "").split("/")
    else:
        splited_title = title.replace(" 반응정리", "").split("/")

    final_title = "".join(splited_title[:-1])
    viewer = splited_title[-1]

    viewer = viewer.replace("💙", "🩵")
    viewer = viewer.replace("🖤", "💙")


    return [final_title, viewer]


# endregion


class DownloadAudio:
    # region 초기화
    def __init__(self):
        load_dotenv("crawl.env")

        self.temp_dir = TemporaryDirectory().name
        self.origin_audio = None
        self.download_path = "./video"
        self.music_title = "음악"

    # endregion

    # region 진행 상황 출력
    async def print_progress(self, message):
        socketio.emit("progress_update", {"message": message})
        print(message)
        socketio.sleep(0)

    # endregion

    # region 유튜브 링크 가져오기
    async def get_html(self, article_id: str):
        url = f"{os.getenv('NAVER_CAFE_HTML_API')}/{os.getenv('NAVER_CAFE_ID')}/articles/{article_id}?useCafeId=false"
        response = requests.get(url)
        data = response.json()
        # HTML 파싱
        title = data["result"]["article"]["subject"]
        soup = bs(data["result"]["article"]["contentHtml"], "html.parser")

        # '__se_module_data' 클래스를 가진 모든 스크립트 태그 찾기
        datas = soup.find_all(class_="__se_module_data")

        youtube_links = []
        for data in datas:
            # data-module 속성에서 JSON 데이터 추출
            module_data = data.get("data-module")
            if module_data:
                a = json.loads(module_data)["data"]
                if a.get("html") is None:
                    continue

                # HTML 내용에서 <iframe> 태그 추출
                iframe_html = a["html"]
                iframe_soup = bs(iframe_html, "html.parser")
                iframe = iframe_soup.find("iframe")

                # src 속성 추출
                if iframe and "src" in iframe.attrs:
                    youtube_links.append(change_to_youtube_url(iframe["src"]))
        return title, youtube_links

    # endregion

    # region 유튜브 다운로드
    async def download_youtube(self, yt: YouTube, title: str):
        video_stream = yt.streams.filter(
            resolution="1080p", file_extension="mp4"
        ).first()
        audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4").first()

        try:
            video_stream.download(output_path=self.temp_dir, filename=f"{title}.mp4")
            audio_stream.download(output_path=self.temp_dir, filename=f"{title}.wav")

            await self.print_progress(f"Downloaded {title}")
        except Exception as e:
            print(f"Error: {title}")
            print(e)
            return

    # endregion

    # region 동영상 파일 시간 조정
    async def adjust_audio_start_time(self, title: str, output_path: str = "../video"):
        audio, _ = await asyncio.to_thread(
            librosa.load, f"{self.temp_dir}/{title}.wav", sr=None, mono=False
        )
        start_index = await find_time(self.origin_audio, audio[0]) * 512
        start_time = start_index / 44100

        await asyncio.to_thread(
            soundfile.write,
            f"{self.temp_dir}/{title}_compiled.wav",
            audio[:, start_index:].T,
            44100,
        )

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"00:00:{start_time}",  # 시작 시간
            "-i",
            f"{self.temp_dir}/{title}.mp4",  # 입력 비디오 파일
            "-c",
            "copy",  # 비디오와 오디오를 재인코딩하지 않고 복사
            f"{self.temp_dir}/{title}_compiled.mp4",  # 출력 비디오 파일
        ]

        await asyncio.to_thread(
            subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        command = [
            "ffmpeg",
            "-i",
            f"{self.temp_dir}/{title}_compiled.mp4",
            "-i",
            f"{self.temp_dir}/{title}_compiled.wav",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-strict",
            "experimental",
            f"{output_path}/final_{title}.mp4",
        ]

        await asyncio.to_thread(
            subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        await self.print_progress(f"Adjusted {title}")

    # endregion

    # region ZIP 파일 생성
    async def create_zip(self, output_path: str, zip_name: str):
        zip_path = os.path.join(output_path, zip_name)
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for root, _, files in os.walk(self.temp_dir):
                for file in files:
                    if file.split("_")[0] == "final":
                        file_path = os.path.join(root, file)

                        # ZIP 내부에 경로 없이 파일 이름만 추가
                        zipf.write(file_path, arcname=file)

        return zip_path

    # endregion

    # region 오디오 다운로드 함수
    async def download_audio(self, url_id: str):

        # region 이미 처리된 파일 있는지 확인
        if os.path.exists(f"./video/{url_id}.zip"):
            return
        # endregion

        current_title, youtube_links = await self.get_html(
            url_id
        )  # 유튜브 링크 가져오기

        # region 에러 처리
        if len(youtube_links) == 0:
            print("ERROR")
            return
        # endregion

        # region 제목 비교 및 업데이트
        db_conn = sqlite3.connect("./database/posted_link.db")
        db_cur = db_conn.cursor()
        db_cur.execute("SELECT title FROM posted_link WHERE link = ?", (url_id,))
        past_title = db_cur.fetchone()

        if current_title != past_title[0]:
            db_cur.execute(
                "UPDATE posted_link SET title = ? WHERE link = ?",
                (current_title, url_id),
            )
            db_conn.commit()
        db_conn.close()
        # endregion

        # region 유튜브 영상 다운로드
        youtubes_dict = {}
        for link in youtube_links:
            try:
                yt = YouTube(link, use_po_token=True)
                youtubes_dict[get_viewer(yt.author, yt.title)] = yt
            except Exception as e:
                print(f"Error: {link}")
                print(e)
                pass

        default_name = "원본"
        if not "원본" in youtubes_dict.keys():
            await self.print_progress("No original video")
            await self.print_progress(f"Use {list(youtubes_dict.keys())[0]} as default")
            default_name = list(youtubes_dict.keys())[0]

        # region 원본 영상 처리
        await self.download_youtube(youtubes_dict[default_name], "원본")
        del youtubes_dict[default_name]

        command = [
            "ffmpeg",
            "-i",
            f"{self.temp_dir}/원본.mp4",
            "-i",
            f"{self.temp_dir}/원본.wav",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-strict",
            "experimental",
            f"{self.temp_dir}/final_원본.mp4",
        ]

        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # endregion

        if len(youtubes_dict) == 0:
            await self.print_progress("No reaction video")
            return

        self.origin_audio, _ = librosa.load(
            f"{self.temp_dir}/원본.wav", sr=None, mono=True
        )
        # region 다운로드 및 시간 조정
        for key in youtubes_dict.keys():
            await self.download_youtube(youtubes_dict[key], key)
        for key in youtubes_dict.keys():
            await self.adjust_audio_start_time(key, self.temp_dir)

        await self.create_zip(self.download_path, f"{url_id}.zip")

        # endregion

        # endregion

    # endregion
