import time
import csv
import os
import sqlite3
import tkinter as tk
import soundfile
import subprocess
import asyncio
import librosa
import numpy as np

from tempfile import TemporaryDirectory

from tkinter import messagebox as msgbox
from tkinter import ttk

from pytubefix import YouTube
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup as bs

from .FindStartTime import find_time
from constants.crawl import SAMPLE_RATE
from constants import Personal_information


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


# region 유튜브 다운로드
async def download_youtube(yt: YouTube, title: str, temp_dir: str):

    video_stream = yt.streams.filter(resolution="1080p", file_extension="mp4").first()
    audio_stream = yt.streams.filter(only_audio=True, file_extension="mp4").first()

    video_stream.download(output_path=temp_dir, filename=f"{title}.mp4")
    audio_stream.download(output_path=temp_dir, filename=f"{title}.wav")

    print(f"{title} 다운로드 완료")


# endregion


# region 동영상 파일 시간 조정
async def adjust_audio_start_time(title: str, temp_dir: str, origin_audio: np.ndarray):

    if title != "원본":
        audio, _ = await asyncio.to_thread(
            librosa.load, f"{temp_dir}/{title}.wav", sr=None
        )
        start_index = await find_time(origin_audio, audio) * 512
        start_time = start_index / 44100

        await asyncio.to_thread(
            soundfile.write,
            f"{temp_dir}/{title}.wav",
            audio[0][start_index:],
            SAMPLE_RATE,
        )

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"00:00:{start_time}",  # 시작 시간
            "-i",
            f"{temp_dir}/{title}.mp4",  # 입력 비디오 파일
            "-c",
            "copy",  # 비디오와 오디오를 재인코딩하지 않고 복사
            f"{temp_dir}/video.mp4",  # 출력 비디오 파일
        ]

        await asyncio.to_thread(
            subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    else:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            f"{temp_dir}/{title}.mp4",  # 입력 비디오 파일
            "-c",
            "copy",  # 비디오와 오디오를 재인코딩하지 않고 복사
            f"{temp_dir}/video.mp4",  # 출력 비디오 파일
        ]

        await asyncio.to_thread(
            subprocess.run, command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    command = [
        "ffmpeg",
        "-i",
        f"{temp_dir}/video.mp4",
        "-i",
        f"{temp_dir}/{title}.wav",
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

    print(f"{title} 최적화 완료")


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
        f"document.getElementsByName('id')[0].value='{Personal_information.NAVER_ID}'"
    )  # ID 입력
    browser.execute_script(
        f"document.getElementsByName('pw')[0].value='{Personal_information.NAVER_PW}'"
    )  # 비밀번호 입력
    browser.find_element(
        by=By.XPATH, value='//*[@id="log.login"]'
    ).click()  # 로그인 버튼 클릭
    time.sleep(1)  # 잠시 대기

    return browser


# endregion


class DownloadAudio:
    # region 초기화
    def __init__(self):
        self.url = None
        db_conn = sqlite3.connect("../database/posted_link.db")
        db_cur = db_conn.cursor()
        db_cur.execute("SELECT * FROM posted_link ORDER BY link DESC")
        self.db_list = db_cur.fetchall()
        db_conn.close()

    # endregion

    # region 오디오 선택 함수
    def select_audio(self):
        root = tk.Tk()
        root.title("오디오 선택창")
        root.geometry("400x300")

        tk.Label(root, text="Download Audio").grid(
            row=0, column=0, columnspan=2, padx=5, pady=5
        )

        listbox = tk.Listbox(root, width=50)
        listbox.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        for item in self.db_list:
            listbox.insert(tk.END, item[1])

        def on_double_click(event):
            select = listbox.curselection()
            if select:
                self.url = self.db_list[select[0]][0]  # 선택된 URL 저장
                root.destroy()  # 창 닫기

        listbox.bind("<Double-1>", on_double_click)  # 더블 클릭 이벤트 바인딩
        root.mainloop()  # Tkinter 이벤트 루프 시작

    # endregion

    # region 오디오 다운로드 함수
    async def download_audio(self):
        youtube_links = []
        download_path = "../data/video"

        self.select_audio()

        if self.url is None:
            return

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

        temp_dict = TemporaryDirectory().name

        tasks = []
        for key in youtubes_dict.keys():
            tasks.append(download_youtube(youtubes_dict[key], key, temp_dict))

        await asyncio.gather(*tasks)

        print("TEST")

        origin_audio, _ = librosa.load(f"{temp_dict}/원본.wav", sr=None)

        tasks = []
        for key in youtubes_dict.keys():
            tasks.append(adjust_audio_start_time(key, temp_dict, origin_audio))

        await asyncio.gather(*tasks)
        # endregion

    # endregion
