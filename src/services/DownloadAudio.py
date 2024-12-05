import asyncio
import os
import sqlite3
import subprocess
import time
import tkinter as tk
from tempfile import TemporaryDirectory

import librosa
import numpy as np
import soundfile
from bs4 import BeautifulSoup as bs
from constants.crawl import SAMPLE_RATE
from pytubefix import YouTube
from selenium import webdriver
from selenium.webdriver.common.by import By

from .FindStartTime import find_time


# region 폴더 정리
def clear_folder(path: str):
    if not os.path.exists(path):
        os.makedirs(path)  # 폴더가 없으면 생성
    else:
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)  # 파일 삭제


# endregion


# region 로그인
def login():
    login_url = "https://nid.naver.com/nidlogin.login"

    options = webdriver.ChromeOptions()
    options.add_argument("disable-gpu")  # GPU 가속 비활성화
    options.add_argument("headless")

    # Chrome 브라우저 인스턴스 생성
    browser = webdriver.Chrome(options=options)
    browser.get(login_url)  # 로그인 페이지 열기
    browser.implicitly_wait(2)  # 로드 대기

    browser.execute_script(
        f"document.getElementsByName('id')[0].value='{os.getenv('NAVER_ID')}'"
    )  # ID 입력
    browser.execute_script(
        f"document.getElementsByName('pw')[0].value='{os.getenv('NAVER_PW')}'"
    )  # 비밀번호 입력
    browser.find_element(
        by=By.XPATH, value='//*[@id="log.login"]'
    ).click()  # 로그인 버튼 클릭
    time.sleep(1)  # 잠시 대기

    return browser


# endregion


# region 유튜브 URL 변환
def change_to_youtube_url(source: str) -> str:
    video_id = (
        source.split("src=")[1]
        .split('"')[1]
        .replace("\\", "")
        .split("/")[-1]
        .split("?")[0]
    )  # 비디오 ID 추출
    return f"https://www.youtube.com/watch?v={video_id}"  # 유튜브 URL 반환


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

    if author in authors:
        wav_path = authors[author]

    return wav_path  # 최종 이름 반환


# endregion 로그인 함수


class DownloadAudio:
    # region 초기화
    def __init__(self, url: str):
        self.url = url
        db_conn = sqlite3.connect("../database/posted_link.db")
        db_cur = db_conn.cursor()
        db_cur.execute("SELECT * FROM posted_link ORDER BY link DESC")
        self.db_list = db_cur.fetchall()
        db_conn.close()
        self.temp_dir = TemporaryDirectory().name
        self.origin_audio = None

    # endregion

    # region 유튜브 다운로드
    async def download_youtube(self, yt: YouTube, title: str):
        video_stream = yt.streams.filter(
            resolution="1080p", file_extension="mp4"
        ).first()
        audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4").first()

        video_stream.download(output_path=self.temp_dir, filename=f"{title}.mp4")
        audio_stream.download(output_path=self.temp_dir, filename=f"{title}.wav")

    # endregion

    # region 동영상 파일 시간 조정
    async def adjust_audio_start_time(self, title: str):
        audio, _ = await asyncio.to_thread(
            librosa.load, f"{self.temp_dir}/{title}.wav", sr=None
        )
        start_index = await find_time(self.origin_audio, audio) * 512
        start_time = start_index / 44100

        await asyncio.to_thread(
            soundfile.write,
            f"{self.temp_dir}/{title}.wav",
            audio[start_index:],
            SAMPLE_RATE,
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
            f"{self.temp_dir}/{title}.wav",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-strict",
            "experimental",
            f"../data/video/{title}.mp4",
        ]

        await asyncio.to_thread(
            subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    # endregion

    # region 오디오 다운로드 함수
    async def download_audio(self):
        youtube_links = []
        download_tasks = []
        adjust_tasks = []
        download_path = "../data/video"

        # region 기존 파일 삭제
        clear_folder(download_path)
        # endregion

        # region 크롤링
        browser = login()

        browser.get(self.url)

        time.sleep(2)

        browser.switch_to.frame("cafe_main")
        soup = bs(browser.page_source, "html.parser")
        datas = soup.find_all(
            class_="se-component se-oembed se-l-default __se-component"
        )
        # endregion

        # region 유튜브 링크 가져오기
        for data in datas:
            data = data.find_all_next(class_="__se_module_data")[0]
            watch_url = change_to_youtube_url(str(data))
            youtube_links.append(watch_url)
        browser.quit()
        # endregion

        # region 에러 처리
        if len(youtube_links) == 0:
            print("ERROR")
            return
        # endregion

        # region 유튜브 영상 다운로드
        youtubes_dict = {}
        for link in youtube_links:
            yt = YouTube(link)
            youtubes_dict[get_viewer(yt.author, yt.title)] = yt

        # region 원본 영상 처리
        await self.download_youtube(youtubes_dict["원본"], "원본")
        del youtubes_dict["원본"]

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
            f"../data/video/원본.mp4",
        ]

        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # endregion

        self.origin_audio, _ = librosa.load(
            f"{self.temp_dir}/원본.wav", sr=None, mono=True
        )

        # region 다운로드 및 시간 조정
        for key in youtubes_dict.keys():
            download_tasks.append(self.download_youtube(youtubes_dict[key], key))
            adjust_tasks.append(self.adjust_audio_start_time(key))

        await asyncio.gather(*download_tasks)
        await asyncio.gather(*adjust_tasks)
        # endregion

        # endregion

    # endregion
